#!/usr/bin/env python3
"""
Terminal API Client
基于ttyd提供简洁的终端API接口，支持流式输出
"""

import asyncio
import logging
import time
from typing import Optional, Callable, List
from dataclasses import dataclass
from enum import Enum

from .websocket_client import TtydWebSocketClient, TtydMessage
from .utils import format_terminal_output, clean_terminal_text, FormattedOutput

logger = logging.getLogger(__name__)

class TerminalState(Enum):
    """终端状态"""
    IDLE = "idle"
    BUSY = "busy"
    ERROR = "error"
    DISCONNECTED = "disconnected"

@dataclass
class CommandResult:
    """命令执行结果"""
    command: str
    output: str
    markdown: str  # Markdown 格式输出
    success: bool
    execution_time: float
    error: Optional[str] = None

class TerminalAPIClient:
    """Terminal API Client"""
    
    def __init__(self, host: str = "localhost", port: int = 7681,
                 username: str = "demo", password: str = "password123",
                 use_ssl: bool = False, format_output: bool = True):
        """
        初始化终端API客户端
        
        Args:
            host: ttyd服务器主机
            port: ttyd服务器端口
            username: 认证用户名
            password: 认证密码
            use_ssl: 是否使用SSL
            format_output: 是否格式化输出为 Markdown
        """
        self.host = host
        self.port = port
        self.username = username
        self.password = password
        self.use_ssl = use_ssl
        self.format_output = format_output
        
        # WebSocket客户端
        self.ws_client = TtydWebSocketClient(
            host=host, port=port, 
            username=username, password=password,
            use_ssl=use_ssl
        )
        
        # 状态管理
        self.state = TerminalState.DISCONNECTED
        
        # 输出缓冲
        self.output_buffer: List[str] = []
        self.max_buffer_size = 1000  # 限制缓冲区大小
        
        # 流式输出回调
        self.output_callback: Optional[Callable[[str], None]] = None
        self.error_callback: Optional[Callable[[Exception], None]] = None
        
        # 设置WebSocket消息处理器
        self.ws_client.set_message_handler(self._handle_message)
        self.ws_client.set_error_handler(self._handle_error)
        
        # 命令执行同步
        self._command_complete = asyncio.Event()
        self._command_output: List[str] = []
        self._command_timeout = False
        self._current_command: Optional[str] = None  # 当前执行的命令
        self._command_echo_removed = False  # 是否已移除命令回显
    
    @property
    def is_connected(self) -> bool:
        """检查是否已连接"""
        return self.ws_client.is_connected and self.state != TerminalState.DISCONNECTED
    
    def set_output_callback(self, callback: Callable[[str], None]):
        """设置流式输出回调函数"""
        self.output_callback = callback
    
    def set_error_callback(self, callback: Callable[[Exception], None]):
        """设置错误回调函数"""
        self.error_callback = callback
    
    def _set_state(self, new_state: TerminalState):
        """设置终端状态"""
        if self.state != new_state:
            old_state = self.state
            self.state = new_state
            logger.debug(f"终端状态变化: {old_state.value} -> {new_state.value}")
    
    def _handle_message(self, message: str):
        """处理WebSocket消息 - 支持流式清理"""
        try:
            # 消息已经是清理后的字符串
            output = message
            if not output:
                return
                
            # 添加到缓冲区
            self.output_buffer.append(output)
            
            # 限制缓冲区大小
            if len(self.output_buffer) > self.max_buffer_size:
                self.output_buffer = self.output_buffer[-self.max_buffer_size:]
            
            # 如果正在执行命令，进行流式处理
            if self.state == TerminalState.BUSY and self._current_command:
                # 添加到命令输出缓冲区
                self._command_output.append(output)
                
                # 流式清理和输出
                cleaned_output = self._process_stream_output(output)
                if cleaned_output and self.output_callback:
                    try:
                        self.output_callback(cleaned_output)
                    except Exception as e:
                        logger.error(f"流式输出回调出错: {e}")
                
                # 检测命令完成（基于 OSC 697 序列）
                if self._is_command_complete(output):
                    self._command_complete.set()
            
            logger.debug(f"收到终端输出: {repr(output[:100])}")
            
        except Exception as e:
            logger.error(f"处理消息时出错: {e}")
            self._handle_error(e)
    
    def _process_stream_output(self, output: str) -> str:
        """处理流式输出 - 实时清理命令回显"""
        if not output or not self._current_command:
            return output
        
        # 清理控制字符
        cleaned = clean_terminal_text(output)
        if not cleaned:
            return ""
        
        # 移除命令回显（只在第一次遇到时移除）
        if not self._command_echo_removed:
            command = self._current_command.strip()
            
            # 检查是否包含命令回显
            if command in cleaned:
                # 移除命令回显
                cleaned = cleaned.replace(command, "", 1)
                self._command_echo_removed = True
                logger.debug(f"移除命令回显: {command}")
        
        # 过滤掉 OSC 序列和其他噪音
        lines = cleaned.split('\n')
        filtered_lines = []
        
        for line in lines:
            line = line.strip()
            if not line:
                continue
            
            # 跳过 OSC 697 序列
            if '697;' in line:
                continue
            
            # 跳过提示符行
            if any(prompt in line for prompt in ['ubuntu@', '$ ', '# ']):
                continue
            
            filtered_lines.append(line)
        
        result = '\n'.join(filtered_lines)
        return result if result.strip() else ""
    
    def _is_command_complete(self, output: str) -> bool:
        """基于 OSC 697 序列的命令完成检测"""
        if not output:
            return False
        
        # 检查是否包含命令完成的 OSC 序列
        completion_indicators = [
            '697;NewCmd=',      # 新命令开始（最可靠的完成标志）
            '697;EndPrompt',    # 提示符结束
        ]
        
        for indicator in completion_indicators:
            if indicator in output:
                logger.debug(f"检测到命令完成，OSC 标志: {indicator}")
                return True
        
        return False
    
    def _handle_error(self, error: Exception):
        """处理错误"""
        logger.error(f"终端API客户端错误: {error}")
        self._set_state(TerminalState.ERROR)
        
        if self.error_callback:
            try:
                self.error_callback(error)
            except Exception as e:
                logger.error(f"错误回调出错: {e}")
    
    async def connect(self) -> bool:
        """连接到终端"""
        logger.info(f"连接到ttyd终端: {self.host}:{self.port}")
        
        try:
            success = await self.ws_client.connect()
            if success:
                self._set_state(TerminalState.IDLE)
                logger.info("终端连接成功")
                
                # 等待初始化完成
                await asyncio.sleep(1)
                return True
            else:
                self._set_state(TerminalState.ERROR)
                logger.error("终端连接失败")
                return False
                
        except Exception as e:
            logger.error(f"连接终端时出错: {e}")
            self._set_state(TerminalState.ERROR)
            self._handle_error(e)
            return False
    
    async def disconnect(self):
        """断开终端连接"""
        logger.info("断开终端连接")
        await self.ws_client.disconnect()
        self._set_state(TerminalState.DISCONNECTED)
    
    async def send_input(self, data: str) -> bool:
        """发送输入到终端"""
        if not self.is_connected:
            logger.error("终端未连接")
            return False
        
        return await self.ws_client.send_input(data)
    
    async def execute_command(self, command: str, timeout: float = 30.0) -> CommandResult:
        """
        执行命令并等待结果
        
        Args:
            command: 要执行的命令
            timeout: 超时时间（秒）
            
        Returns:
            CommandResult: 命令执行结果
        """
        if not self.is_connected:
            error_msg = "终端未连接"
            return CommandResult(
                command=command,
                output="",
                markdown=f"## ❌ 命令执行失败\n**错误:** `{error_msg}`\n---",
                success=False,
                execution_time=0.0,
                error=error_msg
            )
        
        logger.info(f"执行命令: {command}")
        
        # 设置状态
        self._set_state(TerminalState.BUSY)
        start_time = time.time()
        
        # 初始化命令执行状态
        self._current_command = command
        self._command_echo_removed = False
        self._command_output.clear()
        self._command_complete.clear()
        self._command_timeout = False
        
        # 收集流式输出
        stream_output_parts = []
        
        def collect_stream_output(output: str):
            """收集流式输出"""
            if output:
                stream_output_parts.append(output)
        
        # 设置临时流式回调（如果用户没有设置的话）
        original_callback = self.output_callback
        if not self.output_callback:
            self.set_output_callback(collect_stream_output)
        
        try:
            # 发送命令
            success = await self.ws_client.send_command(command)
            if not success:
                raise Exception("发送命令失败")
            
            # 等待命令完成或超时
            try:
                await asyncio.wait_for(self._command_complete.wait(), timeout=timeout)
            except asyncio.TimeoutError:
                logger.warning(f"命令执行超时: {command}")
                self._command_timeout = True
            
            # 计算执行时间和状态
            execution_time = time.time() - start_time
            success = not self._command_timeout
            error = "命令执行超时" if self._command_timeout else None
            
            # 使用流式输出作为最终输出
            final_output = '\n'.join(stream_output_parts).strip()
            
            # 格式化输出
            if self.format_output:
                formatted = format_terminal_output(
                    raw_output=final_output,
                    command=command,
                    success=success,
                    execution_time=execution_time
                )
                markdown = formatted.markdown
            else:
                markdown = f"```\n{final_output}\n```" if final_output else "无输出"
            
            result = CommandResult(
                command=command,
                output=final_output,
                markdown=markdown,
                success=success,
                execution_time=execution_time,
                error=error
            )
            
            logger.info(f"命令执行完成: {command} (成功: {success}, 耗时: {execution_time:.2f}s)")
            return result
            
        except Exception as e:
            execution_time = time.time() - start_time
            error_msg = str(e)
            logger.error(f"执行命令时出错: {error_msg}")
            
            return CommandResult(
                command=command,
                output="",
                markdown=f"## ❌ 命令执行失败\n**错误:** `{error_msg}`\n**执行时间:** {execution_time:.2f}秒\n---",
                success=False,
                execution_time=execution_time,
                error=error_msg
            )
        
        finally:
            # 清理状态
            self._current_command = None
            self._command_echo_removed = False
            self._set_state(TerminalState.IDLE)
            
            # 恢复原始回调
            if not original_callback:
                self.set_output_callback(None)
    
    async def resize_terminal(self, rows: int, cols: int) -> bool:
        """调整终端大小"""
        if not self.is_connected:
            return False
        
        return await self.ws_client.resize_terminal(rows, cols)
    
    def get_output_buffer(self) -> str:
        """获取输出缓冲区内容"""
        return '\n'.join(self.output_buffer)
    
    def clear_output_buffer(self):
        """清空输出缓冲区"""
        self.output_buffer.clear()
    
    async def __aenter__(self):
        """异步上下文管理器入口"""
        await self.connect()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """异步上下文管理器出口"""
        await self.disconnect()
