#!/usr/bin/env python3
"""
消息处理器 - 处理和格式化终端输出消息
"""

import time
import re
from typing import Dict, Any, Tuple, List
from dataclasses import dataclass
from datetime import datetime

@dataclass
class CommandExecution:
    """命令执行信息"""
    command: str
    start_time: datetime
    end_time: datetime = None
    return_code: int = None
    status: str = "running"  # running, success, failed, error
    stdout_lines: int = 0
    stderr_lines: int = 0
    
    @property
    def duration(self) -> float:
        """执行时长（秒）"""
        if self.end_time:
            return (self.end_time - self.start_time).total_seconds()
        return (datetime.now() - self.start_time).total_seconds()

class MessageProcessor:
    """消息处理器 - 处理WebSocket消息并格式化输出"""
    
    def __init__(self):
        self.current_execution: CommandExecution = None
        self.stdout_buffer = []
        self.stderr_buffer = []
        
        # 危险命令列表
        self.dangerous_commands = [
            'rm -rf', 'sudo rm', 'mkfs', 'dd if=', 'format', 
            ':(){ :|:& };:', 'chmod -R 777 /', 'chown -R'
        ]
        
        # 更全面的ANSI转义序列正则表达式
        self.ansi_escape = re.compile(r'\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~]|\d+|\w)')
    
    def is_dangerous_command(self, command: str) -> bool:
        """检查是否为危险命令"""
        command_lower = command.lower().strip()
        return any(dangerous in command_lower for dangerous in self.dangerous_commands)
    
    def clean_ansi_codes(self, text: str) -> str:
        """彻底清理ANSI代码和控制字符"""
        # 1. 清理ANSI转义序列
        text = self.ansi_escape.sub('', text)
        
        # 2. 清理其他控制字符（除了基本的空白字符）
        control_chars = re.compile(r'[\x00-\x08\x0B-\x1F\x7F-\x9F]')
        text = control_chars.sub('', text)
        
        # 3. 清理多余的空白
        text = re.sub(r'\s+', ' ', text).strip()
        
        return text
    
    def start_command_execution(self, command: str) -> Tuple[str, str, Dict[str, Any]]:
        """开始命令执行"""
        # 安全检查
        if self.is_dangerous_command(command):
            return ("error", "⚠️ 危险命令已被阻止执行", {"title": "🚫 安全拦截"})
        
        # 创建执行记录
        self.current_execution = CommandExecution(
            command=command,
            start_time=datetime.now()
        )
        
        # 清空缓冲区
        self.stdout_buffer.clear()
        self.stderr_buffer.clear()
        
        return ("status", f"正在执行命令: `{command}`", {
            "title": "🔄 执行中...",
            "status": "pending"
        })
    
    def process_websocket_message(self, message: Dict[str, Any]) -> Tuple[str, str, Dict[str, Any]]:
        """处理WebSocket消息"""
        msg_type = message.get("type", "")
        data = message.get("data", "")
        
        if not data.strip():
            return None
        
        # 清理ANSI代码
        clean_data = self.clean_ansi_codes(data).strip()
        
        if msg_type == "output":
            # 标准输出
            self.stdout_buffer.append(clean_data)
            if self.current_execution:
                self.current_execution.stdout_lines = len(self.stdout_buffer)
            
            return ("stdout", clean_data, {})
            
        elif msg_type == "error":
            # 错误输出
            self.stderr_buffer.append(clean_data)
            if self.current_execution:
                self.current_execution.stderr_lines = len(self.stderr_buffer)
            
            return ("stderr", clean_data, {"title": "⚠️ 错误输出"})
            
        else:
            # 其他类型消息，当作标准输出处理
            self.stdout_buffer.append(clean_data)
            if self.current_execution:
                self.current_execution.stdout_lines = len(self.stdout_buffer)
            
            return ("stdout", clean_data, {})
    
    def finish_command_execution(self, return_code: int = 0) -> Tuple[str, Dict[str, Any], Dict[str, Any]]:
        """完成命令执行"""
        if not self.current_execution:
            return ("error", "没有正在执行的命令", {"title": "❌ 执行错误"})
        
        # 更新执行信息
        self.current_execution.end_time = datetime.now()
        self.current_execution.return_code = return_code
        self.current_execution.status = "success" if return_code == 0 else "failed"
        
        # 生成执行摘要
        summary_data = {
            "command": self.current_execution.command,
            "return_code": self.current_execution.return_code,
            "status": self.current_execution.status,
            "stdout_lines": self.current_execution.stdout_lines,
            "stderr_lines": self.current_execution.stderr_lines,
            "duration": self.current_execution.duration
        }
        
        status_icon = "✅" if self.current_execution.status == "success" else "❌"
        summary_title = f"{status_icon} 执行完成"
        
        metadata = {
            "title": summary_title,
            "duration": self.current_execution.duration,
            "status": "done"
        }
        
        return ("summary", summary_data, metadata)
    
    def format_summary(self, summary: Dict[str, Any]) -> str:
        """格式化执行摘要"""
        status_icon = "✅" if summary["status"] == "success" else "❌"
        status_text = "成功" if summary["status"] == "success" else "失败"
        
        result = f"**命令执行摘要**\n\n"
        result += f"- 命令: `{summary['command']}`\n"
        result += f"- 返回码: {summary['return_code']}\n"
        result += f"- 状态: {status_icon} {status_text}\n"
        result += f"- 执行时间: {summary['duration']:.2f}秒\n"
        
        if summary["stdout_lines"] > 0:
            result += f"- 标准输出: {summary['stdout_lines']} 行\n"
        if summary["stderr_lines"] > 0:
            result += f"- 错误输出: {summary['stderr_lines']} 行\n"
        
        return result
    
    def get_current_execution_info(self) -> Dict[str, Any]:
        """获取当前执行信息"""
        if not self.current_execution:
            return {}
        
        return {
            "command": self.current_execution.command,
            "status": self.current_execution.status,
            "duration": self.current_execution.duration,
            "stdout_lines": self.current_execution.stdout_lines,
            "stderr_lines": self.current_execution.stderr_lines
        }