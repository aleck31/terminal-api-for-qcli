#!/usr/bin/env python3
"""
Message Processor - 统一数据流架构
将原始消息转换为统一的 StreamChunk 格式
"""

import logging
import time
from typing import Optional

from .data_structures import StreamChunk, ChunkType, MetadataBuilder, TerminalType
from .utils.ansi_formatter import ansi_formatter

logger = logging.getLogger(__name__)


class MessageProcessor:
    """统一的输出处理器 - 实现统一数据流架构"""
    
    def __init__(self, terminal_type: TerminalType = TerminalType.GENERIC):
        """
        初始化输出处理器
        
        Args:
            terminal_type: 终端类型
        """
        self.terminal_type = terminal_type
    
    def process_raw_message(self, raw_message: str, command: str = "", 
                          terminal_type: Optional[TerminalType] = None) -> Optional[StreamChunk]:
        """
        统一的消息处理入口 - 核心接口
        
        Args:
            raw_message: 原始消息数据
            command: 当前执行的命令（用于回显移除）
            terminal_type: 终端类型（可选，覆盖实例设置）
            
        Returns:
            StreamChunk: 统一格式的数据块，如果无有效内容则返回 None
        """
        if not raw_message:
            return None
        
        # 使用传入的终端类型或实例设置
        current_terminal_type = terminal_type or self.terminal_type
        
        try:
            if current_terminal_type == TerminalType.QCLI:
                return self._process_qcli_message(raw_message, command)
            else:
                return self._process_generic_message(raw_message, command)
                
        except Exception as e:
            logger.error(f"消息处理失败: {e}")
            return StreamChunk.create_error(
                str(e), 
                current_terminal_type.value,
                "processing_error"
            )

    def _process_generic_message(self, raw_message: str, command: str) -> Optional[StreamChunk]:
        """
        Generic 分支处理 - 使用统一的ChunkType
        
        Args:
            raw_message: 原始消息
            command: 当前命令（用于回显移除）
            
        Returns:
            StreamChunk: 处理后的数据块
        """
        # 1. 使用新的parse_terminal_output方法，一次获得内容和类型
        clean_content, chunk_type = ansi_formatter.parse_terminal_output(raw_message)
        
        # 2. 移除命令回显（只对CONTENT类型的消息处理）
        if chunk_type == ChunkType.CONTENT and command and command.strip():
            clean_content = self._remove_command_echo(clean_content, command.strip())
        
        # 3. 如果没有有效内容且不是完成信号，跳过
        if not clean_content.strip() and chunk_type != ChunkType.COMPLETE:
            return None
        
        # 4. 根据类型决定返回的内容
        if chunk_type == ChunkType.CONTENT:
            content = clean_content
        elif chunk_type == ChunkType.COMPLETE:
            # 完成信号不返回内容给用户
            content = ""
        else:
            content = clean_content
        
        # 5. 构建 StreamChunk
        return StreamChunk(
            content=content,
            type=chunk_type,
            metadata=MetadataBuilder.for_content(
                len(raw_message),
                len(content),
                "generic"
            ),
            timestamp=time.time()
        )
    
    def _remove_command_echo(self, content: str, command: str, terminal_type: str = 'generic') -> str:
        """移除命令回显"""
        if not content or not command:
            return content
        
        # 移除第一次出现的完整命令
        if command in content:
            content = content.replace(command, "", 1)
            logger.debug(f"移除命令回显: {command}")
        
        if terminal_type == 'qcli':
            return command

        # 清理可能的多余空白
        lines = content.split('\n')
        cleaned_lines = []
        
        for line in lines:
            # 移除只包含空白字符的行
            if line.strip():
                cleaned_lines.append(line.rstrip())
        
        return '\n'.join(cleaned_lines)

    def _process_qcli_message(self, raw_message: str, command: str) -> Optional[StreamChunk]:
        """
        Q CLI 分支处理 - 使用统一的ChunkType
        
        Args:
            raw_message: 原始消息
            command: 当前命令（预留）
            
        Returns:
            StreamChunk: 处理后的数据块
        """
        # 1. 获得清理后的内容和类型
        clean_content, chunk_type = ansi_formatter.parse_qcli_output(raw_message)
        
        # 2. 根据类型决定返回的内容
        if chunk_type == ChunkType.CONTENT:
            # 内容类型：移除命令回显后返回清理后的内容
            # clean_content = self._remove_command_echo(clean_content, command.strip(), 'qcli')
            content = clean_content
        elif chunk_type in [ChunkType.THINKING, ChunkType.TOOL_USE, ChunkType.COMPLETE]:
            # 状态类型：不返回内容给用户，但保留类型信息
            content = ""
        else:
            # 其他类型
            content = clean_content
        
        # 3. 构建元数据
        metadata = self._build_qcli_metadata(raw_message, clean_content, chunk_type)
        
        # 4. 构建 StreamChunk
        return StreamChunk(
            content=content,
            type=chunk_type,
            metadata=metadata,
            timestamp=time.time()
        )

    def _build_qcli_metadata(self, raw_message: str, clean_content: str, 
                           chunk_type: ChunkType) -> dict:
        """构建 Q CLI 特定的元数据 - 简化版本"""
        if chunk_type == ChunkType.THINKING:
            return MetadataBuilder.for_thinking(len(raw_message), "qcli")
        elif chunk_type == ChunkType.TOOL_USE:
            tool_name = self._extract_tool_name(raw_message)
            return MetadataBuilder.for_tool_use(tool_name, len(raw_message), "qcli")
        elif chunk_type == ChunkType.CONTENT:
            return MetadataBuilder.for_content(
                len(raw_message),
                len(clean_content),
                "qcli"
            )
        elif chunk_type == ChunkType.COMPLETE:
            return {
                "raw_length": len(raw_message),
                "terminal_type": "qcli"
            }
        else:
            return {"raw_length": len(raw_message), "terminal_type": "qcli"}
    
    def _extract_tool_name(self, raw_message: str) -> str:
        """从原始消息中提取工具名称"""
        import re
        
        # 清理后再提取
        cleaned, _ = ansi_formatter.parse_qcli_output(raw_message)
        
        # 提取工具名称的模式
        patterns = [
            r'Using tool:\s*([a-zA-Z_][a-zA-Z0-9_]*)',
            r'🛠️\s*Using tool:\s*([a-zA-Z_][a-zA-Z0-9_]*)',
            r'tool:\s*([a-zA-Z_][a-zA-Z0-9_]*)',
        ]
        
        for pattern in patterns:
            match = re.search(pattern, cleaned, re.IGNORECASE)
            if match:
                return match.group(1)
        
        return "unknown_tool"
