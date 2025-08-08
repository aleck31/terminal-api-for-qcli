#!/usr/bin/env python3
"""
Command Executor
无状态的命令执行工具：发送命令、检测完成、收集结果
"""

import asyncio
import logging
import time
from typing import Optional, Callable
from dataclasses import dataclass
from enum import Enum

from .connection_manager import ConnectionManager

logger = logging.getLogger(__name__)

# 常量定义
class ExecutionConstants:
    """执行相关常量"""
    DEFAULT_TIMEOUT = 30.0
    QCLI_MAX_TIMEOUT = 120.0

class TerminalType(Enum):
    """终端类型"""
    GENERIC = "generic"
    QCLI = "qcli"

@dataclass
class CommandResult:
    """命令执行结果"""
    command: str
    success: bool
    execution_time: float
    error: Optional[str] = None
    
    @classmethod
    def create_error_result(cls, command: str, error_msg: str, execution_time: float = 0.0) -> 'CommandResult':
        """创建错误结果"""
        return cls(
            command=command,
            success=False,
            execution_time=execution_time,
            error=error_msg
        )

class CommandExecution:
    """命令执行上下文"""
    def __init__(self, command: str):
        self.command = command
        self.start_time = time.time()
        self.complete_event = asyncio.Event()
        self.timeout_occurred = False
        
        # 活跃性检测
        self.last_message_time = time.time()  # 最后收到消息的时间
        
        # 保存最后一个消息块（用于命令完成检测）
        self.last_chunk = ""
        
    @property
    def execution_time(self) -> float:
        return time.time() - self.start_time
    
    def update_activity(self):
        """更新活跃性时间戳"""
        self.last_message_time = time.time()
    
    def get_silence_duration(self) -> float:
        """获取静默时长"""
        return time.time() - self.last_message_time

class CommandExecutor:
    """无状态命令执行器"""
    
    def __init__(self, connection_manager: ConnectionManager, 
                 terminal_type: TerminalType = TerminalType.GENERIC):
        """
        初始化命令执行器
        
        Args:
            connection_manager: 连接管理器
            terminal_type: 终端类型
        """
        self.connection_manager = connection_manager
        self.terminal_type = terminal_type
        
        # 当前执行状态
        self.current_execution: Optional[CommandExecution] = None
        
        # 输出处理器（由外部注入）
        self.output_processor = None
        self.stream_callback: Optional[Callable[[str], None]] = None
    
    def set_output_processor(self, output_processor):
        """设置输出处理器"""
        self.output_processor = output_processor
    
    def set_stream_callback(self, callback: Callable[[str], None]):
        """设置流式输出回调"""
        self.stream_callback = callback
    
    def _handle_raw_message(self, raw_output: str):
        """处理原始消息"""
        if not self.current_execution or not raw_output:
            return
        
        try:
            # 更新活跃性时间戳（收到任何消息都算活跃）
            self.current_execution.update_activity()
            
            # 保存最后一个消息块用于命令完成检测
            self.current_execution.last_chunk = raw_output
            
            # 检测命令完成（使用当前消息块）
            if self._is_command_complete(raw_output):
                self.current_execution.complete_event.set()
            
            # 如果有输出处理器，处理数据并调用流式回调
            if self.output_processor:
                processed_output = self.output_processor.process_stream_output(
                    raw_output=raw_output,
                    command=self.current_execution.command
                )
                
                # 调用用户设置的流式回调
                if processed_output and self.stream_callback:
                    try:
                        self.stream_callback(processed_output)
                    except Exception as e:
                        logger.error(f"流式输出回调出错: {e}")
                        
        except Exception as e:
            logger.error(f"处理原始消息时出错: {e}")
    
    def _is_command_complete(self, raw_output: str) -> bool:
        """命令完成检测"""
        if not raw_output or not self.current_execution:
            return False
        
        if self.terminal_type == TerminalType.QCLI:
            return self._is_qcli_command_complete(raw_output)
        else:
            return self._is_generic_command_complete(raw_output)
    
    def _is_qcli_command_complete(self, raw_output: str) -> bool:
        """Q CLI 命令完成检测"""
        # Q CLI 完成标志：新提示符出现
        completion_indicators = [
            '\x1b[31m!\x1b[35m> \x1b(B\x1b[m',  # 新提示符（!>）
            '\x1b[31m!\x1b[35m>\x1b(B\x1b[m',   # 可能的变体
            '\x1b[35m> \x1b(B\x1b[m',   # 新提示符（>）
            '\x1b[35m>\x1b(B\x1b[m',    # 可能的变体
        ]
        
        for indicator in completion_indicators:
            if indicator in raw_output:
                logger.debug("检测到 Q CLI 命令完成：新提示符出现")
                return True
            return True
        
        # 超时保护
        if self.current_execution.execution_time > ExecutionConstants.QCLI_MAX_TIMEOUT:
            logger.warning("Q CLI 命令执行时间过长，强制完成")
            return True
        
        return False
    
    def _is_generic_command_complete(self, raw_output: str) -> bool:
        """通用终端命令完成检测（基于 OSC 697 序列）"""
        # 检查是否包含命令完成的 OSC 序列
        completion_indicators = [
            '\x1b]697;NewCmd=',      # 新命令开始
            '\x1b]697;EndPrompt',    # 提示符结束
            '\x1b]697;StartPrompt',  # 新提示符开始
        ]
        
        for indicator in completion_indicators:
            if indicator in raw_output:
                logger.debug(f"检测到通用终端命令完成，OSC 标志: {indicator}")
                return True
        
        return False
    
    async def execute_command(self, command: str, silence_timeout: float = 30.0) -> CommandResult:
        """
        执行命令并等待结果
        
        Args:
            command: 要执行的命令
            silence_timeout: 静默超时时间（秒）- 只有完全无响应时才超时
            
        Returns:
            CommandResult: 命令执行结果（包含原始输出）
        """
        if not self.connection_manager.is_connected:
            return CommandResult.create_error_result(command, "连接未建立")
        
        logger.info(f"执行命令: {command}")
        
        # 创建新的执行状态
        self.current_execution = CommandExecution(command)
        
        try:
            # 发送命令
            success = await self.connection_manager.send_command(command)
            if not success:
                raise Exception("发送命令失败")
            
            # 活跃性检测等待命令完成
            while not self.current_execution.complete_event.is_set():
                try:
                    # 等待命令完成事件，使用短超时进行周期性检查
                    await asyncio.wait_for(
                        self.current_execution.complete_event.wait(), 
                        timeout=1.0
                    )
                    break
                except asyncio.TimeoutError:
                    # 检查是否真正超时（静默时间过长）
                    silence_duration = self.current_execution.get_silence_duration()
                    if silence_duration > silence_timeout:
                        logger.warning(f"命令执行静默超时: {command} (静默 {silence_duration:.1f}s)")
                        self.current_execution.timeout_occurred = True
                        break
                    # 否则继续等待（Q CLI 仍在工作）
            
            # 生成结果
            return self._create_command_result()
            
        except Exception as e:
            logger.error(f"执行命令时出错: {e}")
            return CommandResult.create_error_result(
                command, str(e), self.current_execution.execution_time
            )
        finally:
            # 清理执行状态
            self.current_execution = None
    
    def _create_command_result(self) -> CommandResult:
        """创建命令执行结果"""
        if not self.current_execution:
            return CommandResult.create_error_result("", "无执行上下文")

        success = not self.current_execution.timeout_occurred
        error = None
        if self.current_execution.timeout_occurred:
            silence_duration = self.current_execution.get_silence_duration()
            error = f"命令执行静默超时 (静默 {silence_duration:.1f}s)"
        
        return CommandResult(
            command=self.current_execution.command,
            success=success,
            execution_time=self.current_execution.execution_time,
            error=error
        )
