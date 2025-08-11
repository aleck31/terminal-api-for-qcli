#!/usr/bin/env python3
"""
ttyd WebSocket客户端
"""

import asyncio
import websockets
from websockets import ClientConnection
from websockets.protocol import State
import base64
import json
import logging
from typing import Optional, Callable
from dataclasses import dataclass
from enum import Enum

logger = logging.getLogger(__name__)


class TtydProtocolState(Enum):
    """ttyd 协议状态"""
    DISCONNECTED = "disconnected"     # 未连接
    CONNECTING = "connecting"         # 正在建立 WebSocket 连接
    AUTHENTICATING = "authenticating" # 正在进行 ttyd 认证
    PROTOCOL_READY = "protocol_ready" # ttyd 协议就绪，可以收发消息
    PROTOCOL_ERROR = "protocol_error" # 协议层错误


@dataclass
class TtydMessage:
    """ttyd消息"""
    data: str
    timestamp: float
    message_type: str = "output"


class TtydWebSocketClient:
    """ttyd WebSocket 客户端 - 专注协议实现"""

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
        self.ws_connection: Optional[ClientConnection] = None
        self._protocol_state = TtydProtocolState.DISCONNECTED

        # 回调处理器
        self.message_handler: Optional[Callable[[str], None]] = None
        self.error_handler: Optional[Callable[[Exception], None]] = None
        self.state_change_handler: Optional[Callable[[TtydProtocolState], None]] = None

        # 内部状态
        self._listen_task: Optional[asyncio.Task] = None
        self._should_stop = False

        # 认证令牌
        self.auth_token = base64.b64encode(
            f"{username}:{password}".encode()).decode()

    @property
    def protocol_state(self) -> TtydProtocolState:
        """获取协议状态（只读）"""
        return self._protocol_state

    def _set_protocol_state(self, new_state: TtydProtocolState):
        """设置协议状态并通知上层"""
        if self._protocol_state != new_state:
            old_state = self._protocol_state
            self._protocol_state = new_state
            logger.debug(f"协议状态变化: {old_state.value} -> {new_state.value}")
            
            # 通知上层状态变化
            if self.state_change_handler:
                try:
                    self.state_change_handler(new_state)
                except Exception as e:
                    logger.error(f"状态变化回调出错: {e}")

    @property
    def url(self) -> str:
        """获取WebSocket URL"""
        protocol = "wss" if self.use_ssl else "ws"
        return f"{protocol}://{self.host}:{self.port}/ws"

    @property
    def is_protocol_ready(self) -> bool:
        """检查协议是否就绪"""
        return (self.ws_connection is not None and 
                self._protocol_state == TtydProtocolState.PROTOCOL_READY and
                self._is_websocket_alive())

    def _is_websocket_alive(self) -> bool:
        """检查底层WebSocket连接是否存活"""
        if self.ws_connection is None:
            return False
        
        try:
            # 使用 websockets (15.x) state检查
            return self.ws_connection.state == State.OPEN
        except Exception:
            return False

    def set_message_handler(self, handler: Callable[[str], None]):
        """设置消息处理器"""
        self.message_handler = handler

    def set_error_handler(self, handler: Callable[[Exception], None]):
        """设置错误处理器"""
        self.error_handler = handler

    def set_state_change_handler(self, handler: Callable[[TtydProtocolState], None]):
        """设置状态变化处理器"""
        self.state_change_handler = handler

    async def connect(self) -> bool:
        """连接到ttyd服务器"""
        if self.is_protocol_ready:
            logger.warning("协议已就绪")
            return True

        try:
            self._set_protocol_state(TtydProtocolState.CONNECTING)
            logger.info(f"连接到ttyd服务器: {self.url}")

            # WebSocket握手时提供HTTP基本认证头
            self.ws_connection = await websockets.connect(
                self.url,
                subprotocols=['tty'],  # type: ignore
                additional_headers={
                    "Authorization": f"Basic {self.auth_token}"
                },
                ping_interval=None,  # 禁用客户端心跳
                ping_timeout=None    # 禁用心跳超时
            )

            logger.info("WebSocket连接成功，开始认证")
            self._set_protocol_state(TtydProtocolState.AUTHENTICATING)

            # 启动消息监听
            self._should_stop = False
            self._listen_task = asyncio.create_task(self._listen_messages())

            # 发送初始化消息（ttyd认证）
            await self._send_initialization()
            
            # 认证完成，协议就绪
            self._set_protocol_state(TtydProtocolState.PROTOCOL_READY)
            logger.info("ttyd协议就绪")

            return True

        except Exception as e:
            self._set_protocol_state(TtydProtocolState.PROTOCOL_ERROR)
            logger.error(f"连接ttyd失败: {e}")
            if self.error_handler:
                self.error_handler(e)
            return False

    async def _send_initialization(self):
        """发送初始化消息到ttyd"""
        try:
            # JSON初始化消息（ttyd双重认证的第二部分）
            init_data = {
                "columns": 240, # 默认 80
                "rows": 60, # 默认 24
                "AuthToken": self.auth_token
            }

            # 发送JSON初始化消息
            init_message = json.dumps(init_data)
            await self.ws_connection.send(init_message)  # type: ignore
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
        if self.ws_connection:
            try:
                if self._is_websocket_alive():
                    await self.ws_connection.close()
            except Exception as e:
                logger.warning(f"关闭WebSocket时出错: {e}")

        self.ws_connection = None
        self._set_protocol_state(TtydProtocolState.DISCONNECTED)
        logger.info("ttyd连接已断开")

    async def send_command(self, command: str, terminal_type: str = "bash") -> bool:
        """发送命令到终端"""
        if not self.is_protocol_ready:
            logger.error("协议未就绪，无法发送命令")
            return False

        try:
            # 根据终端类型选择合适的行结束符
            if terminal_type.lower() == "qcli":
                # Q CLI 需要 \r 结尾
                if not command.endswith('\r'):
                    command += '\r'
            else:
                # 其他终端使用 \n 结尾
                if not command.endswith('\n'):
                    command += '\n'

            # ttyd协议：INPUT命令 = '0' + 数据
            message = '0' + command
            await self.ws_connection.send(message)  # type: ignore
            logger.debug(f"发送命令 ({terminal_type}): {repr(command.strip())}")
            return True

        except Exception as e:
            logger.error(f"发送命令失败: {e}")
            self._set_protocol_state(TtydProtocolState.PROTOCOL_ERROR)
            if self.error_handler:
                self.error_handler(e)
            return False

    async def send_input(self, data: str) -> bool:
        """发送输入数据"""
        if not self.is_protocol_ready:
            logger.error("协议未就绪，无法发送数据")
            return False

        try:
            # ttyd协议：INPUT命令 = '0' + 数据
            message = '0' + data
            await self.ws_connection.send(message)  # type: ignore
            logger.debug(f"发送输入: {repr(data)}")
            return True

        except Exception as e:
            logger.error(f"发送输入失败: {e}")
            self._set_protocol_state(TtydProtocolState.PROTOCOL_ERROR)
            if self.error_handler:
                self.error_handler(e)
            return False

    async def resize_terminal(self, rows: int, cols: int) -> bool:
        """调整终端大小"""
        if not self.is_protocol_ready:
            logger.error("协议未就绪，无法调整终端大小")
            return False

        try:
            # ttyd协议：RESIZE_TERMINAL命令 = '1' + JSON数据
            resize_data = {
                "columns": cols,
                "rows": rows
            }
            message = '1' + json.dumps(resize_data)
            await self.ws_connection.send(message)  # type: ignore
            logger.debug(f"调整终端大小: {rows}x{cols}")
            return True

        except Exception as e:
            logger.error(f"调整终端大小失败: {e}")
            self._set_protocol_state(TtydProtocolState.PROTOCOL_ERROR)
            return False

    async def _listen_messages(self):
        """监听WebSocket消息"""
        logger.info("开始监听ttyd消息")

        try:
            while not self._should_stop and self.ws_connection:
                try:
                    # 检查连接状态
                    if not self._is_websocket_alive():
                        logger.warning("WebSocket连接已关闭")
                        break

                    # 接收消息
                    message = await asyncio.wait_for(
                        self.ws_connection.recv(),
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
                    self._set_protocol_state(TtydProtocolState.PROTOCOL_ERROR)
                    if self.error_handler:
                        self.error_handler(e)
                    break

        except Exception as e:
            logger.error(f"消息监听出错: {e}")
            self._set_protocol_state(TtydProtocolState.PROTOCOL_ERROR)
        finally:
            logger.info("停止监听ttyd消息")
            if self._protocol_state != TtydProtocolState.DISCONNECTED:
                self._set_protocol_state(TtydProtocolState.DISCONNECTED)

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
                    # 终端输出
                    if self.message_handler:
                        self.message_handler(data)
                    else:
                        logger.debug(f"收到终端输出: {repr(data[:50])}")

                elif command == '1':  # SET_WINDOW_TITLE
                    logger.debug(f"收到窗口标题设置: {data}")
                elif command == '2':  # SET_PREFERENCES
                    logger.debug(f"收到偏好设置: {data}")
                else:
                    logger.debug(f"收到未知ttyd消息: {repr(raw_data[:100])}")

        except Exception as e:
            logger.error(f"处理消息时出错: {e}")
            self._set_protocol_state(TtydProtocolState.PROTOCOL_ERROR)
            if self.error_handler:
                self.error_handler(e)

    async def __aenter__(self):
        """异步上下文管理器入口"""
        await self.connect()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """异步上下文管理器出口"""
        await self.disconnect()
