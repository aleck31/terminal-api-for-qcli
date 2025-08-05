#!/usr/bin/env python3
"""
Output Processor
专注数据转换：统一的原始数据清理和格式化入口
支持不同终端类型：bash、qcli 等
"""

import logging
from typing import Optional, Union
from dataclasses import dataclass
from enum import Enum

from .utils.formatter import clean_terminal_text
from .utils.qcli_formatter import clean_qcli_text, process_qcli_chunk, QCLIChunk, QCLIState

logger = logging.getLogger(__name__)

class TerminalType(Enum):
    """终端类型"""
    BASH = "bash"
    QCLI = "qcli"
    PYTHON = "python"

@dataclass
class ProcessedOutput:
    """处理后的输出"""
    cleaned_text: str        # 清理后的纯文本
    formatted_text: str      # 格式化后的文本（用于显示）
    command_echo_removed: bool = False
    # Q CLI 特有字段
    qcli_chunk: Optional[QCLIChunk] = None

class OutputProcessor:
    """输出处理器 - 专注数据转换，支持多种终端类型"""
    
    def __init__(self, terminal_type: TerminalType = TerminalType.BASH, enable_formatting: bool = True):
        """
        初始化输出处理器
        
        Args:
            terminal_type: 终端类型
            enable_formatting: 是否启用格式化输出
        """
        self.terminal_type = terminal_type
        self.enable_formatting = enable_formatting
        
        # 命令回显移除状态（每个命令独立）
        self._echo_removed_for_command = {}
    
    def process_raw_output(self, raw_output: str) -> str:
        """
        处理原始输出 - 基础清理
        
        Args:
            raw_output: 原始输出数据
            
        Returns:
            str: 清理后的文本
        """
        if not raw_output:
            return ""
        
        # 根据终端类型选择清理方法
        if self.terminal_type == TerminalType.QCLI:
            cleaned = clean_qcli_text(raw_output)
        else:
            # 默认使用标准终端清理
            cleaned = clean_terminal_text(raw_output)
        
        if not cleaned:
            return ""
        
        # 进一步清理（移除多余的空白等）
        cleaned = self._additional_cleanup(cleaned)
        
        return cleaned
    
    def process_stream_output(self, raw_output: str, command: str) -> str:
        """
        处理流式输出 - 用于实时显示
        
        Args:
            raw_output: 原始输出数据
            command: 当前执行的命令
            
        Returns:
            str: 处理后的输出（用于流式显示）
        """
        if not raw_output:
            return ""
        
        # Q CLI 有特殊的流式处理逻辑
        if self.terminal_type == TerminalType.QCLI:
            return self._process_qcli_stream_output(raw_output, command)
        
        # 标准终端的流式处理
        return self._process_standard_stream_output(raw_output, command)
    
    def process_qcli_chunk(self, raw_output: str) -> QCLIChunk:
        """
        处理 Q CLI 消息块 - Q CLI 专用方法
        
        Args:
            raw_output: 原始输出数据
            
        Returns:
            QCLIChunk: Q CLI 消息块
        """
        if self.terminal_type != TerminalType.QCLI:
            raise ValueError("process_qcli_chunk 只能在 QCLI 终端类型下使用")
        
        return process_qcli_chunk(raw_output)
    
    def _process_qcli_stream_output(self, raw_output: str, command: str) -> str:
        """处理 Q CLI 流式输出"""
        chunk = process_qcli_chunk(raw_output)
        
        # 只返回有效的回复内容
        if chunk.is_content:
            return chunk.content
        elif chunk.state == QCLIState.THINKING:
            return "Thinking..."  # 可以选择是否显示思考状态
        else:
            return ""  # 其他状态不返回内容
    
    def _process_standard_stream_output(self, raw_output: str, command: str) -> str:
        """处理标准终端流式输出"""
        # 1. 基础清理
        cleaned = self.process_raw_output(raw_output)
        
        if not cleaned:
            return ""
        
        # 2. 移除命令回显（只移除一次）
        if command and not self._echo_removed_for_command.get(command, False):
            if command in cleaned:
                cleaned = cleaned.replace(command, "", 1)
                self._echo_removed_for_command[command] = True
                logger.debug(f"移除命令回显: {command}")
        
        # 3. 清理处理后的空白
        cleaned = cleaned.strip()
        
        return cleaned
    
    def _additional_cleanup(self, text: str) -> str:
        """
        额外的文本清理
        
        Args:
            text: 已经过 ANSI 清理的文本
            
        Returns:
            str: 进一步清理后的文本
        """
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
        """
        重置特定命令的状态
        
        Args:
            command: 要重置状态的命令
        """
        if command in self._echo_removed_for_command:
            del self._echo_removed_for_command[command]
    
    def clear_all_states(self):
        """清理所有命令状态"""
        self._echo_removed_for_command.clear()
