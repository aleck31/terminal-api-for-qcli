#!/usr/bin/env python3
"""
Output Processor
专注数据转换：统一的原始数据清理和格式化入口
不负责命令完成检测，只处理数据转换
"""

import logging
from typing import Optional
from dataclasses import dataclass

from .utils.formatter import clean_terminal_text

logger = logging.getLogger(__name__)

@dataclass
class ProcessedOutput:
    """处理后的输出"""
    cleaned_text: str        # 清理后的纯文本
    formatted_text: str      # 格式化后的文本（用于显示）
    command_echo_removed: bool = False

class OutputProcessor:
    """输出处理器 - 专注数据转换"""
    
    def __init__(self, enable_formatting: bool = True):
        """
        初始化输出处理器
        
        Args:
            enable_formatting: 是否启用格式化输出
        """
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
        
        # 1. ANSI 清理
        cleaned = clean_terminal_text(raw_output)
        
        if not cleaned:
            return ""
        
        # 2. 进一步清理（移除多余的空白等）
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
