#!/usr/bin/env python3
"""
Q CLI 专用格式化工具 - 流式处理版本
与现有 formatter.py 架构保持一致
"""

import re
import logging
from typing import Optional, Dict, Any
from enum import Enum
from dataclasses import dataclass

logger = logging.getLogger(__name__)

class QCLIState(Enum):
    """Q CLI 状态"""
    INITIALIZING = "initializing"    # 初始化中
    READY = "ready"                  # 准备接收输入
    THINKING = "thinking"            # 思考中
    RESPONDING = "responding"        # 回复中
    COMPLETE = "complete"            # 回复完成

@dataclass
class QCLIChunk:
    """Q CLI 单个消息块"""
    state: QCLIState
    content: str                     # 清理后的内容
    is_content: bool = False         # 是否是有效的回复内容
    metadata: Dict[str, Any] = None

class QcliOutputFormatter:
    """Q CLI 专用输出格式化器 - 与 TerminalOutputFormatter 保持一致的设计"""
    
    def __init__(self):
        # ANSI 清理模式（与 TerminalOutputFormatter 保持一致）
        self.ansi_escape = re.compile(r'\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])')
        self.osc_pattern = re.compile(r'\x1B\][^\x07]*\x07')
        self.control_chars = re.compile(r'[\x00-\x08\x0B\x0C\x0E-\x1F\x7F-\x9F]')
        self.carriage_return = re.compile(r'\r+')
        self.multiple_spaces = re.compile(r' {3,}')
        self.multiple_newlines = re.compile(r'\n{3,}')
        
        # Q CLI 特定模式
        self.thinking_pattern = re.compile(r'[⠙⠹⠸⠼⠴⠦⠧⠇⠏⠋]\s*Thinking\.\.\.')
        self.token_usage_pattern = re.compile(r'█\s*(Tools|Q responses|Your prompts):')
        self.pro_tips_pattern = re.compile(r'💡\s*Pro Tips:')
        # 使用更宽松的模式匹配实际的回复开始格式
        self.response_start_pattern = re.compile(r'\x1b\[32m[\r\n]*>\s*\x1b\[39m')
        
        # 轻量级状态跟踪（仅用于状态检测）
        self.last_state = QCLIState.INITIALIZING
    
    def clean_qcli_output(self, text: str) -> str:
        """
        清理 Q CLI 输出 - 与 TerminalOutputFormatter.clean_terminal_output 保持一致的清理顺序
        """
        if not text:
            return ""
        
        # 1. 首先清理所有完整的 OSC 序列（优先级最高）
        text = self.osc_pattern.sub('', text)
        
        # 2. 移除 ANSI 转义序列
        text = self.ansi_escape.sub('', text)
        
        # 3. 处理回车符和特殊字符
        text = self.carriage_return.sub('', text)
        
        # 4. 移除其他控制字符（保留换行符和制表符）
        text = self.control_chars.sub('', text)
        
        # 5. 清理 Q CLI 特有的提示符残留
        text = re.sub(r'>\s*$', '', text)  # 移除行尾的提示符
        
        # 6. 清理多余的空白
        text = self.multiple_spaces.sub(' ', text)
        text = self.multiple_newlines.sub('\n\n', text)
        
        return text.strip()
    
    def detect_qcli_state(self, raw_message: str) -> QCLIState:
        """检测 Q CLI 当前状态"""
        cleaned = self.clean_qcli_output(raw_message)
        
        # 检测思考状态
        if self.thinking_pattern.search(raw_message):
            return QCLIState.THINKING
        
        # 检测初始化界面
        if (self.token_usage_pattern.search(cleaned) or 
            self.pro_tips_pattern.search(cleaned)):
            return QCLIState.INITIALIZING
        
        # 检测回复开始
        if self.response_start_pattern.search(raw_message):
            return QCLIState.RESPONDING
        
        # 如果上一个状态是回复中，且当前是纯文本，继续回复状态
        if (self.last_state == QCLIState.RESPONDING and 
            cleaned.strip() and 
            not re.search(r'[>\[\]█⠙⠹⠸⠼⠴⠦⠧⠇⠏⠋]', cleaned)):
            return QCLIState.RESPONDING
        
        # 检测准备状态（显示提示符）
        if '>' in cleaned and len(cleaned.strip()) < 10:
            return QCLIState.READY
        
        return self.last_state
    
    def extract_initialization_info(self, raw_message: str) -> Optional[Dict[str, Any]]:
        """提取初始化信息"""
        cleaned = self.clean_qcli_output(raw_message)
        
        info = {}
        
        # 提取 token 使用情况
        token_matches = re.findall(r'█\s*(.*?):\s*[^\n]*?(\d+)\s*tokens', cleaned)
        if token_matches:
            info['token_usage'] = {match[0]: match[1] for match in token_matches}
        
        # 检查是否包含 Pro Tips
        if self.pro_tips_pattern.search(cleaned):
            info['has_pro_tips'] = True
            
            # 提取命令提示
            commands = re.findall(r'/(\w+)', cleaned)
            if commands:
                info['available_commands'] = commands
        
        return info if info else None
    
    def is_response_content(self, raw_message: str, current_state: QCLIState) -> bool:
        """判断是否是有效的回复内容"""
        if current_state != QCLIState.RESPONDING:
            return False
        
        cleaned = self.clean_qcli_output(raw_message)
        
        # 如果是回复开始消息
        if self.response_start_pattern.search(raw_message):
            # 检查是否有实际内容
            content = re.sub(r'.*?>\s*', '', cleaned).strip()
            return bool(content)
        
        # 如果是纯文本消息（流式回复的一部分）
        return (cleaned.strip() and 
                not re.search(r'[>\[\]█⠙⠹⠸⠼⠴⠦⠧⠇⠏⠋]', cleaned))
    
    def process_qcli_chunk(self, raw_message: str) -> QCLIChunk:
        """处理单个 Q CLI 消息块 - 流式版本"""
        # 检测状态
        current_state = self.detect_qcli_state(raw_message)
        
        # 更新状态跟踪
        self.last_state = current_state
        
        # 清理内容
        cleaned_content = self.clean_qcli_output(raw_message)
        
        # 根据状态处理
        if current_state == QCLIState.INITIALIZING:
            metadata = self.extract_initialization_info(raw_message)
            return QCLIChunk(
                state=current_state,
                content=cleaned_content,
                is_content=False,
                metadata=metadata
            )
        
        elif current_state == QCLIState.THINKING:
            return QCLIChunk(
                state=current_state,
                content="Thinking...",  # 简化显示
                is_content=False
            )
        
        elif current_state == QCLIState.RESPONDING:
            is_content = self.is_response_content(raw_message, current_state)
            
            # 如果是回复开始，提取实际内容
            if self.response_start_pattern.search(raw_message):
                content = re.sub(r'.*?>\s*', '', cleaned_content).strip()
                cleaned_content = content if content else cleaned_content
            
            return QCLIChunk(
                state=current_state,
                content=cleaned_content,
                is_content=is_content
            )
        
        else:
            return QCLIChunk(
                state=current_state,
                content=cleaned_content,
                is_content=False
            )
    
    def reset(self):
        """重置格式化器状态"""
        self.last_state = QCLIState.INITIALIZING

# 全局实例
qcli_formatter = QcliOutputFormatter()

# 便捷函数
def clean_qcli_text(text: str) -> str:
    """清理 Q CLI 文本的便捷函数 """
    return qcli_formatter.clean_qcli_output(text)

def process_qcli_chunk(raw_message: str) -> QCLIChunk:
    """处理 Q CLI 消息块的便捷函数"""
    return qcli_formatter.process_qcli_chunk(raw_message)
