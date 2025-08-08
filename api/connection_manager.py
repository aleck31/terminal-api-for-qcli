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

        # WebSocket客户端
        self._client = TtydWebSocketClient(
            host=host, port=port,
            username=username, password=password,
            use_ssl=use_ssl
        )

        # 设置协议状态变化回调
        self._client.set_state_change_handler(self._handle_protocol_state_change)

        # 回调函数
        self._user_message_handler: Optional[Callable[[str], None]] = None
        self._error_handler: Optional[Callable[[Exception], None]] = None

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

    def _handle_protocol_state_change(self, protocol_state: TtydProtocolState):
        """处理协议层状态变化"""
        logger.debug(f"收到协议状态变化: {protocol_state.value}")
        
        # 将协议状态映射为连接管理状态
        if protocol_state == TtydProtocolState.CONNECTING:
            # 协议层开始连接时，连接管理层可能已经是 CONNECTING 状态
            pass
        elif protocol_state == TtydProtocolState.AUTHENTICATING:
            # 认证阶段仍然是连接中
            if self._connection_state == ConnectionState.CONNECTING:
                pass  # 保持连接中状态
        elif protocol_state == TtydProtocolState.PROTOCOL_READY:
            # 协议就绪 = 连接成功
            if self._connection_state in [ConnectionState.CONNECTING, ConnectionState.RECONNECTING]:
                self._set_connection_state(ConnectionState.CONNECTED)
        elif protocol_state == TtydProtocolState.PROTOCOL_ERROR:
            # 协议错误 = 连接失败
            if self._connection_state == ConnectionState.RECONNECTING:
                self._set_connection_state(ConnectionState.FAILED)
            else:
                self._set_connection_state(ConnectionState.FAILED)
        elif protocol_state == TtydProtocolState.DISCONNECTED:
            # 协议断开 = 连接断开
            if self._connection_state == ConnectionState.DISCONNECTING:
                self._set_connection_state(ConnectionState.DISCONNECTED)
            else:
                # 意外断开
                self._set_connection_state(ConnectionState.DISCONNECTED)

    @property
    def is_connected(self) -> bool:
        """检查连接状态"""
        return (self._connection_state == ConnectionState.CONNECTED and 
                self._client.is_protocol_ready)

    def set_message_handler(self, handler: Callable[[str], None]):
        """设置用户消息处理器"""
        self._user_message_handler = handler
        # 同时设置到协议层
        self._client.set_message_handler(handler)

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
