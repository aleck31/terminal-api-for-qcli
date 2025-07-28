#!/usr/bin/env python3
"""
终端API客户端 - 提供与Gotty服务交互的高级接口
"""

import requests
import base64
import logging
import time
from typing import Generator, Tuple, Dict, Any, Optional
from .websocket_handler import WebSocketHandler
from .message_processor import MessageProcessor

class TerminalAPIClient:
    """终端API客户端 - 封装与Gotty WebSocket API的通信逻辑"""
    
    def __init__(self, base_url: str = "http://localhost:8080", 
                 username: str = "demo", password: str = "password123"):
        self.base_url = base_url
        self.username = username
        self.password = password
        
        # 初始化组件
        self.ws_handler = WebSocketHandler(base_url, username, password)
        self.message_processor = MessageProcessor()
        
        # HTTP会话
        self.session = requests.Session()
        credentials = base64.b64encode(f"{username}:{password}".encode()).decode()
        self.session.headers.update({
            'Authorization': f'Basic {credentials}',
            'User-Agent': 'Terminal-API-Client/1.0'
        })
        
        # 设置日志
        self.logger = logging.getLogger(__name__)
    
    def test_connection(self) -> bool:
        """测试HTTP连接"""
        try:
            response = self.session.get(self.base_url, timeout=5)
            return response.status_code == 200
        except Exception as e:
            self.logger.error(f"HTTP连接测试失败: {e}")
            return False
    
    def test_websocket_connection(self) -> bool:
        """测试WebSocket连接"""
        try:
            if self.ws_handler.connect():
                self.ws_handler.disconnect()
                return True
            return False
        except Exception as e:
            self.logger.error(f"WebSocket连接测试失败: {e}")
            return False
    
    def execute_command(self, command: str, timeout: float = 30.0) -> Generator[Tuple[str, str, Dict[str, Any]], None, None]:
        """
        执行命令并流式返回结果
        
        Args:
            command: 要执行的命令
            timeout: 命令执行超时时间（秒）
            
        Yields:
            Tuple[str, str, Dict[str, Any]]: (output_type, content, metadata)
        """
        # 开始命令执行
        output_type, content, metadata = self.message_processor.start_command_execution(command)
        if output_type == "error":
            yield (output_type, content, metadata)
            return
        
        # 发送开始执行状态
        yield (output_type, content, metadata)
        
        # 建立WebSocket连接
        if not self.ws_handler.connect():
            yield ("error", "无法建立WebSocket连接", {"title": "🔌 连接错误"})
            return
        
        try:
            # 发送命令
            if not self.ws_handler.send_command(command):
                yield ("error", "发送命令失败", {"title": "📤 发送错误"})
                return
            
            # 接收响应
            start_time = time.time()
            last_activity = start_time
            no_output_timeout = 5.0  # 5秒无输出则认为命令可能已完成
            
            while time.time() - start_time < timeout:
                message = self.ws_handler.receive_message(timeout=1.0)
                
                if message is None:
                    # 检查是否超时无输出
                    if time.time() - last_activity > no_output_timeout:
                        self.logger.info("命令执行可能已完成（无新输出）")
                        break
                    continue
                
                # 更新最后活动时间
                last_activity = time.time()
                
                # 处理消息
                result = self.message_processor.process_websocket_message(message)
                if result:
                    output_type, content, metadata = result
                    yield (output_type, content, metadata)
                
                # 检查是否收到命令完成信号
                if self._is_command_complete(message):
                    break
            
            # 生成执行摘要
            summary_type, summary_data, summary_metadata = self.message_processor.finish_command_execution()
            yield (summary_type, summary_data, summary_metadata)
            
        except Exception as e:
            self.logger.error(f"命令执行过程中出错: {e}")
            yield ("error", f"执行错误: {str(e)}", {"title": "❌ 执行异常"})
            
        finally:
            # 关闭WebSocket连接
            self.ws_handler.disconnect()
    
    def _is_command_complete(self, message: Dict[str, Any]) -> bool:
        """
        判断命令是否执行完成
        这是一个简单的启发式方法，可以根据实际情况调整
        """
        data = message.get("data", "")
        
        # 检查是否包含命令提示符（简单判断）
        if any(prompt in data for prompt in ["$ ", "# ", "> ", ">>> "]):
            return True
        
        # 检查是否包含命令完成的标志
        if "command not found" in data.lower():
            return True
            
        return False
    
    def get_connection_status(self) -> Dict[str, Any]:
        """获取连接状态信息"""
        return {
            "http_connected": self.test_connection(),
            "websocket_connected": self.ws_handler.is_connected(),
            "base_url": self.base_url,
            "username": self.username
        }
    
    def close(self):
        """关闭客户端连接"""
        self.ws_handler.disconnect()
        if hasattr(self.session, 'close'):
            self.session.close()