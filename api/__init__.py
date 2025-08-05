"""Terminal API components"""

from .terminal_api_client import TerminalAPIClient, TerminalType
from .websocket_client import TtydWebSocketClient

__all__ = [
    'TerminalAPIClient',     # 主要API接口
    'TtydWebSocketClient',   # WebSocket底层通信
    'TerminalType',          # 终端类型枚举
]