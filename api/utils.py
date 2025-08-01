#!/usr/bin/env python3
"""
Utility components - 终端输出格式化工具
专门为 Gradio UI 提供友好的 Markdown 格式输出
"""

import re
from typing import List, Dict, Optional, Tuple
from dataclasses import dataclass

@dataclass
class FormattedOutput:
    """格式化后的输出"""
    markdown: str
    plain_text: str
    command: Optional[str] = None
    exit_code: Optional[int] = None

class TerminalOutputFormatter:
    """终端输出格式化器 - 转换为 Markdown 格式"""
    
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
        
        # 命令提示符模式
        self.prompt_patterns = [
            re.compile(r'^[a-zA-Z0-9_-]+@[a-zA-Z0-9_-]+:[^$#]*[$#]\s*'),  # user@host:path$ 
            re.compile(r'^[$#]\s*'),  # 简单提示符
            re.compile(r'^>>>\s*'),   # Python 提示符
            re.compile(r'^>\s*'),     # 其他提示符
        ]
    
    def clean_terminal_output(self, raw_output: str) -> str:
        """清理终端输出，移除控制序列"""
        if not raw_output:
            return ""
        
        text = raw_output
        
        # 1. 移除各种 OSC 序列和 shell 集成信息
        # OSC 697 序列（shell 集成信息）
        text = re.sub(r'697;[^697\n]*(?=697|$)', '', text)
        text = re.sub(r'697[^;\n]*', '', text)
        
        # 移除所有以分号开头的 shell 集成信息
        text = re.sub(r';[A-Za-z][A-Za-z0-9]*=[^\n]*', '', text)
        text = re.sub(r';[A-Za-z][A-Za-z0-9]*\n', '', text)
        text = re.sub(r';[A-Za-z][A-Za-z0-9]*$', '', text)
        
        # OSC 0 序列（窗口标题）
        text = re.sub(r'\x1b\]0;[^\x07]*\x07', '', text)
        
        # OSC 1337 序列（iTerm2 集成）
        text = re.sub(r'1337;[^\n]*', '', text)
        
        # 其他 OSC 序列
        text = self.osc_pattern.sub('', text)
        
        # 2. 移除 ANSI 转义序列
        text = self.ansi_escape.sub('', text)
        
        # 3. 处理回车符和特殊字符
        text = self.carriage_return.sub('', text)
        
        # 4. 移除其他控制字符（保留换行符和制表符）
        text = self.control_chars.sub('', text)
        
        # 5. 清理提示符相关的残留
        # 移除常见的提示符模式
        text = re.sub(r'ubuntu@[^:]*:[^$]*\$\s*', '', text)
        text = re.sub(r'StartPrompt[^\n]*', '', text)
        text = re.sub(r'EndPrompt[^\n]*', '', text)
        text = re.sub(r'NewCmd[^\n]*', '', text)
        text = re.sub(r'PreExec[^\n]*', '', text)
        text = re.sub(r'OSCLock[^\n]*', '', text)
        text = re.sub(r'OSCUnlock[^\n]*', '', text)
        
        # 6. 清理多余的空白和特殊字符
        text = re.sub(r'[;\s]*$', '', text, flags=re.MULTILINE)  # 移除行尾的分号和空白
        text = re.sub(r'^[;\s]*', '', text, flags=re.MULTILINE)  # 移除行首的分号和空白
        text = self.multiple_spaces.sub('  ', text)  # 最多保留2个空格
        text = self.multiple_newlines.sub('\n\n', text)  # 最多保留2个换行
        
        # 7. 移除空行和首尾空白
        lines = [line.strip() for line in text.split('\n') if line.strip() and not line.strip().startswith(';')]
        text = '\n'.join(lines)
        
        return text
    
    def extract_command_and_output(self, text: str) -> Tuple[Optional[str], str]:
        """提取命令和输出"""
        if not text:
            return None, ""
        
        lines = text.split('\n')
        if not lines:
            return None, text
        
        # 尝试识别第一行是否为命令
        first_line = lines[0].strip()
        
        # 检查是否匹配提示符模式
        for pattern in self.prompt_patterns:
            match = pattern.match(first_line)
            if match:
                # 提取命令（去除提示符部分）
                command = first_line[match.end():].strip()
                # 输出是剩余的行
                output_lines = lines[1:] if len(lines) > 1 else []
                output = '\n'.join(output_lines).strip()
                return command, output
        
        # 如果第一行看起来像命令（没有空格或常见命令）
        if (first_line and 
            not first_line.startswith(' ') and 
            len(first_line.split()) <= 5 and  # 命令通常不会太长
            any(first_line.startswith(cmd) for cmd in ['echo', 'ls', 'pwd', 'whoami', 'date', 'cat', 'grep', 'find'])):
            
            command = first_line
            output_lines = lines[1:] if len(lines) > 1 else []
            output = '\n'.join(output_lines).strip()
            return command, output
        
        # 否则整个文本都是输出
        return None, text
    
    def format_as_markdown(self, text: str, command: Optional[str] = None) -> str:
        """将文本格式化为 Markdown"""
        if not text and not command:
            return ""
        
        markdown_parts = []
        
        # 如果有命令，显示命令
        if command:
            markdown_parts.append(f"**命令:** `{command}`\n")
        
        # 如果有输出内容
        if text:
            # 检查是否为代码/结构化输出
            if self._looks_like_code_output(text):
                # 使用代码块格式
                markdown_parts.append("**输出:**")
                markdown_parts.append(f"```\n{text}\n```")
            else:
                # 使用普通文本格式
                markdown_parts.append("**输出:**")
                # 将每行作为引用块
                lines = text.split('\n')
                for line in lines:
                    if line.strip():
                        markdown_parts.append(f"> {line}")
                    else:
                        markdown_parts.append("")
        
        return '\n'.join(markdown_parts)
    
    def _looks_like_code_output(self, text: str) -> bool:
        """判断是否看起来像代码输出"""
        # 检查是否包含常见的代码输出特征
        code_indicators = [
            '/',  # 路径
            '=',  # 赋值或配置
            '{', '}',  # JSON/配置
            '[', ']',  # 数组/列表
            '|',  # 管道或表格
            'total',  # ls -la 输出
            'drwx', '-rw-',  # 文件权限
        ]
        
        return any(indicator in text for indicator in code_indicators)
    
    def format_command_result(self, raw_output: str, command: str = None, 
                            success: bool = True, execution_time: float = 0.0,
                            error: str = None) -> FormattedOutput:
        """格式化命令执行结果"""
        
        # 清理原始输出
        cleaned_output = self.clean_terminal_output(raw_output)
        
        # 提取命令和输出
        extracted_command, output_text = self.extract_command_and_output(cleaned_output)
        
        # 使用提供的命令或提取的命令
        final_command = command or extracted_command
        
        # 构建 Markdown 内容
        markdown_parts = []
        
        # 状态指示器
        status_icon = "✅" if success else "❌"
        status_text = "成功" if success else "失败"
        
        # 命令标题
        if final_command:
            markdown_parts.append(f"## {status_icon} 命令执行 - {status_text}")
            markdown_parts.append(f"**命令:** `{final_command}`")
        else:
            markdown_parts.append(f"## {status_icon} 终端输出")
        
        # 执行信息
        if execution_time > 0:
            markdown_parts.append(f"**执行时间:** {execution_time:.2f}秒")
        
        # 输出内容
        if output_text:
            if self._looks_like_code_output(output_text):
                markdown_parts.append("**输出:**")
                markdown_parts.append(f"```bash\n{output_text}\n```")
            else:
                markdown_parts.append("**输出:**")
                lines = output_text.split('\n')
                for line in lines:
                    if line.strip():
                        markdown_parts.append(f"> {line}")
        
        # 错误信息
        if error:
            markdown_parts.append(f"**错误:** `{error}`")
        
        # 分隔线
        markdown_parts.append("---")
        
        markdown_content = '\n'.join(markdown_parts)
        plain_text = output_text or ""
        
        return FormattedOutput(
            markdown=markdown_content,
            plain_text=plain_text,
            command=final_command,
            exit_code=0 if success else 1
        )
    
    def format_streaming_output(self, text: str) -> str:
        """格式化流式输出（实时显示）"""
        cleaned = self.clean_terminal_output(text)
        if not cleaned:
            return ""
        
        # 对于流式输出，使用简单的格式
        if len(cleaned) > 100:
            # 长输出使用代码块
            return f"```\n{cleaned}\n```"
        else:
            # 短输出使用引用
            return f"> {cleaned}"

# 全局实例
terminal_formatter = TerminalOutputFormatter()

# 便捷函数
def format_terminal_output(raw_output: str, command: str = None, 
                         success: bool = True, execution_time: float = 0.0,
                         error: str = None) -> FormattedOutput:
    """格式化终端输出的便捷函数"""
    return terminal_formatter.format_command_result(
        raw_output, command, success, execution_time, error
    )

def clean_terminal_text(text: str) -> str:
    """清理终端文本的便捷函数"""
    return terminal_formatter.clean_terminal_output(text)

def format_for_gradio(text: str) -> str:
    """为 Gradio 格式化文本的便捷函数"""
    return terminal_formatter.format_streaming_output(text)
    