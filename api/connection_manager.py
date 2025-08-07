#!/usr/bin/env python3
"""
Connection Manager
负责管理 WebSocket 连接的生命周期，包括初始化消息预消费
"""

import asyncio
import logging
from typing import Optional, Callable
from enum import Enum

from .websocket_client import TtydWebSocketClient

logger = logging.getLogger(__name__)


class ConnectionState(Enum):
    """连接状态"""
    DISCONNECTED = "disconnected"
    CONNECTING = "connecting"
    INITIALIZING = "initializing"
    CONNECTED = "connected"
    ERROR = "error"


class ConnectionManager:
    """连接管理器 - 负责 WebSocket 连接的生命周期和初始化消息预消费"""

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

        # 连接状态
        self.state = ConnectionState.DISCONNECTED

        # WebSocket客户端
        self._client = TtydWebSocketClient(
            host=host, port=port,
            username=username, password=password,
            use_ssl=use_ssl
        )

        # 回调函数
        self._user_message_handler: Optional[Callable[[str], None]] = None
        self._error_handler: Optional[Callable[[Exception], None]] = None

    def set_message_handler(self, handler: Callable[[str], None]):
        """设置用户消息处理器"""
        self._user_message_handler = handler

    def set_error_handler(self, handler: Callable[[Exception], None]):
        """设置错误处理器"""
        self._error_handler = handler
        self._client.set_error_handler(self._handle_error)

    def _handle_error(self, error: Exception):
        """内部错误处理"""
        logger.error(f"连接错误: {error}")
        self.state = ConnectionState.ERROR

        if self._error_handler:
            try:
                self._error_handler(error)
            except Exception as e:
                logger.error(f"错误处理器出错: {e}")

    @property
    def is_connected(self) -> bool:
        """检查连接状态"""
        if self._client is None:
            return False

        try:
            return self._client.is_connected and self.state == ConnectionState.CONNECTED
        except Exception as e:
            logger.debug(f"检查连接状态时出错: {e}")
            return False

    async def _drain_initialization_messages(self):
        """
        消费初始化消息直到流结束
        
        基于活跃性检测，只要有消息持续输出就继续等待，
        只有在完全静默时才认为初始化完成，不设置硬性时间限制
        """
        messages = []
        
        # 设置临时处理器收集消息
        def collector(msg):
            messages.append(msg)
        
        self._client.set_message_handler(collector)
        
        logger.info("开始消费初始化消息...")
        start_time = asyncio.get_event_loop().time()
        
        # 基于活跃性的初始化检测 - 只要有消息就继续等待
        last_count = 0
        last_progress_report = 0
        
        while True:
            await asyncio.sleep(self.silence_time)
            
            current_time = asyncio.get_event_loop().time()
            elapsed_time = current_time - start_time
            
            # 检查是否有新消息
            if len(messages) == last_count:
                # 没有新消息，初始化流结束
                logger.info(f"检测到 {self.silence_time}s 无新消息，初始化流结束")
                break
            
            # 定期报告初始化进度（每10秒报告一次，避免日志过多）
            if elapsed_time - last_progress_report >= 10.0:
                logger.info(f"初始化进行中... 已耗时 {elapsed_time:.1f}s，收到 {len(messages)} 条消息")
                last_progress_report = elapsed_time
            
            last_count = len(messages)
        
        total_time = asyncio.get_event_loop().time() - start_time
        logger.info(f"初始化完成: 丢弃 {len(messages)} 条消息，耗时 {total_time:.1f}s")

    async def connect(self) -> bool:
        """
        建立连接并处理初始化

        Returns:
            bool: 连接是否成功
        """
        logger.info(f"连接到ttyd服务器: {self.host}:{self.port}")

        try:
            self.state = ConnectionState.CONNECTING

            # 1. 建立 WebSocket 连接
            success = await self._client.connect()
            if not success:
                self.state = ConnectionState.ERROR
                logger.error("WebSocket 连接建立失败")
                return False

            logger.info("WebSocket 连接成功")
            
            # 2. 消费初始化消息直到流结束（基于活跃性检测，无时间限制）
            self.state = ConnectionState.INITIALIZING
            await self._drain_initialization_messages()

            # 3. 切换到用户消息处理
            if self._user_message_handler:
                self._client.set_message_handler(self._user_message_handler)
            
            self.state = ConnectionState.CONNECTED
            logger.info("连接完全建立，可以开始用户交互")
            return True

        except Exception as e:
            logger.error(f"连接时出错: {e}")
            self.state = ConnectionState.ERROR
            self._handle_error(e)
            return False

    async def disconnect(self):
        """断开连接"""
        logger.info("断开连接")

        try:
            if self._client:
                await self._client.disconnect()
        except Exception as e:
            logger.error(f"断开连接时出错: {e}")
        finally:
            self.state = ConnectionState.DISCONNECTED

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
            self._handle_error(e)
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
            self._handle_error(e)
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
            self._handle_error(e)
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
            'state': self.state.value,
            'is_connected': self.is_connected,
            'terminal_type': self.terminal_type
        }
