#!/usr/bin/env python3
"""
WebSocket连接处理器 - 管理与Gotty服务的WebSocket连接
"""

import websocket
import json
import base64
import logging
import time
import threading
from typing import Optional, Callable, Dict, Any
from urllib.parse import urlparse, urlencode

class WebSocketHandler:
    """WebSocket连接管理器"""
    
    def __init__(self, base_url: str, username: str, password: str):
        self.base_url = base_url
        self.username = username
        self.password = password
        self.ws: Optional[websocket.WebSocket] = None
        self.connected = False
        self.reconnect_attempts = 0
        self.max_reconnect_attempts = 3
        self.reconnect_delay = 2
        
        # 消息重组缓冲区
        self.message_buffer = ""
        self.fragment_buffer = []
        self.max_buffer_size = 50000  # 50KB限制
        
        # 设置日志
        self.logger = logging.getLogger(__name__)
        
        # WebSocket URL
        parsed_url = urlparse(self.base_url)
        ws_scheme = "wss" if parsed_url.scheme == "https" else "ws"
        self.ws_url = f"{ws_scheme}://{parsed_url.netloc}/ws"
        
        # 认证头
        credentials = base64.b64encode(f"{username}:{password}".encode()).decode()
        self.headers = {
            'Authorization': f'Basic {credentials}',
            'User-Agent': 'Terminal-API-Client/1.0'
        }
    
    def connect(self) -> bool:
        """建立WebSocket连接"""
        try:
            self.logger.info(f"正在连接到 {self.ws_url}")
            
            # 创建WebSocket连接
            self.ws = websocket.WebSocket()
            
            # 连接到WebSocket（不需要在URL中包含认证信息）
            self.ws.connect(self.ws_url)
            
            # 连接成功后，发送认证消息（这是Gotty的认证方式）
            auth_message = {
                "Arguments": "",  # 命令行参数
                "AuthToken": f"{self.username}:{self.password}"  # 认证token
            }
            
            self.ws.send(json.dumps(auth_message))
            self.connected = True
            self.reconnect_attempts = 0
            
            self.logger.info("WebSocket连接和认证成功")
            return True
            
        except Exception as e:
            self.logger.error(f"WebSocket连接失败: {e}")
            self.connected = False
            return False
    
    def disconnect(self):
        """关闭WebSocket连接"""
        if self.ws:
            try:
                self.ws.close()
                self.logger.info("WebSocket连接已关闭")
            except Exception as e:
                self.logger.error(f"关闭WebSocket连接时出错: {e}")
            finally:
                self.ws = None
                self.connected = False
    
    def reconnect(self) -> bool:
        """重新连接WebSocket"""
        if self.reconnect_attempts >= self.max_reconnect_attempts:
            self.logger.error(f"重连次数已达上限 ({self.max_reconnect_attempts})")
            return False
        
        self.reconnect_attempts += 1
        self.logger.info(f"尝试重连 (第 {self.reconnect_attempts} 次)")
        
        # 先关闭现有连接
        self.disconnect()
        
        # 等待一段时间后重连
        time.sleep(self.reconnect_delay * self.reconnect_attempts)
        
        return self.connect()
    
    def send_message(self, message: Dict[str, Any]) -> bool:
        """发送消息到WebSocket"""
        if not self.connected or not self.ws:
            self.logger.error("WebSocket未连接，无法发送消息")
            return False
        
        try:
            message_json = json.dumps(message)
            self.ws.send(message_json)
            self.logger.debug(f"发送消息: {message_json}")
            return True
            
        except Exception as e:
            self.logger.error(f"发送消息失败: {e}")
            self.connected = False
            return False
    
    def receive_message(self, timeout: float = 1.0) -> Optional[Dict[str, Any]]:
        """接收WebSocket消息"""
        if not self.connected or not self.ws:
            return None
        
        try:
            self.ws.settimeout(timeout)
            message = self.ws.recv()
            
            if not message:
                return None
            
            self.logger.debug(f"接收原始消息: {repr(message)}")
            
            # 处理Gotty消息格式
            if isinstance(message, str) and len(message) > 0:
                # 1. 检查标准Gotty格式 ('0' + base64)
                if message.startswith('0'):
                    try:
                        import base64
                        decoded_data = base64.b64decode(message[1:]).decode('utf-8')
                        return {"type": "output", "data": decoded_data}
                    except:
                        return {"type": "output", "data": message[1:]}
                
                elif message.startswith('1'):
                    return {"type": "pong", "data": message[1:]}
                elif message.startswith('2'):
                    return {"type": "title", "data": message[1:]}
                
                # 2. 尝试直接base64解码（处理分片情况）
                else:
                    # 添加到缓冲区
                    self.message_buffer += message
                    
                    # 尝试解码缓冲区
                    try:
                        import base64
                        decoded_data = base64.b64decode(self.message_buffer).decode('utf-8')
                        # 成功解码，清空缓冲区
                        self.message_buffer = ""
                        return {"type": "output", "data": decoded_data}
                    except:
                        # 解码失败，检查缓冲区大小
                        if len(self.message_buffer) > self.max_buffer_size:
                            # 缓冲区过大，清空并返回原始数据
                            result = self.message_buffer
                            self.message_buffer = ""
                            return {"type": "output", "data": result}
                        
                        # 继续等待更多数据
                        return None
            
            # 尝试解析JSON（备用方案）
            try:
                data = json.loads(message)
                self.logger.debug(f"接收JSON消息: {data}")
                return data
            except json.JSONDecodeError:
                # 如果不是JSON格式，包装为输出消息
                return {
                    "type": "output",
                    "data": str(message)
                }
                
        except websocket.WebSocketTimeoutException:
            # 超时是正常的，返回None
            return None
        except websocket.WebSocketConnectionClosedException:
            self.logger.warning("WebSocket连接已关闭")
            self.connected = False
            return None
        except Exception as e:
            self.logger.error(f"接收消息失败: {e}")
            self.connected = False
            return None
    
    def send_command(self, command: str) -> bool:
        """发送命令到终端"""
        # Gotty使用特殊格式：'0' + 命令内容
        message = "0" + command + "\n"
        
        if not self.connected or not self.ws:
            self.logger.error("WebSocket未连接，无法发送命令")
            return False
        
        try:
            self.ws.send(message)
            self.logger.debug(f"发送命令: {repr(message)}")
            return True
        except Exception as e:
            self.logger.error(f"发送命令失败: {e}")
            self.connected = False
            return False
    
    def is_connected(self) -> bool:
        """检查连接状态"""
        return self.connected and self.ws is not None
    
    def ping(self) -> bool:
        """发送ping检查连接"""
        if not self.is_connected():
            return False
        
        try:
            self.ws.ping()
            return True
        except Exception as e:
            self.logger.error(f"Ping失败: {e}")
            self.connected = False
            return False
    
    def _looks_like_base64(self, text: str) -> bool:
        """检查字符串是否看起来像base64编码"""
        import re
        # base64字符集：A-Z, a-z, 0-9, +, /, =
        base64_pattern = re.compile(r'^[A-Za-z0-9+/]*={0,2}$')
        return bool(base64_pattern.match(text)) and len(text) % 4 == 0
    
    def _process_message_smart(self, message: str) -> Optional[Dict[str, Any]]:
        """智能处理消息，支持分片重组"""
        import base64
        import re
        
        # ANSI清理正则表达式
        ansi_escape = re.compile(r'\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])')
        
        def clean_ansi(text):
            """清理ANSI代码"""
            return ansi_escape.sub('', text)
        
        # 1. 检查标准Gotty协议格式
        if len(message) > 0:
            msg_type = message[0]
            data = message[1:] if len(message) > 1 else ""
            
            if msg_type == '0':
                # 终端输出数据（base64编码）
                try:
                    decoded_data = base64.b64decode(data).decode('utf-8')
                    cleaned_data = clean_ansi(decoded_data).strip()
                    self.logger.debug(f"标准格式解码: {repr(cleaned_data)}")
                    self._clear_buffers()  # 清空缓冲区
                    return {"type": "output", "data": cleaned_data}
                except Exception as e:
                    self.logger.warning(f"标准格式解码失败: {e}")
                    return {"type": "output", "data": data}
            
            elif msg_type == '1':
                self._clear_buffers()
                return {"type": "pong", "data": data}
            elif msg_type == '2':
                self._clear_buffers()
                return {"type": "title", "data": data}
            elif msg_type == '3':
                self._clear_buffers()
                try:
                    import json
                    return {"type": "preferences", "data": json.loads(data)}
                except:
                    return {"type": "preferences", "data": data}
            elif msg_type == '4':
                self._clear_buffers()
                return {"type": "reconnect", "data": data}
        
        # 2. 尝试直接解码整个消息（可能是完整的base64）
        if self._looks_like_base64(message) and len(message) > 10:
            try:
                decoded_data = base64.b64decode(message).decode('utf-8')
                cleaned_data = clean_ansi(decoded_data).strip()
                if cleaned_data:  # 只有非空内容才返回
                    self.logger.debug(f"直接解码成功: {repr(cleaned_data)}")
                    self._clear_buffers()  # 清空缓冲区
                    return {"type": "output", "data": cleaned_data}
            except:
                pass
        
        # 3. 添加到片段缓冲区并尝试重组
        self.fragment_buffer.append(message)
        
        # 尝试重组缓冲区中的片段
        result = self._try_reassemble_fragments()
        if result:
            return result
        
        # 4. 检查是否是明显的非base64短消息
        if len(message) < 10 and not self._looks_like_base64(message):
            # 可能是错误消息或状态信息，直接返回
            self._clear_buffers()
            return {"type": "output", "data": message}
        
        # 5. 检查缓冲区是否过大
        total_buffer_size = sum(len(frag) for frag in self.fragment_buffer)
        if total_buffer_size > self.max_buffer_size:
            self.logger.warning(f"缓冲区过大({total_buffer_size}字符)，清空并返回原始数据")
            combined_data = ''.join(self.fragment_buffer)
            self._clear_buffers()
            return {"type": "output", "data": combined_data}
        
        # 6. 继续等待更多片段
        return None
    
    def _try_reassemble_fragments(self) -> Optional[Dict[str, Any]]:
        """尝试重组片段缓冲区中的数据"""
        import base64
        import re
        
        if not self.fragment_buffer:
            return None
        
        # ANSI清理正则表达式
        ansi_escape = re.compile(r'\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])')
        
        # 尝试不同的组合方式
        for start_idx in range(len(self.fragment_buffer)):
            for end_idx in range(start_idx + 1, len(self.fragment_buffer) + 1):
                # 组合片段
                combined = ''.join(self.fragment_buffer[start_idx:end_idx])
                
                # 尝试解码
                if self._looks_like_base64(combined):
                    try:
                        decoded_data = base64.b64decode(combined).decode('utf-8')
                        cleaned_data = ansi_escape.sub('', decoded_data).strip()
                        
                        if cleaned_data:  # 只有非空内容才返回
                            self.logger.debug(f"重组解码成功: {repr(cleaned_data)}")
                            
                            # 移除已使用的片段
                            self.fragment_buffer = self.fragment_buffer[:start_idx] + self.fragment_buffer[end_idx:]
                            
                            return {"type": "output", "data": cleaned_data}
                    except:
                        continue
        
        return None
    
    def _clear_buffers(self):
        """清空所有缓冲区"""
        self.message_buffer = ""
        self.fragment_buffer = []
