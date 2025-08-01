"""Terminal API components - 简洁架构版本"""

from .terminal_api_client import TerminalAPIClient
from .websocket_client import TtydWebSocketClient

__all__ = [
    'TerminalAPIClient',     # 主要API接口
    'TtydWebSocketClient',   # WebSocket底层通信
]