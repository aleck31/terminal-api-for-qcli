#!/usr/bin/env python3
"""
Q CLI State Detector - Q CLI 状态检测器
"""

import re
import time
import logging
from typing import Optional, Callable
from dataclasses import dataclass
from enum import Enum

logger = logging.getLogger(__name__)

class QCLIState(Enum):
    """Q CLI 状态枚举"""
    IDLE = "idle"
    COMMAND_ECHO = "command_echo"
    THINKING = "thinking"
    TOOL_USE = "tool_use"
    AI_RESPONSE = "ai_response"
    WAITING_INPUT = "waiting_input"

@dataclass
class QCLIStateChange:
    """Q CLI 状态变化事件"""
    from_state: QCLIState
    to_state: QCLIState
    timestamp: float
    trigger_content: str
    confidence: float = 1.0

class QCLIStateDetector:
    """简洁的 Q CLI 状态检测器"""
    
    def __init__(self):
        # 预编译正则表达式（性能优化）
        self.patterns = {
            'thinking_spinner': re.compile(r'[⠸⠼⠴⠦⠧⠇⠏⠋⠙⠹]'),
            'thinking_text': re.compile(r'Thinking\.\.\.', re.IGNORECASE),
            'tool_use_start': re.compile(r'🛠️\s*Using tool:', re.IGNORECASE),
            'tool_use_running': re.compile(r'●\s*Running\s+\w+', re.IGNORECASE),
            'response_start': re.compile(r'^>\s*[A-Za-z]', re.MULTILINE),
            'waiting_prompt': re.compile(r'^>\s*$', re.MULTILINE),
        }
        
        self.current_state = QCLIState.IDLE
        self.state_start_time = time.time()
        self.command_buffer = []
        self.recent_outputs = []
        self.state_change_callback: Optional[Callable[[QCLIStateChange], None]] = None
    
    def set_state_change_callback(self, callback: Callable[[QCLIStateChange], None]):
        """设置状态变化回调"""
        self.state_change_callback = callback
    
    def set_expected_command(self, command: str):
        """设置期望的命令，用于回显检测"""
        self.command_buffer = list(command.lower().strip())
    
    def process_output(self, output: str) -> QCLIState:
        """处理输出并检测状态变化"""
        if not output:
            return self.current_state
        
        self.recent_outputs.append(output)
        if len(self.recent_outputs) > 20:
            self.recent_outputs.pop(0)
        
        new_state = self._detect_state(output)
        
        if new_state != self.current_state:
            self._handle_state_change(self.current_state, new_state, output)
            self.current_state = new_state
            self.state_start_time = time.time()
        
        return self.current_state
    
    def _detect_state(self, output: str) -> QCLIState:
        """检测当前状态"""
        recent_text = ''.join(self.recent_outputs[-5:])
        
        # 检测 Thinking 状态
        if (self.patterns['thinking_spinner'].search(output) or 
            self.patterns['thinking_text'].search(output)):
            return QCLIState.THINKING
        
        # 检测 Tool Use 状态
        if (self.patterns['tool_use_start'].search(recent_text) or
            self.patterns['tool_use_running'].search(recent_text)):
            return QCLIState.TOOL_USE
        
        # 检测命令回显
        if self._is_command_echo(output):
            return QCLIState.COMMAND_ECHO
        
        # 检测等待输入状态
        if self.patterns['waiting_prompt'].search(output):
            return QCLIState.WAITING_INPUT
        
        # 检测 AI 响应状态
        if (self.current_state == QCLIState.WAITING_INPUT and 
            output.strip() and output not in ['>', ' ']):
            return QCLIState.AI_RESPONSE
        
        if (self.current_state == QCLIState.AI_RESPONSE and 
            output.strip() and not output.strip() == '>'):
            return QCLIState.AI_RESPONSE
        
        return self.current_state
    
    def _is_command_echo(self, output: str) -> bool:
        """检测是否为命令回显"""
        if not self.command_buffer or not output.strip():
            return False
        
        output_char = output.lower().strip()
        if (len(self.command_buffer) > 0 and output_char == self.command_buffer[0]):
            self.command_buffer.pop(0)
            return True
        
        return False
    
    def _handle_state_change(self, from_state: QCLIState, to_state: QCLIState, trigger_content: str):
        """处理状态变化"""
        if self.state_change_callback:
            state_change = QCLIStateChange(
                from_state=from_state,
                to_state=to_state,
                timestamp=time.time(),
                trigger_content=trigger_content
            )
            self.state_change_callback(state_change)
    
    def get_current_state(self) -> QCLIState:
        """获取当前状态"""
        return self.current_state
    
    def reset(self):
        """重置状态检测器"""
        self.current_state = QCLIState.IDLE
        self.state_start_time = time.time()
        self.command_buffer.clear()
        self.recent_outputs.clear()