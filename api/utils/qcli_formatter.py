#!/usr/bin/env python3
"""
Q CLI 输出格式化工具
专用于处理 Amazon Q CLI 的输出格式化和消息类型识别
"""

import re
from typing import Dict, Any, Optional

# 导入统一的数据结构
from ..data_structures import ChunkType


class QcliOutputFormatter:
    """
    Q CLI 输出格式化器 - 纯工具类
    
    专门处理 Q CLI 的输出格式化和消息类型识别，
    不定义自己的数据结构，只提供工具方法。
    """
    
    def __init__(self):
        """初始化格式化器 - 预编译所有正则表达式以提高性能"""
        
        # === 消息类型识别模式 ===
        # 思考状态：只检测旋转指示符
        self.thinking_pattern = re.compile(r'[⠋⠙⠹⠸⠼⠴⠦⠧⠇⠏]')
        
        # 工具使用状态：基于真实格式 "🛠️  Using tool: web_search_exa"
        self.tool_use_pattern = re.compile(r'🛠️\s+Using tool:', re.IGNORECASE)
        
        # === 清理模式 ===
        # 统一的控制字符和ANSI序列清理
        self.unified_cleanup = re.compile(
            r'(?:'
            # 完整OSC序列，如窗口标题设置
            r'\x1B\][^\x07]*\x07|'
            # 标准ANSI序列
            r'\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])|'
            # 光标控制序列：保存、恢复、移动
            r'\x1B[78]|'  # \x1b7 和 \x1b8 (保存/恢复)
            r'\x1B\[[0-9]*[ABCDEFGHJKST]|'  # 光标移动
            r'\x1B\[[0-9]*K|'  # 行清除
            # 残留的ANSI片段
            r'\[[0-9;]*[a-zA-Z]|'
            r'[0-9]+m|'  # 单独的数字+m (如 39m)
            # 其他控制字符，但保留换行符和制表符
            r'[\x00-\x09\x0B\x0C\x0E-\x1F\x7F-\x9F]|'
            # 连续回车符
            r'\r+'
            r')'
        )
        
        # 旋转指示符清理
        self.spinner_pattern = re.compile(r'[⠋⠙⠹⠸⠼⠴⠦⠧⠇⠏]+')
        
        # Q CLI 提示符清理
        self.prompt_cleanup = re.compile(r'!\s*>\s*$')
        
        # 多行清理
        self.multiple_newlines = re.compile(r'\n{3,}')
        
        # 完成检测模式
        self.completion_patterns = [
            # 标准的 Q CLI 提示符模式
            re.compile(r'\x1b\[38;5;9m!\x1b\[39m\x1b\[38;5;13m>\s*\x1b\[39m'),  # 红色!紫色>
            re.compile(r'\x1b\[31m!\x1b\[35m>\s*\x1b\[39m'),  # 简化版本
            re.compile(r'\x1b\[31m!\x1b\[35m>\s*\x1b\[0m'),   # 另一种重置
            # 更宽松的模式
            re.compile(r'!\x1b\[39m\x1b\[38;5;13m>\s*'),  # 部分匹配
            re.compile(r'!\x1b.*?>\s*\x1b'),  # 通用模式
        ]
        
        # 上下文跟踪（用于连续性判断）
        self.last_message_type = ChunkType.THINKING
    
    def clean_qcli_output(self, raw_message: str) -> str:
        """
        清理 Q CLI 输出中的控制字符
        
        使用预编译的正则表达式，高效清理所有终端控制字符
        
        Args:
            raw_message: 原始消息（来自 ttyd 协议解析）
            
        Returns:
            str: 清理后的消息内容
        """
        if not raw_message:
            return ""
        
        # 1. 一次性清理所有控制字符和 ANSI 序列（使用预编译的正则）
        clean_message = self.unified_cleanup.sub('', raw_message)
        
        # 2. 清理旋转指示符 (spinners)（使用预编译的正则）
        clean_message = self.spinner_pattern.sub('', clean_message)
        
        # 3. 清理 Q CLI 特有的提示符残留（使用预编译的正则）
        clean_message = self.prompt_cleanup.sub('', clean_message)
        
        # 4. 清理多余的空白行（保留段落结构）（使用预编译的正则）
        clean_message = self.multiple_newlines.sub('\n\n', clean_message)
        
        # 5. 不使用 strip()，保留重要的前后空格
        return clean_message
    
    def clean_and_detect_completion(self, raw_message: str) -> tuple[str, bool]:
        """
        清理 Q CLI 输出并检测是否完成
        
        Args:
            raw_message: 原始消息（来自 ttyd 协议解析）
            
        Returns:
            tuple: (clean_message, is_complete)
        """
        if not raw_message:
            return "", False
        
        # 先检测完成状态（基于原始消息）
        is_complete = self.detect_completion(raw_message)
        
        # 再清理内容
        clean_message = self.clean_qcli_output(raw_message)
        
        return clean_message, is_complete
    
    def detect_message_type(self, raw_message: str) -> ChunkType:
        """
        识别 Q CLI 消息类型 - 统一架构版本
        
        直接返回统一的 ChunkType，解决空格丢失问题
        
        Args:
            raw_message: 原始消息
            
        Returns:
            ChunkType: 统一的消息类型
        """
        if not raw_message:
            return self.last_message_type
        
        cleaned = self.clean_qcli_output(raw_message)
        
        # 1. 识别思考消息（旋转指示符）
        if self.thinking_pattern.search(cleaned):
            self.last_message_type = ChunkType.THINKING
            return self.last_message_type
        
        # 2. 识别工具使用
        if self.tool_use_pattern.search(cleaned):
            self.last_message_type = ChunkType.TOOL_USE
            return self.last_message_type
        
        # 3. 所有其他消息都视为内容（包括单独的空格）
        # 这解决了空格丢失的问题
        if cleaned or raw_message.strip():  # 只要有任何内容就认为是有效的
            self.last_message_type = ChunkType.CONTENT
            return ChunkType.CONTENT
        
        return self.last_message_type
    
    def detect_completion(self, raw_message: str) -> bool:
        """
        检测 Q CLI 回复是否完成
        
        Args:
            raw_message: 原始消息（包含 ANSI 序列）
            
        Returns:
            bool: 是否完成
        """
        if not raw_message:
            return False
            
        # 使用预编译的完成检测模式
        for pattern in self.completion_patterns:
            if pattern.search(raw_message):
                return True
        
        return False


# 全局实例（如果需要的话）
qcli_formatter = QcliOutputFormatter()

# 便捷函数
def clean_qcli_text(text: str) -> str:
    """清理 Q CLI 文本的便捷函数"""
    return qcli_formatter.clean_qcli_output(text)
