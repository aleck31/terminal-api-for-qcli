#!/usr/bin/env python3
"""
ANSI 转义序列清理工具
"""

import re

class ANSICleaner:
    """ANSI 转义序列清理器"""
    
    def __init__(self):
        # 更全面的ANSI转义序列正则表达式
        self.ansi_escape = re.compile(r'''
            \x1B  # ESC
            (?:   # 7-bit C1 Fe (except CSI)
                [@-Z\\-_]
            |     # or [ for CSI, followed by the parameter bytes
                \[
                [0-?]*  # Parameter bytes
                [ -/]*  # Intermediate bytes
                [@-~]   # Final byte
            )
        ''', re.VERBOSE)
        
        # 其他控制字符
        self.control_chars = re.compile(r'[\x00-\x08\x0B-\x1F\x7F-\x9F]')
        
        # 特殊的Unicode字符（如加载动画）
        self.spinner_chars = re.compile(r'[⠋⠙⠹⠸⠼⠴⠦⠧⠇⠏]')
    
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
        
        # 1. 清理ANSI转义序列
        text = self.ansi_escape.sub('', text)
        
        # 2. 清理加载动画字符
        text = self.spinner_chars.sub('', text)
        
        # 3. 清理其他控制字符（保留换行符和制表符）
        if preserve_newlines:
            # 保留 \n (0x0A) 和 \r (0x0D) 和 \t (0x09)
            text = re.sub(r'[\x00-\x08\x0B\x0C\x0E-\x1F\x7F-\x9F]', '', text)
        else:
            text = self.control_chars.sub('', text)
        
        # 4. 清理多余的空白
        text = re.sub(r' +', ' ', text)  # 多个空格变成一个
        text = re.sub(r'\n\s*\n', '\n', text)  # 多个换行变成一个
        
        # 5. 去除首尾空白
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
        return len(cleaned) > 0 and not cleaned.isspace()

# 全局实例
ansi_cleaner = ANSICleaner()