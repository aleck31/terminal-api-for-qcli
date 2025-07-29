#!/usr/bin/env python3
"""
ANSI转义序列清理工具
"""

import re

class ANSICleaner:
    """ANSI 转义序列清理器"""
    
    def __init__(self):
        # 组合正则表达式 - 一次性清理所有不需要的字符
        self.cleanup_pattern = re.compile(r'''
            \x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])  # ANSI转义序列
            |
            \x1b[78]  # 光标控制序列 (ESC 7/8)
            |
            [⠋⠙⠹⠸⠼⠴⠦⠧⠇⠏⠛⠓⠒⠑⠐⠡⠢⠤⠥⠦⠧⠨⠩⠪⠫⠬⠭⠮⠯⠰⠱⠲⠳⠴⠵⠶⠷⠸⠹⠺⠻⠼⠽⠾⠿]  # Braille字符（加载动画）
        ''', re.VERBOSE)
        
        # 其他控制字符（保留换行符、回车符、制表符）
        self.control_chars = re.compile(r'[\x00-\x08\x0B\x0C\x0E-\x1F\x7F-\x9F]')
        
        # 常见的无意义字符组合
        self.meaningless_patterns = re.compile(r'^\s*[78]+\s*$|^\s*[A-Z]?\s*$|^\s*\[\d*[A-Z]?\s*$')
        
        # 空白字符清理
        self.whitespace_cleanup = re.compile(r' +')  # 多个空格
        self.newline_cleanup = re.compile(r'\n\s*\n')  # 多个换行
    
    def clean(self, text: str, preserve_newlines: bool = True) -> str:
        """
        清理ANSI转义序列和控制字符
        
        Args:
            text: 要清理的文本
            preserve_newlines: 是否保留换行符
            
        Returns:
            清理后的文本
        """
        if not text:
            return text
        
        # 1. 使用组合正则一次性清理ANSI序列、光标控制和动画字符
        text = self.cleanup_pattern.sub('', text)
        
        # 2. 清理其他控制字符
        if preserve_newlines:
            text = self.control_chars.sub('', text)
        else:
            # 如果不保留换行符，清理所有控制字符
            text = re.sub(r'[\x00-\x1F\x7F-\x9F]', '', text)
        
        # 3. 清理多余的空白（使用预编译的正则）
        text = self.whitespace_cleanup.sub(' ', text)
        text = self.newline_cleanup.sub('\n', text)
        
        # 4. 去除首尾空白
        text = text.strip()
        
        return text
    
    def extract_readable_content(self, text: str) -> str:
        """
        提取可读内容，过滤掉纯控制序列
        
        Args:
            text: 原始文本
            
        Returns:
            可读内容，如果没有可读内容返回空字符串
        """
        cleaned = self.clean(text)
        
        # 如果清理后的内容太短或只包含空白，认为没有有用内容
        if len(cleaned.strip()) < 2:
            return ""
        
        return cleaned
    
    def is_meaningful_content(self, text: str) -> bool:
        """
        判断文本是否包含有意义的内容
        
        Args:
            text: 要检查的文本
            
        Returns:
            True 如果包含有意义的内容
        """
        cleaned = self.extract_readable_content(text)
        
        # 检查是否为空或只有空白
        if len(cleaned) == 0 or cleaned.isspace():
            return False
        
        # 检查是否匹配无意义模式
        if self.meaningless_patterns.match(cleaned):
            return False
        
        # 检查是否只包含数字和少量字符（如 "78", "1A8" 等）
        if len(cleaned) <= 3 and re.match(r'^[0-9A-Za-z\[\]]+$', cleaned):
            return False
        
        # 保留常见的命令提示符
        if cleaned in ['>', '$ ', '# ', '>>> ', '> ']:
            return True
        
        return True
    
    def clean_batch(self, messages: list) -> list:
        """
        批量清理消息，提升处理大量消息时的性能
        
        Args:
            messages: 消息列表
            
        Returns:
            清理后的消息列表
        """
        return [self.clean(msg) for msg in messages if msg]
    
    def filter_meaningful_messages(self, messages: list) -> list:
        """
        过滤出有意义的消息
        
        Args:
            messages: 消息列表
            
        Returns:
            有意义的消息列表
        """
        return [msg for msg in messages if self.is_meaningful_content(msg)]

# 全局实例
ansi_cleaner = ANSICleaner()