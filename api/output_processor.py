#!/usr/bin/env python3
"""
Output Processor - 统一数据流架构
专注数据转换：将原始消息转换为统一的 StreamChunk 格式
支持不同终端类型的分支处理
"""

import logging
import time
from typing import Optional

from .data_structures import StreamChunk, ChunkType, MetadataBuilder, TerminalType
from .utils.formatter import clean_terminal_text
from .utils.qcli_formatter import QcliOutputFormatter, QCLIResponseType

logger = logging.getLogger(__name__)


class OutputProcessor:
    """统一的输出处理器 - 实现统一数据流架构"""
    
    def __init__(self, terminal_type: TerminalType = TerminalType.GENERIC):
        """
        初始化输出处理器
        
        Args:
            terminal_type: 终端类型
        """
        self.terminal_type = terminal_type
        
        # 初始化格式化器
        if terminal_type == TerminalType.QCLI:
            self.qcli_formatter = QcliOutputFormatter()
        
        # 命令回显移除状态（每个命令独立）
        self._echo_removed_for_command = {}
    
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
                return self._process_qcli_message(raw_message)
            else:
                return self._process_generic_message(raw_message, command)
                
        except Exception as e:
            logger.error(f"消息处理失败: {e}")
            return StreamChunk.create_error(
                str(e), 
                current_terminal_type.value,
                "processing_error"
            )
    
    def _process_qcli_message(self, raw_message: str) -> Optional[StreamChunk]:
        """
        Q CLI 分支处理
        
        Args:
            raw_message: 原始消息
            
        Returns:
            StreamChunk: 处理后的数据块
        """
        # 1. 检测消息类型（基于原始数据）
        qcli_message_type = self.qcli_formatter.detect_message_type(raw_message)
        
        # 2. 清理消息内容
        clean_content = self.qcli_formatter.clean_qcli_output(raw_message)
        
        # 3. 映射到统一的 ChunkType
        chunk_type = self._map_qcli_type_to_chunk_type(qcli_message_type)
        
        # 4. 根据类型决定内容
        if chunk_type in [ChunkType.THINKING, ChunkType.TOOL_USE, ChunkType.COMPLETE]:
            # 状态类型：不返回内容，但保留类型信息
            content = ""
        elif chunk_type == ChunkType.CONTENT:
            # 内容类型：返回清理后的内容
            content = clean_content
            # 如果清理后没有有效内容，跳过这个消息
            if not content.strip():
                return None
        else:
            # 其他类型
            content = clean_content
        
        # 5. 构建元数据
        metadata = self._build_qcli_metadata(raw_message, clean_content, chunk_type, qcli_message_type)
        
        # 6. 构建 StreamChunk
        return StreamChunk(
            content=content,
            type=chunk_type,
            metadata=metadata,
            timestamp=time.time()
        )
    
    def _process_generic_message(self, raw_message: str, command: str) -> Optional[StreamChunk]:
        """
        Generic 分支处理
        
        Args:
            raw_message: 原始消息
            command: 当前命令（用于回显移除）
            
        Returns:
            StreamChunk: 处理后的数据块
        """
        # 1. 清理消息内容
        clean_content = self._clean_generic_content(raw_message, command)
        
        # 2. 如果没有有效内容，跳过
        if not clean_content.strip():
            return None
        
        # 3. 构建元数据
        metadata = MetadataBuilder.for_content(
            len(raw_message),
            len(clean_content),
            "generic"
        )
        
        # 4. 构建 StreamChunk（通用终端默认为内容类型）
        return StreamChunk(
            content=clean_content,
            type=ChunkType.CONTENT,
            metadata=metadata,
            timestamp=time.time()
        )
    
    def _map_qcli_type_to_chunk_type(self, qcli_type: QCLIResponseType) -> ChunkType:
        """将 Q CLI 类型映射到统一的 ChunkType"""
        mapping = {
            QCLIResponseType.THINKING: ChunkType.THINKING,
            QCLIResponseType.TOOL_USE: ChunkType.TOOL_USE,
            QCLIResponseType.STREAMING: ChunkType.CONTENT,
            QCLIResponseType.COMPLETE: ChunkType.COMPLETE,
        }
        return mapping.get(qcli_type, ChunkType.CONTENT)
    
    def _build_qcli_metadata(self, raw_message: str, clean_content: str, 
                           chunk_type: ChunkType, qcli_type: QCLIResponseType) -> dict:
        """构建 Q CLI 特定的元数据"""
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
            # 完成状态的元数据需要从外部传入执行时间等信息
            # 这里先提供基础信息
            return {
                "raw_length": len(raw_message),
                "terminal_type": "qcli",
                "qcli_message_type": qcli_type.value
            }
        else:
            return {"raw_length": len(raw_message), "terminal_type": "qcli"}
    
    def _extract_tool_name(self, raw_message: str) -> str:
        """从原始消息中提取工具名称"""
        # 基于真实数据的工具名称提取
        # 格式："\u001b[38;5;13m🛠️  Using tool: web_search_exa\u001b[38;5;2m (trusted)\u001b[39m"
        import re
        
        # 清理后再提取
        cleaned = self.qcli_formatter.clean_qcli_output(raw_message)
        
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
    
    def _clean_generic_content(self, raw_message: str, command: str) -> str:
        """清理通用终端内容"""
        # 1. 基础 ANSI 清理
        cleaned = clean_terminal_text(raw_message)
        
        if not cleaned:
            return ""
        
        # 2. 移除命令回显（只移除一次）
        if command and not self._echo_removed_for_command.get(command, False):
            if command in cleaned:
                cleaned = cleaned.replace(command, "", 1)
                self._echo_removed_for_command[command] = True
                logger.debug(f"移除命令回显: {command}")
        
        # 3. 额外清理
        cleaned = self._additional_cleanup(cleaned)
        
        return cleaned
    
    def _additional_cleanup(self, text: str) -> str:
        """额外的文本清理"""
        if not text:
            return ""
        
        # 移除多余的空白行
        lines = text.split('\n')
        cleaned_lines = []
        
        for line in lines:
            # 移除只包含空白字符的行
            if line.strip():
                cleaned_lines.append(line.rstrip())
        
        # 重新组合，避免多余的空行
        result = '\n'.join(cleaned_lines)
        
        # 移除开头和结尾的空白
        result = result.strip()
        
        return result
    
    def reset_command_state(self, command: str):
        """重置特定命令的状态"""
        if command in self._echo_removed_for_command:
            del self._echo_removed_for_command[command]
    
    def clear_all_states(self):
        """清理所有命令状态"""
        self._echo_removed_for_command.clear()
    
    # 向后兼容的方法（保留旧接口，内部调用新接口）
    def process_stream_output(self, raw_output: str, command: str) -> str:
        """向后兼容：处理流式输出"""
        chunk = self.process_raw_message(raw_output, command)
        if chunk and chunk.type == ChunkType.CONTENT:
            return chunk.content
        return ""
