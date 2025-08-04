#!/usr/bin/env python3
"""
ttyd WebSocket客户端
基于实测结果修复认证和协议问题
"""

import asyncio
import websockets
import base64
import json
import logging
import re
from typing import Optional, Callable, Dict, Any
from dataclasses import dataclass
from enum import Enum
from datetime import datetime

logger = logging.getLogger(__name__)

class ConnectionState(Enum):
    """连接状态"""
    DISCONNECTED = "disconnected"
    CONNECTING = "connecting" 
    CONNECTED = "connected"
    ERROR = "error"

@dataclass
class TtydMessage:
    """ttyd消息"""
    data: str
    timestamp: float
    message_type: str = "output"

class ANSICleaner:
    """ANSI清理器 - 兼容各种终端类型"""
    
    def __init__(self):
        # 组合正则表达式 - 清理ANSI转义序列和OSC序列
        self.ansi_pattern = re.compile(r'\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])')
        self.osc_pattern = re.compile(r'\x1B\][^\x07]*\x07')
        self.control_chars = re.compile(r'[\x00-\x08\x0B\x0C\x0E-\x1F\x7F-\x9F]')
    
    def clean(self, text: str) -> str:
        """清理ANSI转义序列"""
        if not text:
            return text
        
        original_text = text
        
        # 移除ANSI转义序列
        text = self.ansi_pattern.sub('', text)
        # 移除OSC序列  
        text = self.osc_pattern.sub('', text)
        # 移除其他控制字符（保留换行符、制表符）
        text = self.control_chars.sub('', text)
        
        # 调试：如果清理前后有差异，记录日志
        if original_text != text:
            logger.debug(f"ANSI清理: {repr(original_text)} -> {repr(text)}")
        
        return text.strip()
    
    def is_meaningful(self, text: str) -> bool:
        """判断是否为有意义的内容"""
        cleaned = self.clean(text)
        return len(cleaned) > 0 and not cleaned.isspace()

class TtydWebSocketClient:
    """修复后的 ttyd WebSocket 客户端"""
    
    def __init__(self, host: str = "localhost", port: int = 7681,
                 username: str = "demo", password: str = "password123",
                 use_ssl: bool = False):
        """
        初始化客户端
        
        Args:
            host: ttyd服务器主机
            port: ttyd服务器端口  
            username: 认证用户名
            password: 认证密码
            use_ssl: 是否使用SSL
        """
        self.host = host
        self.port = port
        self.username = username
        self.password = password
        self.use_ssl = use_ssl
        
        # WebSocket连接
        self.websocket: Optional[websockets.WebSocketServerProtocol] = None
        self.state = ConnectionState.DISCONNECTED
        
        # 消息处理
        self.message_handler: Optional[Callable[[str], None]] = None
        self.error_handler: Optional[Callable[[Exception], None]] = None
        
        # 内部状态
        self._listen_task: Optional[asyncio.Task] = None
        self._should_stop = False
        
        # ANSI清理器
        self.ansi_cleaner = ANSICleaner()
        
        # 认证令牌
        self.auth_token = base64.b64encode(f"{username}:{password}".encode()).decode()
        
    @property
    def url(self) -> str:
        """获取WebSocket URL"""
        protocol = "wss" if self.use_ssl else "ws"
        return f"{protocol}://{self.host}:{self.port}/ws"
    
    @property
    def is_connected(self) -> bool:
        """检查是否已连接"""
        if self.websocket is None or self.state != ConnectionState.CONNECTED:
            return False
        
        # 兼容不同版本的websockets库
        try:
            # 新版本websockets使用close_code检查
            if hasattr(self.websocket, 'close_code'):
                return self.websocket.close_code is None
            # 旧版本使用closed属性
            elif hasattr(self.websocket, 'closed'):
                return not self.websocket.closed
            # 其他情况，检查连接状态
            else:
                return self.state == ConnectionState.CONNECTED
        except Exception:
            return self.state == ConnectionState.CONNECTED
    
    def set_message_handler(self, handler: Callable[[str], None]):
        """设置消息处理器"""
        self.message_handler = handler
    
    def set_error_handler(self, handler: Callable[[Exception], None]):
        """设置错误处理器"""
        self.error_handler = handler
    
    async def connect(self) -> bool:
        """连接到ttyd服务器"""
        if self.is_connected:
            logger.warning("已经连接到ttyd服务器")
            return True
            
        try:
            self.state = ConnectionState.CONNECTING
            logger.info(f"连接到ttyd服务器: {self.url}")
            
            # 关键修复：在WebSocket握手时提供HTTP基本认证头
            self.websocket = await websockets.connect(
                self.url,
                subprotocols=['tty'],
                additional_headers={
                    "Authorization": f"Basic {self.auth_token}"
                },
                ping_interval=30,
                ping_timeout=10
            )
            
            self.state = ConnectionState.CONNECTED
            logger.info("ttyd WebSocket连接成功")
            
            # 启动消息监听
            self._should_stop = False
            self._listen_task = asyncio.create_task(self._listen_messages())
            
            # 发送初始化消息（双重认证的第二部分）
            await self._send_initialization()
            
            return True
            
        except Exception as e:
            self.state = ConnectionState.ERROR
            logger.error(f"连接ttyd失败: {e}")
            if self.error_handler:
                self.error_handler(e)
            return False
    
    async def _send_initialization(self):
        """发送初始化消息到ttyd"""
        try:
            # ttyd需要JSON初始化消息（双重认证的第二部分）
            init_data = {
                "AuthToken": self.auth_token,
                "columns": 80,
                "rows": 24
            }
            
            # 发送JSON初始化消息
            init_message = json.dumps(init_data)
            await self.websocket.send(init_message)
            logger.info("发送ttyd初始化消息成功")
            
        except Exception as e:
            logger.error(f"发送初始化消息失败: {e}")
            raise
    
    async def disconnect(self):
        """断开连接"""
        logger.info("断开ttyd连接")
        self._should_stop = True
        
        # 停止消息监听
        if self._listen_task and not self._listen_task.done():
            self._listen_task.cancel()
            try:
                await self._listen_task
            except asyncio.CancelledError:
                pass
        
        # 关闭WebSocket连接
        if self.websocket:
            try:
                # 兼容不同版本的websockets库
                if hasattr(self.websocket, 'close_code'):
                    # 新版本：检查close_code
                    if self.websocket.close_code is None:
                        await self.websocket.close()
                elif hasattr(self.websocket, 'closed'):
                    # 旧版本：检查closed属性
                    if not self.websocket.closed:
                        await self.websocket.close()
                else:
                    # 其他情况：直接尝试关闭
                    await self.websocket.close()
            except Exception as e:
                logger.warning(f"关闭WebSocket时出错: {e}")
        
        self.websocket = None
        self.state = ConnectionState.DISCONNECTED
        logger.info("ttyd连接已断开")
    
    async def send_command(self, command: str) -> bool:
        """发送命令到终端"""
        if not self.is_connected:
            logger.error("未连接到ttyd服务器")
            return False
        
        try:
            # 确保命令以换行符结尾
            if not command.endswith('\n'):
                command += '\n'
            
            # ttyd协议：INPUT命令 = '0' + 数据
            message = '0' + command
            await self.websocket.send(message)
            logger.debug(f"发送命令: {repr(command.strip())}")
            return True
            
        except Exception as e:
            logger.error(f"发送命令失败: {e}")
            if self.error_handler:
                self.error_handler(e)
            return False
    
    async def resize_terminal(self, rows: int, cols: int) -> bool:
        """调整终端大小"""
        if not self.is_connected:
            return False
            
        try:
            # ttyd协议：RESIZE_TERMINAL命令 = '1' + JSON数据
            resize_data = {
                "columns": cols,
                "rows": rows
            }
            message = '1' + json.dumps(resize_data)
            await self.websocket.send(message)
            logger.debug(f"调整终端大小: {rows}x{cols}")
            return True
            
        except Exception as e:
            logger.error(f"调整终端大小失败: {e}")
            return False
    
    async def _listen_messages(self):
        """监听WebSocket消息"""
        logger.info("开始监听ttyd消息")
        
        try:
            while not self._should_stop and self.websocket:
                try:
                    # 检查连接状态（兼容不同版本）
                    connection_alive = True
                    if hasattr(self.websocket, 'close_code'):
                        connection_alive = self.websocket.close_code is None
                    elif hasattr(self.websocket, 'closed'):
                        connection_alive = not self.websocket.closed
                    # 如果没有这些属性，假设连接正常
                    
                    if not connection_alive:
                        logger.warning("WebSocket连接已关闭")
                        break
                    
                    # 接收消息
                    message = await asyncio.wait_for(
                        self.websocket.recv(), 
                        timeout=1.0
                    )
                    
                    # 处理消息
                    await self._handle_message(message)
                    
                except asyncio.TimeoutError:
                    # 超时是正常的，继续监听
                    continue
                except websockets.exceptions.ConnectionClosed:
                    logger.warning("ttyd连接已关闭")
                    break
                except Exception as e:
                    logger.error(f"接收消息时出错: {e}")
                    if self.error_handler:
                        self.error_handler(e)
                    break
                    
        except Exception as e:
            logger.error(f"消息监听出错: {e}")
        finally:
            logger.info("停止监听ttyd消息")
            self.state = ConnectionState.DISCONNECTED
    
    async def _handle_message(self, message):
        """处理接收到的消息"""
        try:
            # 处理不同类型的消息
            if isinstance(message, bytes):
                # 二进制消息，解码为文本
                raw_data = message.decode('utf-8', errors='replace')
            else:
                # 文本消息
                raw_data = str(message)
            
            # 解析ttyd协议消息
            if len(raw_data) > 0:
                command = raw_data[0]
                data = raw_data[1:] if len(raw_data) > 1 else ""
                
                # 根据命令类型处理
                if command == '0':  # OUTPUT
                    # 终端输出 - 这是我们主要关心的
                    cleaned_data = self.ansi_cleaner.clean(data)
                    
                    # 只处理有意义的内容
                    if self.ansi_cleaner.is_meaningful(data):
                        if self.message_handler:
                            self.message_handler(cleaned_data)
                        else:
                            logger.debug(f"收到终端输出: {repr(cleaned_data[:100])}")
                            
                elif command == '1':  # SET_WINDOW_TITLE
                    logger.debug(f"收到窗口标题设置: {data}")
                elif command == '2':  # SET_PREFERENCES
                    logger.debug(f"收到偏好设置: {data}")
                else:
                    logger.debug(f"收到未知ttyd消息: {repr(raw_data[:100])}")
            
        except Exception as e:
            logger.error(f"处理消息时出错: {e}")
            if self.error_handler:
                self.error_handler(e)

    async def __aenter__(self):
        """异步上下文管理器入口"""
        await self.connect()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """异步上下文管理器出口"""
        await self.disconnect()
