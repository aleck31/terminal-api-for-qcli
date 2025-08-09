#!/usr/bin/env python3
"""
Connection Manager
负责管理 WebSocket 连接的生命周期
"""

import asyncio
import logging
from typing import Optional, Callable
from enum import Enum

from .websocket_client import TtydWebSocketClient, TtydProtocolState

logger = logging.getLogger(__name__)


class ConnectionState(Enum):
    """连接管理状态"""
    IDLE = "idle"                     # 空闲，未尝试连接
    CONNECTING = "connecting"         # 正在连接中
    CONNECTED = "connected"           # 已连接，可用
    RECONNECTING = "reconnecting"     # 重连中
    FAILED = "failed"                # 连接失败
    DISCONNECTING = "disconnecting"   # 正在断开
    DISCONNECTED = "disconnected"     # 已断开


class ConnectionManager:
    """连接管理器 - 负责 WebSocket 连接的生命周期"""

    def __init__(self, host: str = "localhost", port: int = 7681,
                 username: str = "demo", password: str = "password123",
                 use_ssl: bool = False, terminal_type: str = "bash",
                 silence_time: float = 3.0):
        """
        初始化连接管理器

        Args:
            host: ttyd服务器主机
            port: ttyd服务器端口
            username: 认证用户名
            password: 认证密码
            use_ssl: 是否使用SSL
            terminal_type: 终端类型 (bash, qcli, python)
            silence_time: 静默时间（秒）- 无新消息时认为初始化结束
        """
        self.host = host
        self.port = port
        self.username = username
        self.password = password
        self.use_ssl = use_ssl
        self.terminal_type = terminal_type
        self.silence_time = silence_time

        # 连接状态管理
        self._connection_state = ConnectionState.IDLE
        
        # 初始化协议状态到连接状态的映射表
        self._protocol_to_connection_map = {
            TtydProtocolState.PROTOCOL_READY: ConnectionState.CONNECTED,
            TtydProtocolState.PROTOCOL_ERROR: ConnectionState.FAILED
        }

        # WebSocket客户端
        self._client = TtydWebSocketClient(
            host=host, port=port,
            username=username, password=password,
            use_ssl=use_ssl
        )

        # 设置协议状态变化回调
        self._client.set_state_change_handler(self._handle_protocol_state_change)

        # 错误处理器
        self._error_handler: Optional[Callable[[Exception], None]] = None
        
        # 状态变化回调
        self._state_change_callback: Optional[Callable[[ConnectionState], None]] = None
        
        # 事件驱动消息处理
        self._message_listeners = []  # 临时监听器列表
        self._primary_handler = None   # 主要处理器
        
        # 事件驱动消息处理
        self._message_listeners = []  # 临时监听器列表
        self._primary_handler = None   # 主要处理器

    @property
    def state(self) -> ConnectionState:
        """获取连接管理状态"""
        return self._connection_state

    def _set_connection_state(self, new_state: ConnectionState):
        """设置连接状态"""
        if self._connection_state != new_state:
            old_state = self._connection_state
            self._connection_state = new_state
            logger.debug(f"连接状态变化: {old_state.value} -> {new_state.value}")
            
            # 通知上层状态变化
            if self._state_change_callback:
                try:
                    self._state_change_callback(new_state)
                except Exception as e:
                    logger.error(f"状态变化回调出错: {e}")

    def set_state_change_callback(self, callback: Callable[[ConnectionState], None]):
        """设置状态变化回调"""
        self._state_change_callback = callback

    def _handle_protocol_state_change(self, protocol_state: TtydProtocolState):
        """处理协议层状态变化"""
        logger.debug(f"收到协议状态变化: {protocol_state.value}")
        
        # 协议断开状态的特殊处理（区分正常断开和意外断开）
        if protocol_state == TtydProtocolState.DISCONNECTED:
            if self._connection_state == ConnectionState.DISCONNECTING:
                logger.info("连接正常断开")
            else:
                logger.warning(f"连接意外断开，当前状态: {self._connection_state.value}")
            self._set_connection_state(ConnectionState.DISCONNECTED)
            return
            
        # 对于连接和认证阶段，保持当前状态
        if protocol_state in [TtydProtocolState.CONNECTING, TtydProtocolState.AUTHENTICATING]:
            logger.debug(f"协议层{protocol_state.value}，保持连接层状态: {self._connection_state.value}")
            return
            
        # 使用映射表处理其他状态
        if protocol_state in self._protocol_to_connection_map:
            new_state = self._protocol_to_connection_map[protocol_state]
            logger.debug(f"协议层{protocol_state.value}，连接层状态从{self._connection_state.value}变为{new_state.value}")
            self._set_connection_state(new_state)
        else:
            logger.warning(f"未处理的协议状态: {protocol_state.value}")

    @property
    def is_connected(self) -> bool:
        """检查连接状态"""
        return (self._connection_state == ConnectionState.CONNECTED and 
                self._client.is_protocol_ready)

    def set_primary_handler(self, handler: Callable[[str], None]):
        """设置主要处理器（正常业务逻辑）"""
        self._primary_handler = handler
        # 设置消息分发器到协议层
        self._client.set_message_handler(self._dispatch_message)
        logger.debug("设置主要消息处理器")
    
    def add_temp_listener(self, listener: Callable[[str], None]) -> int:
        """添加临时监听器，返回监听器ID"""
        self._message_listeners.append(listener)
        listener_id = len(self._message_listeners) - 1
        logger.debug(f"添加临时监听器: ID={listener_id}")
        return listener_id
    
    def remove_temp_listener(self, listener_id: int):
        """移除临时监听器"""
        if 0 <= listener_id < len(self._message_listeners):
            self._message_listeners[listener_id] = None  # 标记为删除
            logger.debug(f"移除临时监听器: ID={listener_id}")
        else:
            logger.warning(f"无效的监听器ID: {listener_id}")
    
    def _dispatch_message(self, message: str):
        """分发消息给所有监听器和主处理器"""
        # 先给临时监听器（如初始化收集器）
        for i, listener in enumerate(self._message_listeners):
            if listener:  # 跳过已删除的
                try:
                    listener(message)
                except Exception as e:
                    logger.error(f"临时监听器 {i} 出错: {e}")
        
        # 再给主要处理器（如CommandExecutor）
        if self._primary_handler:
            try:
                self._primary_handler(message)
            except Exception as e:
                logger.error(f"主要处理器出错: {e}")

    def set_error_handler(self, handler: Callable[[Exception], None]):
        """设置错误处理器"""
        self._error_handler = handler
        self._client.set_error_handler(self._handle_protocol_error)

    def _handle_protocol_error(self, error: Exception):
        """处理协议层错误"""
        logger.error(f"协议层错误: {error}")

        if self._error_handler:
            try:
                self._error_handler(error)
            except Exception as e:
                logger.error(f"错误处理器出错: {e}")

    async def connect(self) -> bool:
        """
        建立连接
        
        Returns:
            bool: 连接是否成功
        """
        if self.is_connected:
            logger.warning("已经连接")
            return True

        logger.info(f"连接到ttyd服务器: {self.host}:{self.port}")
        
        try:
            self._set_connection_state(ConnectionState.CONNECTING)
            
            # 委托给协议层建立连接
            success = await self._client.connect()
            
            if success:
                # 状态变化会通过回调自动更新
                logger.info("连接建立成功")
                return True
            else:
                self._set_connection_state(ConnectionState.FAILED)
                logger.error("连接建立失败")
                return False

        except Exception as e:
            logger.error(f"连接时出错: {e}")
            self._set_connection_state(ConnectionState.FAILED)
            self._handle_protocol_error(e)
            return False

    async def disconnect(self):
        """断开连接"""
        logger.info("断开连接")
        
        try:
            self._set_connection_state(ConnectionState.DISCONNECTING)
            await self._client.disconnect()
            # 状态变化会通过回调自动更新为 DISCONNECTED
        except Exception as e:
            logger.error(f"断开连接时出错: {e}")
            self._set_connection_state(ConnectionState.DISCONNECTED)

    async def send_input(self, data: str) -> bool:
        """
        发送输入数据

        Args:
            data: 要发送的数据

        Returns:
            bool: 发送是否成功
        """
        if not self.is_connected:
            logger.error("连接未建立，无法发送数据")
            return False

        try:
            return await self._client.send_input(data)
        except Exception as e:
            logger.error(f"发送数据时出错: {e}")
            self._handle_protocol_error(e)
            return False

    async def send_command(self, command: str) -> bool:
        """
        发送命令

        Args:
            command: 要发送的命令

        Returns:
            bool: 发送是否成功
        """
        if not self.is_connected:
            logger.error("连接未建立，无法发送命令")
            return False

        try:
            return await self._client.send_command(command, self.terminal_type)
        except Exception as e:
            logger.error(f"发送命令时出错: {e}")
            self._handle_protocol_error(e)
            return False

    async def resize_terminal(self, rows: int, cols: int) -> bool:
        """
        调整终端大小

        Args:
            rows: 行数
            cols: 列数

        Returns:
            bool: 调整是否成功
        """
        if not self.is_connected:
            logger.error("连接未建立，无法调整终端大小")
            return False

        try:
            return await self._client.resize_terminal(rows, cols)
        except Exception as e:
            logger.error(f"调整终端大小时出错: {e}")
            self._handle_protocol_error(e)
            return False

    def get_connection_info(self) -> dict:
        """
        获取连接信息

        Returns:
            dict: 连接信息
        """
        return {
            'host': self.host,
            'port': self.port,
            'use_ssl': self.use_ssl,
            'connection_state': self._connection_state.value,
            'protocol_state': self._client.protocol_state.value,
            'is_connected': self.is_connected,
            'terminal_type': self.terminal_type
        }
