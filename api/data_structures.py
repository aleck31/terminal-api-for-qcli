#!/usr/bin/env python3
"""
统一数据流架构的核心数据结构
定义 StreamChunk、ChunkType、TerminalType 和 MetadataBuilder
"""

import time
from dataclasses import dataclass
from enum import Enum
from typing import Dict, Any


class TerminalType(Enum):
    """终端类型 - 统一定义"""
    GENERIC = "generic"
    QCLI = "qcli"


class ChunkType(Enum):
    """统一的数据块类型 - 语义明确，调用方可根据类型决定展示策略"""
    THINKING = "thinking"      # AI思考中 - 通常显示思考指示器
    TOOL_USE = "tool_use"      # 工具使用 - 可显示工具信息
    CONTENT = "content"        # 文本内容输出 - 应该显示给用户
    PENDING = "pending"        # 等待输入 - 可显示等待提示
    COMPLETE = "complete"      # 完成 - 可显示完成信息
    ERROR = "error"           # 错误 - 应该显示错误信息


@dataclass
class StreamChunk:
    """统一的流式数据块"""
    content: str                    # 处理后的内容
    type: ChunkType                # 数据块类型
    metadata: Dict[str, Any]       # 元数据
    timestamp: float               # 时间戳
    
    def to_api_format(self) -> Dict[str, Any]:
        """转换为API输出格式"""
        return {
            "content": self.content,
            "type": self.type.value,
            "metadata": self.metadata,
            "timestamp": self.timestamp
        }
    
    @classmethod
    def create_content(cls, content: str, terminal_type: str, 
                      raw_length: int = 0) -> 'StreamChunk':
        """快速创建内容类型的数据块"""
        return cls(
            content=content,
            type=ChunkType.CONTENT,
            metadata=MetadataBuilder.for_content(
                raw_length or len(content),
                len(content),
                terminal_type
            ),
            timestamp=time.time()
        )
    
    @classmethod
    def create_error(cls, error_message: str, terminal_type: str,
                    error_type: str = "processing_error") -> 'StreamChunk':
        """快速创建错误类型的数据块"""
        return cls(
            content="",
            type=ChunkType.ERROR,
            metadata=MetadataBuilder.for_error(
                error_message,
                terminal_type,
                error_type
            ),
            timestamp=time.time()
        )


class MetadataBuilder:
    """元数据构建器 - 为不同类型的消息构建相应的元数据"""
    
    @staticmethod
    def for_thinking(raw_length: int, terminal_type: str) -> Dict[str, Any]:
        """思考状态的元数据"""
        return {
            "raw_length": raw_length,
            "terminal_type": terminal_type
        }
    
    @staticmethod
    def for_tool_use(tool_name: str, raw_length: int, terminal_type: str) -> Dict[str, Any]:
        """工具使用的元数据"""
        return {
            "tool_name": tool_name,
            "raw_length": raw_length,
            "terminal_type": terminal_type
        }
    
    @staticmethod
    def for_content(raw_length: int, content_length: int, terminal_type: str) -> Dict[str, Any]:
        """内容输出的元数据"""
        return {
            "raw_length": raw_length,
            "content_length": content_length,
            "terminal_type": terminal_type
        }
    
    @staticmethod
    def for_error(error_message: str, terminal_type: str, error_type: str = "execution_error") -> Dict[str, Any]:
        """错误状态的元数据"""
        return {
            "error_message": error_message,
            "error_type": error_type,
            "terminal_type": terminal_type
        }
    
    @staticmethod
    def for_pending(terminal_type: str, prompt_text: str = "") -> Dict[str, Any]:
        """等待状态的元数据"""
        return {
            "terminal_type": terminal_type,
            "prompt_text": prompt_text
        }


# 便捷的类型检查函数
def is_user_visible_content(chunk: StreamChunk) -> bool:
    """判断数据块是否应该显示给用户"""
    return chunk.type in [ChunkType.CONTENT, ChunkType.ERROR]


def is_status_indicator(chunk: StreamChunk) -> bool:
    """判断数据块是否是状态指示器"""
    return chunk.type in [ChunkType.THINKING, ChunkType.TOOL_USE, ChunkType.PENDING]


def is_completion_marker(chunk: StreamChunk) -> bool:
    """判断数据块是否是完成标记"""
    return chunk.type == ChunkType.COMPLETE
