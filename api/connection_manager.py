#!/usr/bin/env python3
"""
连接管理器 - 处理连接重试、错误恢复和连接池管理
"""

import time
import threading
import logging
from typing import Dict, List, Optional, Callable
from dataclasses import dataclass, field
from enum import Enum
from .websocket_client import WebSocketClient, ConnectionState, WebSocketMessage

class HealthStatus(Enum):
    """健康状态枚举"""
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"

@dataclass
class ConnectionMetrics:
    """连接指标"""
    total_connections: int = 0
    successful_connections: int = 0
    failed_connections: int = 0
    reconnection_attempts: int = 0
    messages_sent: int = 0
    messages_received: int = 0
    last_connection_time: float = 0
    last_error_time: float = 0
    last_error: Optional[str] = None
    uptime_start: float = field(default_factory=time.time)
    
    @property
    def success_rate(self) -> float:
        """连接成功率"""
        if self.total_connections == 0:
            return 0.0
        return self.successful_connections / self.total_connections
    
    @property
    def uptime(self) -> float:
        """运行时间（秒）"""
        return time.time() - self.uptime_start

class ConnectionManager:
    """连接管理器 - 管理WebSocket连接的生命周期"""
    
    def __init__(self, base_url: str, username: str, password: str,
                 auto_reconnect: bool = True,
                 health_check_interval: float = 30.0,
                 max_connection_pool_size: int = 5):
        """
        初始化连接管理器
        
        Args:
            base_url: Gotty服务基础URL
            username: 认证用户名
            password: 认证密码
            auto_reconnect: 是否自动重连
            health_check_interval: 健康检查间隔（秒）
            max_connection_pool_size: 最大连接池大小
        """
        self.base_url = base_url
        self.username = username
        self.password = password
        self.auto_reconnect = auto_reconnect
        self.health_check_interval = health_check_interval
        self.max_connection_pool_size = max_connection_pool_size
        
        # 连接管理
        self.primary_client: Optional[WebSocketClient] = None
        self.connection_pool: List[WebSocketClient] = []
        self.connection_lock = threading.RLock()
        
        # 指标和监控
        self.metrics = ConnectionMetrics()
        self.health_status = HealthStatus.UNHEALTHY
        
        # 设置日志
        self.logger = logging.getLogger(__name__)
        
        # 回调函数
        self.connection_callbacks: List[Callable[[ConnectionState], None]] = []
        self.message_callbacks: List[Callable[[WebSocketMessage], None]] = []
        self.error_callbacks: List[Callable[[Exception], None]] = []
        
        # 监控线程
        self._monitor_thread: Optional[threading.Thread] = None
        self._stop_monitor = threading.Event()
        
        # 创建主连接
        self._create_primary_connection()
    
    def _create_primary_connection(self):
        """创建主连接"""
        self.primary_client = WebSocketClient(
            base_url=self.base_url,
            username=self.username,
            password=self.password,
            max_reconnect_attempts=5,
            reconnect_delay=2.0,
            connection_timeout=10.0,
            ping_interval=30.0
        )
        
        # 注册回调
        self.primary_client.add_state_callback(self._on_connection_state_change)
        self.primary_client.add_message_callback(self._on_message_received)
        self.primary_client.add_error_callback(self._on_error_occurred)
    
    def start(self) -> bool:
        """启动连接管理器"""
        with self.connection_lock:
            self.logger.info("启动连接管理器")
            
            # 启动主连接
            success = self._connect_primary()
            
            # 启动监控线程
            self._start_monitor_thread()
            
            return success
    
    def stop(self):
        """停止连接管理器"""
        with self.connection_lock:
            self.logger.info("停止连接管理器")
            
            # 停止监控线程
            self._stop_monitor_thread()
            
            # 关闭所有连接
            if self.primary_client:
                self.primary_client.disconnect()
            
            for client in self.connection_pool:
                client.disconnect()
            
            self.connection_pool.clear()
            self.health_status = HealthStatus.UNHEALTHY
    
    def _connect_primary(self) -> bool:
        """连接主客户端"""
        if not self.primary_client:
            self._create_primary_connection()
        
        self.metrics.total_connections += 1
        
        if self.primary_client.connect():
            self.metrics.successful_connections += 1
            self.metrics.last_connection_time = time.time()
            self.health_status = HealthStatus.HEALTHY
            self.logger.info("主连接建立成功")
            return True
        else:
            self.metrics.failed_connections += 1
            self.health_status = HealthStatus.UNHEALTHY
            self.logger.error("主连接建立失败")
            return False
    
    def get_client(self) -> Optional[WebSocketClient]:
        """获取可用的客户端连接"""
        with self.connection_lock:
            if self.primary_client and self.primary_client.is_connected():
                return self.primary_client
            
            # 尝试从连接池获取
            for client in self.connection_pool:
                if client.is_connected():
                    return client
            
            # 如果启用自动重连，尝试重新连接主客户端
            if self.auto_reconnect and self.primary_client:
                if self.primary_client.reconnect():
                    return self.primary_client
            
            return None
    
    def send_command(self, command: str) -> bool:
        """发送命令"""
        client = self.get_client()
        if client:
            success = client.send_command(command)
            if success:
                self.metrics.messages_sent += 1
            return success
        return False
    
    def send_input(self, input_data: str) -> bool:
        """发送输入"""
        client = self.get_client()
        if client:
            success = client.send_input(input_data)
            if success:
                self.metrics.messages_sent += 1
            return success
        return False
    
    def is_connected(self) -> bool:
        """检查是否有可用连接"""
        return self.get_client() is not None
    
    def get_health_status(self) -> HealthStatus:
        """获取健康状态"""
        return self.health_status
    
    def get_metrics(self) -> ConnectionMetrics:
        """获取连接指标"""
        return self.metrics
    
    def get_connection_info(self) -> Dict:
        """获取连接信息"""
        info = {
            "health_status": self.health_status.value,
            "metrics": {
                "total_connections": self.metrics.total_connections,
                "successful_connections": self.metrics.successful_connections,
                "failed_connections": self.metrics.failed_connections,
                "success_rate": self.metrics.success_rate,
                "messages_sent": self.metrics.messages_sent,
                "messages_received": self.metrics.messages_received,
                "uptime": self.metrics.uptime,
                "last_error": self.metrics.last_error
            },
            "primary_connection": None,
            "pool_connections": []
        }
        
        if self.primary_client:
            info["primary_connection"] = self.primary_client.get_connection_info()
        
        for i, client in enumerate(self.connection_pool):
            info["pool_connections"].append({
                "index": i,
                "info": client.get_connection_info()
            })
        
        return info
    
    def add_connection_callback(self, callback: Callable[[ConnectionState], None]):
        """添加连接状态回调"""
        self.connection_callbacks.append(callback)
    
    def add_message_callback(self, callback: Callable[[WebSocketMessage], None]):
        """添加消息回调"""
        self.message_callbacks.append(callback)
    
    def add_error_callback(self, callback: Callable[[Exception], None]):
        """添加错误回调"""
        self.error_callbacks.append(callback)
    
    def _on_connection_state_change(self, state: ConnectionState):
        """连接状态变化回调"""
        self.logger.info(f"连接状态变化: {state.value}")
        
        # 更新健康状态
        if state == ConnectionState.CONNECTED:
            self.health_status = HealthStatus.HEALTHY
        elif state == ConnectionState.RECONNECTING:
            self.health_status = HealthStatus.DEGRADED
            self.metrics.reconnection_attempts += 1
        elif state == ConnectionState.FAILED:
            self.health_status = HealthStatus.UNHEALTHY
        
        # 通知回调
        for callback in self.connection_callbacks:
            try:
                callback(state)
            except Exception as e:
                self.logger.error(f"连接状态回调执行失败: {e}")
    
    def _on_message_received(self, message: WebSocketMessage):
        """消息接收回调"""
        self.metrics.messages_received += 1
        
        # 通知回调
        for callback in self.message_callbacks:
            try:
                callback(message)
            except Exception as e:
                self.logger.error(f"消息回调执行失败: {e}")
    
    def _on_error_occurred(self, error: Exception):
        """错误发生回调"""
        self.metrics.last_error_time = time.time()
        self.metrics.last_error = str(error)
        
        # 通知回调
        for callback in self.error_callbacks:
            try:
                callback(error)
            except Exception as e:
                self.logger.error(f"错误回调执行失败: {e}")
    
    def _start_monitor_thread(self):
        """启动监控线程"""
        self._stop_monitor.clear()
        self._monitor_thread = threading.Thread(target=self._monitor_worker, daemon=True)
        self._monitor_thread.start()
    
    def _stop_monitor_thread(self):
        """停止监控线程"""
        self._stop_monitor.set()
        if self._monitor_thread and self._monitor_thread.is_alive():
            self._monitor_thread.join(timeout=2)
    
    def _monitor_worker(self):
        """监控工作线程"""
        while not self._stop_monitor.is_set():
            try:
                self._perform_health_check()
                time.sleep(self.health_check_interval)
            except Exception as e:
                self.logger.error(f"健康检查失败: {e}")
                time.sleep(5)  # 错误时短暂等待
    
    def _perform_health_check(self):
        """执行健康检查"""
        with self.connection_lock:
            # 检查主连接
            if self.primary_client:
                if not self.primary_client.is_connected():
                    self.logger.warning("主连接断开，尝试重连")
                    if self.auto_reconnect:
                        self.primary_client.reconnect()
            
            # 清理断开的连接池连接
            active_connections = []
            for client in self.connection_pool:
                if client.is_connected():
                    active_connections.append(client)
                else:
                    client.disconnect()
            
            self.connection_pool = active_connections
            
            # 更新健康状态
            if self.is_connected():
                if self.health_status == HealthStatus.UNHEALTHY:
                    self.health_status = HealthStatus.DEGRADED
            else:
                self.health_status = HealthStatus.UNHEALTHY
    
    def __enter__(self):
        """上下文管理器入口"""
        self.start()
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """上下文管理器出口"""
        self.stop()