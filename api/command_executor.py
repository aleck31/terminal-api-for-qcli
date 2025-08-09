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

from .connection_manager import ConnectionManager
from .data_structures import TerminalType

logger = logging.getLogger(__name__)

# 常量定义
class ExecutionConstants:
    """执行相关常量"""
    DEFAULT_TIMEOUT = 30.0
    QCLI_MAX_TIMEOUT = 120.0

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
    
    def set_stream_callback(self, callback: Callable):
        """设置流式输出回调 - 现在接收 StreamChunk 对象"""
        self.stream_callback = callback
    
    def _handle_raw_message(self, raw_message: str):
        """处理原始消息 - 基于统一数据流架构"""
        if not self.current_execution or not raw_message:
            return
        
        try:
            # 1. 更新活跃性时间戳（收到任何消息都算活跃）
            self.current_execution.update_activity()
            
            # 2. 保存最后一个消息块用于命令完成检测
            self.current_execution.last_chunk = raw_message
            
            # 3. 检测命令完成（基于原始数据）
            if self._is_command_complete(raw_message):
                self.current_execution.complete_event.set()
            
            # 4. 使用新的统一数据处理接口
            if self.output_processor:
                # 调用新的统一处理接口，传递正确的终端类型
                stream_chunk = self.output_processor.process_raw_message(
                    raw_message=raw_message,
                    command=self.current_execution.command,
                    terminal_type=self.terminal_type  # 传递 CommandExecutor 的终端类型
                )
                
                # 5. 调用 StreamChunk 回调
                if stream_chunk and self.stream_callback:
                    try:
                        self.stream_callback(stream_chunk)
                    except Exception as e:
                        logger.error(f"StreamChunk 回调出错: {e}")
                        
        except Exception as e:
            logger.error(f"处理原始消息时出错: {e}")
            # 发送错误 StreamChunk
            if self.output_processor and self.stream_callback:
                try:
                    from .data_structures import StreamChunk
                    error_chunk = StreamChunk.create_error(
                        str(e), 
                        self.terminal_type.value,
                        "message_processing_error"
                    )
                    self.stream_callback(error_chunk)
                except Exception as callback_error:
                    logger.error(f"发送错误 StreamChunk 失败: {callback_error}")
    
    def _is_command_complete(self, raw_message: str) -> bool:
        """命令完成检测 - 保持基于原始数据的检测逻辑"""
        if not raw_message or not self.current_execution:
            return False
        
        if self.terminal_type == TerminalType.QCLI:
            return self._is_qcli_command_complete(raw_message)
        else:
            return self._is_generic_command_complete(raw_message)
    
    def _is_qcli_command_complete(self, raw_message: str) -> bool:
        """Q CLI 命令完成检测 - 使用 QcliOutputFormatter 的统一检测"""
        if not hasattr(self, '_qcli_formatter'):
            from api.utils.qcli_formatter import QcliOutputFormatter
            self._qcli_formatter = QcliOutputFormatter()
        
        # 使用 QcliOutputFormatter 的完成检测
        _, is_complete = self._qcli_formatter.clean_and_detect_completion(raw_message)
        
        if is_complete:
            logger.debug("检测到 Q CLI 命令完成：新提示符出现")
            return True
        
        # 超时保护
        if self.current_execution.execution_time > ExecutionConstants.QCLI_MAX_TIMEOUT:
            logger.warning("Q CLI 命令执行时间过长，强制完成")
            return True
        
        return False
    
    def _is_generic_command_complete(self, raw_message: str) -> bool:
        """通用终端命令完成检测（基于 OSC 697 序列）"""
        # 检查是否包含命令完成的 OSC 序列
        completion_indicators = [
            '\x1b]697;NewCmd=',      # 新命令开始
            '\x1b]697;EndPrompt',    # 提示符结束
            '\x1b]697;StartPrompt',  # 新提示符开始
        ]
        
        for indicator in completion_indicators:
            if indicator in raw_message:
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
