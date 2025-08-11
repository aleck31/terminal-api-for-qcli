#!/usr/bin/env python3
"""
统一的 ANSI 格式化工具
使用 stransi 进行 ANSI 序列解析，支持通用终端和 Q CLI
"""

import re
import logging
from typing import Tuple
from stransi import Ansi

# 导入统一的数据结构
from ..data_structures import ChunkType

logger = logging.getLogger(__name__)


class AnsiBuffer:
    """简单的ANSI序列缓冲器，处理消息截断问题"""
    
    def __init__(self):
        self.pending = ""
    
    def process(self, chunk: str) -> str:
        """处理消息块，返回完整的文本"""
        full_text = self.pending + chunk
        
        # 检查末尾是否有不完整的ANSI序列（以\x1b[开始但没有结束字母）
        incomplete_match = re.search(r'\x1b\[[0-9;]*$', full_text)
        
        if incomplete_match:
            # 有不完整序列，保存到缓冲区
            complete_part = full_text[:incomplete_match.start()]
            self.pending = full_text[incomplete_match.start():]
            return complete_part
        else:
            # 没有不完整序列，清空缓冲区
            self.pending = ""
            return full_text
    
    def flush(self) -> str:
        """强制刷新缓冲区"""
        pending = self.pending
        self.pending = ""
        return pending


class AnsiFormatter:
    """
    统一的 ANSI 格式化器
    支持通用终端输出和 Q CLI 特定功能
    """
    
    def __init__(self):
        # ANSI缓冲器
        self.ansi_buffer = AnsiBuffer()
        
        # Q CLI 特定的模式
        self.loading_pattern = re.compile(r'[⠋⠙⠹⠸⠼⠴⠦⠧⠇⠏]+')
        self.tool_use_pattern = re.compile(r'🛠️\s+Using tool:', re.IGNORECASE)
        
        # 状态跟踪（用于Q CLI）
        self.last_message_type = ChunkType.CONTENT

    def parse_terminal_output(self, raw_message: str) -> Tuple[str, ChunkType]:
        """
        解析通用终端输出 - 清理ANSI序列并检测消息类型
        
        Args:
            raw_message: 原始终端消息
            
        Returns:
            tuple[str, ChunkType]: (清理后的纯文本, 消息类型)
        """
        
        # 1. 检测完成信号（提示符）- 在原始文本中检测
        is_complete = self._detect_terminal_prompt_regex(raw_message)
        
        # 2. 使用正则表达式清理文本
        clean_text = self._clean_terminal_regex(raw_message)
        
        # 3. 确定消息类型
        if is_complete:
            message_type = ChunkType.COMPLETE
        elif clean_text.strip():
            message_type = ChunkType.CONTENT
        else:
            message_type = self.last_message_type
        
        self.last_message_type = message_type
        return clean_text, message_type
    
    def _detect_terminal_prompt_regex(self, raw_text: str) -> bool:
        """检测终端完成信号"""

        # 检测OSC 697序列（不依赖于shell配置）
        osc_patterns = [
            r'\x1b\]697;NewCmd=',     # 新命令开始（最可靠的完成信号）
            r'\x1b\]697;ExitCode=',   # 命令退出码（命令执行完成）
            r'\x1b\]697;EndPrompt\x07', # 提示符结束
        ]

        for pattern in osc_patterns:
            if re.search(pattern, raw_text):
                return True
        
        return False
    
    def _clean_terminal_regex(self, text: str) -> str:
        """使用正则表达式清理通用终端输出"""
        if not text:
            return ""
        
        # 移除OSC序列（Operating System Command）
        text = re.sub(r'\x1b\][^\x07]*\x07', '', text)
        
        # 移除标准ANSI转义序列
        text = re.sub(r'\x1b\[[0-9;]*[mGKHfABCDsuJ]', '', text)
        
        # 移除其他ANSI序列
        text = re.sub(r'\x1b[?][0-9]*[hl]', '', text)  # 私有模式
        text = re.sub(r'\x1b[78]', '', text)  # 保存/恢复光标
        
        # 清理回车符
        text = re.sub(r'\r+', '', text)
        
        # 清理多余空白
        text = re.sub(r' {3,}', ' ', text)
        text = re.sub(r'\n{3,}', '\n\n', text)
        
        return text.strip()

    def parse_qcli_output(self, raw_message: str) -> Tuple[str, ChunkType]:
        """
        解析 Q CLI 输出 - 一次解析同时获得纯文本和消息类型
        
        Args:
            raw_message: 原始消息
            
        Returns:
            tuple[str, ChunkType]: (清理后的文本, 消息类型)
        """
        if not raw_message:
            return "", self.last_message_type
        
        # 1. 处理ANSI缓冲
        complete_text = self.ansi_buffer.process(raw_message)
        if not complete_text:
            return "", self.last_message_type
        
        # 2. 使用 stransi 解析
        ansi_text = Ansi(complete_text)
        
        # 获取纯文本
        plain_parts = []
        for item in ansi_text.escapes():
            if type(item) is str:
                plain_parts.append(item)
        clean_text = ''.join(plain_parts)
        
        # 同时检测消息类型和完成状态
        message_type = self._detect_qcli_message(ansi_text, clean_text)
        
        # Q CLI输出不需要额外清理，stransi解析的结果已经很干净
        self.last_message_type = message_type
        return clean_text, message_type

    def _detect_qcli_message(self, ansi_text: Ansi, clean_text: str) -> ChunkType:
        """
        基于stransi解析结果检测消息类型和完成状态
        
        Args:
            ansi_text: stransi解析的Ansi对象
            clean_text: 提取的纯文本
            
        Returns:
            ChunkType: 消息类型
        """
        # Q CLI完成检测：基于稳定的文本特征
        if '!>' in clean_text and clean_text.endswith('\r'):
            logger.info("检测到Q CLI完成信号：'!>' 模式 + 结尾\\r")
            return ChunkType.COMPLETE
        
        # 检测思考状态
        if self.loading_pattern.search(clean_text) and 'Thinking' in clean_text:
            return ChunkType.THINKING
        
        # 检测工具使用
        if self.tool_use_pattern.search(clean_text):
            return ChunkType.TOOL_USE
        
        # 默认为内容
        if clean_text.strip():
            return ChunkType.CONTENT
        
        return self.last_message_type

# 全局实例
ansi_formatter = AnsiFormatter()

# 便捷函数

def parse_qcli_text(text: str) -> Tuple[str, ChunkType]:
    """解析 Q CLI 文本的便捷函数 - 返回纯文本和消息类型"""
    return ansi_formatter.parse_qcli_output(text)


def parse_terminal_text(text: str) -> Tuple[str, ChunkType]:
    """解析通用终端文本的便捷函数 - 返回清理后的纯文本和消息类型"""
    return ansi_formatter.parse_terminal_output(text)
