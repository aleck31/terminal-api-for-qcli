#!/usr/bin/env python3
"""
Terminal API Client - 修复版本
基于ttyd提供简洁的终端API接口，专注核心功能
输出格式化为 Markdown 便于 Gradio UI 使用
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
    markdown: str  # 新增：Markdown 格式输出
    success: bool
    execution_time: float
    error: Optional[str] = None

class TerminalAPIClient:
    """Terminal API Client - 主要的终端API接口"""
    
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
        
        # 回调函数
        self.output_callback: Optional[Callable[[str], None]] = None
        self.error_callback: Optional[Callable[[Exception], None]] = None
        
        # 设置WebSocket消息处理器
        self.ws_client.set_message_handler(self._handle_message)
        self.ws_client.set_error_handler(self._handle_error)
        
        # 命令执行同步
        self._command_complete = asyncio.Event()
        self._command_output: List[str] = []
        self._command_timeout = False
    
    @property
    def is_connected(self) -> bool:
        """检查是否已连接"""
        return self.ws_client.is_connected and self.state != TerminalState.DISCONNECTED
    
    def set_output_callback(self, callback: Callable[[str], None]):
        """设置输出回调函数"""
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
        """处理WebSocket消息"""
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
            
            # 添加到命令输出（如果正在执行命令）
            if self.state == TerminalState.BUSY:
                self._command_output.append(output)
                
                # 检测命令完成（简单的提示符检测）
                if self._is_command_complete(output):
                    self._command_complete.set()
            
            # 调用输出回调
            if self.output_callback:
                try:
                    self.output_callback(output)
                except Exception as e:
                    logger.error(f"输出回调出错: {e}")
            
            logger.debug(f"收到终端输出: {repr(output[:100])}")
            
        except Exception as e:
            logger.error(f"处理消息时出错: {e}")
            self._handle_error(e)
    
    def _is_command_complete(self, output: str) -> bool:
        """简单的命令完成检测"""
        # 检测常见的提示符
        prompt_indicators = ['$ ', '# ', '>>> ', '> ', 'bash-', 'ubuntu@']
        return any(indicator in output for indicator in prompt_indicators)
    
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
            CommandResult: 命令执行结果（包含 Markdown 格式）
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
        
        # 清空命令输出缓冲区
        self._command_output.clear()
        self._command_complete.clear()
        self._command_timeout = False
        
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
            
            # 收集输出
            raw_output = '\n'.join(self._command_output)
            execution_time = time.time() - start_time
            success = not self._command_timeout
            error = "命令执行超时" if self._command_timeout else None
            
            # 格式化输出
            if self.format_output:
                formatted = format_terminal_output(
                    raw_output=raw_output,
                    command=command,
                    success=success,
                    execution_time=execution_time,
                    error=error
                )
                clean_output = formatted.plain_text
                markdown_output = formatted.markdown
            else:
                clean_output = clean_terminal_text(raw_output)
                markdown_output = f"```\n{clean_output}\n```"
            
            return CommandResult(
                command=command,
                output=clean_output,
                markdown=markdown_output,
                success=success,
                execution_time=execution_time,
                error=error
            )
            
        except Exception as e:
            logger.error(f"执行命令时出错: {e}")
            execution_time = time.time() - start_time
            error_msg = str(e)
            
            raw_output = '\n'.join(self._command_output)
            
            # 格式化错误输出
            if self.format_output:
                formatted = format_terminal_output(
                    raw_output=raw_output,
                    command=command,
                    success=False,
                    execution_time=execution_time,
                    error=error_msg
                )
                clean_output = formatted.plain_text
                markdown_output = formatted.markdown
            else:
                clean_output = clean_terminal_text(raw_output)
                markdown_output = f"## ❌ 命令执行失败\n**错误:** `{error_msg}`\n```\n{clean_output}\n```\n---"
            
            return CommandResult(
                command=command,
                output=clean_output,
                markdown=markdown_output,
                success=False,
                execution_time=execution_time,
                error=error_msg
            )
        finally:
            self._set_state(TerminalState.IDLE)
    
    async def execute_command_stream(self, command: str, 
                                   output_handler: Callable[[str], None],
                                   timeout: float = 30.0) -> CommandResult:
        """
        执行命令并流式处理输出
        
        Args:
            command: 要执行的命令
            output_handler: 输出处理函数
            timeout: 超时时间（秒）
            
        Returns:
            CommandResult: 命令执行结果
        """
        # 设置临时输出处理器
        original_callback = self.output_callback
        self.set_output_callback(output_handler)
        
        try:
            result = await self.execute_command(command, timeout)
            return result
        finally:
            # 恢复原始回调
            self.set_output_callback(original_callback)
    
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
