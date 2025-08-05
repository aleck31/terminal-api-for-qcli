#!/usr/bin/env python3
"""
Command Executor
专注命令生命周期管理：发送命令、检测完成、收集原始结果
不负责数据清理和格式化，这些由 OutputProcessor 处理
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
    raw_output: str          # 原始输出（未清理）
    success: bool
    execution_time: float
    error: Optional[str] = None
    
    @classmethod
    def create_error_result(cls, command: str, error_msg: str, execution_time: float = 0.0) -> 'CommandResult':
        """创建错误结果"""
        return cls(
            command=command,
            raw_output="",
            success=False,
            execution_time=execution_time,
            error=error_msg
        )

class CommandExecution:
    """命令执行状态"""
    def __init__(self, command: str):
        self.command = command
        self.start_time = time.time()
        self.complete_event = asyncio.Event()
        self.timeout_occurred = False
        
        # 原始输出收集
        self.raw_output_parts = []
        
    @property
    def execution_time(self) -> float:
        return time.time() - self.start_time
    
    @property
    def raw_output(self) -> str:
        return ''.join(self.raw_output_parts)

class CommandExecutor:
    """命令执行器 - 专注命令生命周期管理"""
    
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
        
        # 设置消息处理器 - 专门用于命令完成检测
        self.connection_manager.set_message_handler(self._handle_raw_message)
    
    def set_output_processor(self, output_processor):
        """设置输出处理器"""
        self.output_processor = output_processor
    
    def set_stream_callback(self, callback: Callable[[str], None]):
        """设置流式输出回调"""
        self.stream_callback = callback
    
    def _handle_raw_message(self, raw_output: str):
        """处理原始消息 - 只做命令完成检测和数据收集"""
        if not self.current_execution or not raw_output:
            return
        
        try:
            # 收集原始输出用于最终结果
            self.current_execution.raw_output_parts.append(raw_output)
            
            # 检测命令完成（使用原始数据）
            if self._is_command_complete(raw_output):
                self.current_execution.complete_event.set()
            
            # 如果有输出处理器，处理数据并调用回调
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
        """基于终端类型的命令完成检测 - 只处理原始数据"""
        if not raw_output or not self.current_execution:
            return False
        
        if self.terminal_type == TerminalType.QCLI:
            return self._is_qcli_command_complete(raw_output)
        else:
            return self._is_generic_command_complete(raw_output)
    
    def _is_qcli_command_complete(self, raw_output: str) -> bool:
        """Q CLI 命令完成检测"""
        if not self.current_execution:
            return False
        
        # Q CLI 的完成标志：出现单独的 ">" 提示符
        if '>' in raw_output and self.current_execution.execution_time > 2.0:
            # 简单检测：如果输出包含 ">" 且执行时间超过2秒
            logger.debug("检测到 Q CLI 命令完成")
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
    
    async def execute_command(self, command: str, timeout: float = ExecutionConstants.DEFAULT_TIMEOUT) -> CommandResult:
        """
        执行命令并等待结果
        
        Args:
            command: 要执行的命令
            timeout: 超时时间（秒）
            
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
            
            # 等待命令完成或超时
            try:
                await asyncio.wait_for(self.current_execution.complete_event.wait(), timeout=timeout)
            except asyncio.TimeoutError:
                logger.warning(f"命令执行超时: {command}")
                self.current_execution.timeout_occurred = True
            
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
            return CommandResult.create_error_result("", "无执行状态")
        
        success = not self.current_execution.timeout_occurred
        error = "命令执行超时" if self.current_execution.timeout_occurred else None
        
        return CommandResult(
            command=self.current_execution.command,
            raw_output=self.current_execution.raw_output,
            success=success,
            execution_time=self.current_execution.execution_time,
            error=error
        )
