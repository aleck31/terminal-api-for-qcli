#!/usr/bin/env python3
"""
增强的WebSocket客户端 - 支持重试、错误恢复和安全连接
"""

import websocket
import json
import base64
import logging
import time
import threading
import ssl
from typing import Optional, Callable, Dict, Any, List, Generator
from urllib.parse import urlparse
from dataclasses import dataclass
from enum import Enum
import queue

class ConnectionState(Enum):
    """连接状态枚举"""
    DISCONNECTED = "disconnected"
    CONNECTING = "connecting"
    CONNECTED = "connected"
    RECONNECTING = "reconnecting"
    FAILED = "failed"

@dataclass
class WebSocketMessage:
    """WebSocket消息数据结构"""
    type: str
    data: str
    timestamp: float
    raw_message: str

class MessageSerializer:
    """消息序列化和反序列化器"""
    
    @staticmethod
    def serialize_command(command: str) -> str:
        """序列化命令为Gotty格式"""
        # Gotty使用特殊格式：'0' + 命令内容
        return "0" + command + "\n"
    
    @staticmethod
    def serialize_input(input_data: str) -> str:
        """序列化输入数据"""
        return "0" + input_data
    
    @staticmethod
    def deserialize_message(raw_message: str) -> WebSocketMessage:
        """反序列化WebSocket消息"""
        timestamp = time.time()
        
        if not raw_message:
            return WebSocketMessage("empty", "", timestamp, raw_message)
        
        # 处理Gotty消息格式
        if isinstance(raw_message, str) and len(raw_message) > 0:
            msg_type_char = raw_message[0]
            data = raw_message[1:] if len(raw_message) > 1 else ""
        elif isinstance(raw_message, bytes):
            # 处理二进制消息
            try:
                raw_message = raw_message.decode('utf-8')
                if len(raw_message) > 0:
                    msg_type_char = raw_message[0]
                    data = raw_message[1:] if len(raw_message) > 1 else ""
                else:
                    return WebSocketMessage("empty", "", timestamp, str(raw_message))
            except UnicodeDecodeError:
                return WebSocketMessage("binary", str(raw_message), timestamp, str(raw_message))
        else:
            return WebSocketMessage("unknown", str(raw_message), timestamp, str(raw_message))
        
        # 根据Gotty协议处理不同类型的消息
        if msg_type_char == '0':
            # 用户输入数据
            return WebSocketMessage("input", data, timestamp, raw_message)
        
        elif msg_type_char == '1':
            # 终端输出数据（base64编码）
            try:
                decoded_data = base64.b64decode(data).decode('utf-8')
                return WebSocketMessage("output", decoded_data, timestamp, raw_message)
            except Exception:
                return WebSocketMessage("output", data, timestamp, raw_message)
        
        elif msg_type_char == '2':
            return WebSocketMessage("title", data, timestamp, raw_message)
        elif msg_type_char == '3':
            return WebSocketMessage("preferences", data, timestamp, raw_message)
        elif msg_type_char == '4':
            return WebSocketMessage("reconnect", data, timestamp, raw_message)
        
        # 尝试直接解码base64
        try:
            decoded_data = base64.b64decode(raw_message).decode('utf-8')
            return WebSocketMessage("output", decoded_data, timestamp, raw_message)
        except Exception:
            pass
        
        # 尝试解析JSON
        try:
            json_data = json.loads(raw_message)
            return WebSocketMessage("json", json_data, timestamp, raw_message)
        except json.JSONDecodeError:
            pass
        
        # 默认作为原始文本处理
        return WebSocketMessage("raw", raw_message, timestamp, raw_message)

class WebSocketClient:
    """增强的WebSocket客户端"""
    
    def __init__(self, base_url: str, username: str, password: str, 
                 max_reconnect_attempts: int = 5, 
                 reconnect_delay: float = 2.0,
                 connection_timeout: float = 10.0,
                 ping_interval: float = 30.0):
        """
        初始化WebSocket客户端
        
        Args:
            base_url: Gotty服务基础URL
            username: 认证用户名
            password: 认证密码
            max_reconnect_attempts: 最大重连次数
            reconnect_delay: 重连延迟（秒）
            connection_timeout: 连接超时（秒）
            ping_interval: ping间隔（秒）
        """
        self.base_url = base_url
        self.username = username
        self.password = password
        self.max_reconnect_attempts = max_reconnect_attempts
        self.reconnect_delay = reconnect_delay
        self.connection_timeout = connection_timeout
        self.ping_interval = ping_interval
        
        # 连接状态管理
        self.ws: Optional[websocket.WebSocket] = None
        self.state = ConnectionState.DISCONNECTED
        self.reconnect_attempts = 0
        self.last_ping_time = 0
        self.connection_lock = threading.Lock()
        
        # 消息处理
        self.serializer = MessageSerializer()
        self.message_queue = queue.Queue()
        self.fragment_buffer: List[str] = []
        self.max_buffer_size = 100000  # 100KB限制
        
        # 设置日志
        self.logger = logging.getLogger(__name__)
        self.logger.setLevel(logging.INFO)
        
        # WebSocket URL和认证
        self._setup_connection_params()
        
        # 回调函数
        self.message_callbacks: List[Callable[[WebSocketMessage], None]] = []
        self.error_callbacks: List[Callable[[Exception], None]] = []
        self.state_callbacks: List[Callable[[ConnectionState], None]] = []
        
        # 心跳和监控线程
        self._heartbeat_thread: Optional[threading.Thread] = None
        self._message_thread: Optional[threading.Thread] = None
        self._stop_threads = threading.Event()
    
    def _setup_connection_params(self):
        """设置连接参数"""
        parsed_url = urlparse(self.base_url)
        
        # 确定WebSocket协议
        if parsed_url.scheme == "https":
            ws_scheme = "wss"
        else:
            ws_scheme = "ws"
        
        self.ws_url = f"{ws_scheme}://{parsed_url.netloc}/ws"
        
        # 设置认证头
        credentials = base64.b64encode(f"{self.username}:{self.password}".encode()).decode()
        self.headers = [
            f'Authorization: Basic {credentials}',
            'User-Agent: Terminal-API-Client/2.0'
        ]
        
        # SSL配置（用于wss连接）
        self.ssl_options = {
            'cert_reqs': ssl.CERT_NONE,  # 开发环境可以忽略证书验证
            'check_hostname': False
        } if ws_scheme == "wss" else None
    
    def add_message_callback(self, callback: Callable[[WebSocketMessage], None]):
        """添加消息回调"""
        self.message_callbacks.append(callback)
    
    def add_error_callback(self, callback: Callable[[Exception], None]):
        """添加错误回调"""
        self.error_callbacks.append(callback)
    
    def add_state_callback(self, callback: Callable[[ConnectionState], None]):
        """添加状态变化回调"""
        self.state_callbacks.append(callback)
    
    def _set_state(self, new_state: ConnectionState):
        """设置连接状态并触发回调"""
        if self.state != new_state:
            old_state = self.state
            self.state = new_state
            self.logger.info(f"连接状态变化: {old_state.value} -> {new_state.value}")
            
            for callback in self.state_callbacks:
                try:
                    callback(new_state)
                except Exception as e:
                    self.logger.error(f"状态回调执行失败: {e}")
    
    def _notify_error(self, error: Exception):
        """通知错误"""
        self.logger.error(f"WebSocket错误: {error}")
        for callback in self.error_callbacks:
            try:
                callback(error)
            except Exception as e:
                self.logger.error(f"错误回调执行失败: {e}")
    
    def _notify_message(self, message: WebSocketMessage):
        """通知消息"""
        for callback in self.message_callbacks:
            try:
                callback(message)
            except Exception as e:
                self.logger.error(f"消息回调执行失败: {e}")
    
    def connect(self) -> bool:
        """建立WebSocket连接"""
        with self.connection_lock:
            if self.state == ConnectionState.CONNECTED:
                self.logger.warning("已经连接，跳过重复连接")
                return True
            
            self._set_state(ConnectionState.CONNECTING)
            
            try:
                self.logger.info(f"正在连接到 {self.ws_url}")
                
                # 创建WebSocket连接
                self.ws = websocket.WebSocket(sslopt=self.ssl_options)
                self.ws.settimeout(self.connection_timeout)
                
                # 连接到WebSocket
                self.ws.connect(self.ws_url, header=self.headers)
                
                # 发送Gotty认证消息
                auth_message = {
                    "Arguments": "",
                    "AuthToken": f"{self.username}:{self.password}"
                }
                self.ws.send(json.dumps(auth_message))
                
                self._set_state(ConnectionState.CONNECTED)
                self.reconnect_attempts = 0
                
                # 启动后台线程
                self._start_background_threads()
                
                self.logger.info("WebSocket连接和认证成功")
                return True
                
            except Exception as e:
                self._set_state(ConnectionState.FAILED)
                self._notify_error(e)
                return False
    
    def disconnect(self):
        """关闭WebSocket连接"""
        with self.connection_lock:
            self._set_state(ConnectionState.DISCONNECTED)
            self._stop_background_threads()
            
            if self.ws:
                try:
                    self.ws.close()
                    self.logger.info("WebSocket连接已关闭")
                except Exception as e:
                    self.logger.error(f"关闭WebSocket连接时出错: {e}")
                finally:
                    self.ws = None
    
    def reconnect(self) -> bool:
        """重新连接WebSocket"""
        if self.reconnect_attempts >= self.max_reconnect_attempts:
            self.logger.error(f"重连次数已达上限 ({self.max_reconnect_attempts})")
            self._set_state(ConnectionState.FAILED)
            return False
        
        self.reconnect_attempts += 1
        self._set_state(ConnectionState.RECONNECTING)
        self.logger.info(f"尝试重连 (第 {self.reconnect_attempts} 次)")
        
        # 先关闭现有连接
        self.disconnect()
        
        # 指数退避延迟
        delay = self.reconnect_delay * (2 ** (self.reconnect_attempts - 1))
        time.sleep(min(delay, 30))  # 最大延迟30秒
        
        return self.connect()
    
    def send_command(self, command: str) -> bool:
        """发送命令到终端"""
        if not self.is_connected():
            self.logger.error("WebSocket未连接，无法发送命令")
            return False
        
        try:
            message = self.serializer.serialize_command(command)
            self.ws.send(message)
            self.logger.debug(f"发送命令: {repr(message)}")
            return True
        except Exception as e:
            self.logger.error(f"发送命令失败: {e}")
            self._notify_error(e)
            return False
    
    def send_input(self, input_data: str) -> bool:
        """发送输入数据"""
        if not self.is_connected():
            self.logger.error("WebSocket未连接，无法发送输入")
            return False
        
        try:
            message = self.serializer.serialize_input(input_data)
            self.ws.send(message)
            self.logger.debug(f"发送输入: {repr(message)}")
            return True
        except Exception as e:
            self.logger.error(f"发送输入失败: {e}")
            self._notify_error(e)
            return False
    
    def receive_message(self, timeout: float = 1.0) -> Optional[WebSocketMessage]:
        """接收WebSocket消息"""
        if not self.is_connected():
            return None
        
        try:
            self.ws.settimeout(timeout)
            raw_message = self.ws.recv()
            
            if raw_message:
                message = self.serializer.deserialize_message(raw_message)
                self.logger.debug(f"接收消息: {message.type} - {repr(message.data[:100])}")
                return message
            
        except websocket.WebSocketTimeoutException:
            # 超时是正常的
            return None
        except websocket.WebSocketConnectionClosedException:
            self.logger.warning("WebSocket连接已关闭")
            self._set_state(ConnectionState.DISCONNECTED)
            return None
        except Exception as e:
            self.logger.error(f"接收消息失败: {e}")
            self._notify_error(e)
            return None
    
    def is_connected(self) -> bool:
        """检查连接状态"""
        return self.state == ConnectionState.CONNECTED and self.ws is not None
    
    def get_connection_info(self) -> Dict[str, Any]:
        """获取连接信息"""
        return {
            "url": self.ws_url,
            "state": self.state.value,
            "reconnect_attempts": self.reconnect_attempts,
            "max_reconnect_attempts": self.max_reconnect_attempts,
            "username": self.username,
            "last_ping": self.last_ping_time
        }
    
    def _start_background_threads(self):
        """启动后台线程"""
        self._stop_threads.clear()
        
        # 启动心跳线程
        if self.ping_interval > 0:
            self._heartbeat_thread = threading.Thread(target=self._heartbeat_worker, daemon=True)
            self._heartbeat_thread.start()
        
        # 启动消息处理线程
        self._message_thread = threading.Thread(target=self._message_worker, daemon=True)
        self._message_thread.start()
    
    def _stop_background_threads(self):
        """停止后台线程"""
        self._stop_threads.set()
        
        if self._heartbeat_thread and self._heartbeat_thread.is_alive():
            self._heartbeat_thread.join(timeout=1)
        
        if self._message_thread and self._message_thread.is_alive():
            self._message_thread.join(timeout=1)
    
    def _heartbeat_worker(self):
        """心跳工作线程"""
        while not self._stop_threads.is_set():
            try:
                if self.is_connected():
                    current_time = time.time()
                    if current_time - self.last_ping_time > self.ping_interval:
                        self.ws.ping()
                        self.last_ping_time = current_time
                        self.logger.debug("发送心跳ping")
                
                time.sleep(5)  # 每5秒检查一次
                
            except Exception as e:
                self.logger.error(f"心跳线程错误: {e}")
                self._notify_error(e)
                break
    
    def _message_worker(self):
        """消息处理工作线程"""
        while not self._stop_threads.is_set():
            try:
                if self.is_connected():
                    message = self.receive_message(timeout=1.0)
                    if message:
                        self._notify_message(message)
                else:
                    time.sleep(0.1)
                    
            except Exception as e:
                self.logger.error(f"消息处理线程错误: {e}")
                self._notify_error(e)
                break
    
    def __enter__(self):
        """上下文管理器入口"""
        self.connect()
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """上下文管理器出口"""
        self.disconnect()