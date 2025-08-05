#!/usr/bin/env python3
"""
Formatter Tools
"""

import re
from typing import Optional
from dataclasses import dataclass

@dataclass
class FormattedOutput:
    """格式化后的输出"""
    plain_text: str
    command: Optional[str] = None
    exit_code: Optional[int] = None

class TerminalOutputFormatter:
    """终端输出格式化器 - 清理终端输出中的控制序列和 OSC 序列"""
    
    def __init__(self):
        # ANSI 转义序列模式
        self.ansi_escape = re.compile(r'\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])')
        
        # OSC 序列模式 (Operating System Command)
        self.osc_pattern = re.compile(r'\x1B\][^\x07]*\x07')
        
        # 特殊的 OSC 697 序列（shell 集成信息）
        self.osc_697_pattern = re.compile(r'697;[^697]*(?=697|$)')
        
        # 控制字符模式
        self.control_chars = re.compile(r'[\x00-\x08\x0B\x0C\x0E-\x1F\x7F-\x9F]')
        
        # 回车符处理
        self.carriage_return = re.compile(r'\r+')
        
        # 多余空白处理
        self.multiple_spaces = re.compile(r' {3,}')
        self.multiple_newlines = re.compile(r'\n{3,}')
    
    def clean_terminal_output(self, raw_output: str) -> str:
        """清理终端输出，移除控制序列 - 修复清理顺序"""
        if not raw_output:
            return ""
        
        text = raw_output
        
        # 1. 首先清理所有完整的 OSC 序列（优先级最高，避免被其他规则破坏）
        # 这包括 OSC 0, 697, 1337 等所有序列
        text = self.osc_pattern.sub('', text)
        
        # 2. 移除 ANSI 转义序列
        text = self.ansi_escape.sub('', text)
        
        # 3. 处理回车符和特殊字符
        text = self.carriage_return.sub('', text)
        
        # 4. 移除其他控制字符（保留换行符和制表符）
        text = self.control_chars.sub('', text)
        
        # 5. 清理提示符相关的残留
        text = re.sub(r'ubuntu@[^:]*:[^$]*\$\s*', '', text)
        
        # 6. 清理多余的空白
        text = self.multiple_spaces.sub(' ', text)
        text = self.multiple_newlines.sub('\n\n', text)
        
        return text

# 全局实例
terminal_formatter = TerminalOutputFormatter()

# 便捷函数
def format_terminal_output(raw_output: str, command: str = None, 
                         success: bool = True, execution_time: float = 0.0,
                         error: str = None) -> FormattedOutput:
    """格式化终端输出的便捷函数"""
    # 清理原始输出
    cleaned_output = terminal_formatter.clean_terminal_output(raw_output)
    
    return FormattedOutput(
        plain_text=cleaned_output,
        command=command,
        exit_code=0 if success else 1
    )

def clean_terminal_text(text: str) -> str:
    """清理终端文本的便捷函数"""
    return terminal_formatter.clean_terminal_output(text)
