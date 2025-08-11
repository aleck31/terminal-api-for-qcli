#!/usr/bin/env python3
"""
Command Executor
无状态的命令执行工具：发送命令、检测完成、收集结果
"""

import asyncio
import logging
import time
from typing import Optional, Callable, TYPE_CHECKING
from dataclasses import dataclass
from .connection_manager import ConnectionManager
from .data_structures import TerminalType

if TYPE_CHECKING:
    from .data_structures import StreamChunk

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
    
    @classmethod
    def create_success_result(cls, command: str, execution_time: float) -> 'CommandResult':
        """创建成功结果"""
        return cls(
            command=command,
            success=True,
            execution_time=execution_time,
            error=None
        )
    
    @classmethod
    def create_timeout_result(cls, command: str, execution_time: float, silence_duration: float) -> 'CommandResult':
        """创建超时结果"""
        error_msg = f"命令执行静默超时 (静默 {silence_duration:.1f}s)"
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
        self.message_processor = None
        self.stream_callback: Optional[Callable[['StreamChunk'], None]] = None
    
    def set_output_processor(self, message_processor):
        """设置输出处理器"""
        self.message_processor = message_processor
    
    def set_stream_callback(self, callback: Callable):
        """设置流式输出回调 - 现在接收 StreamChunk 对象"""
        self.stream_callback = callback
    
    def _handle_raw_message(self, raw_message: str):
        """处理原始消息 - 利用MessageProcessor的完成检测结果"""
        if not self.current_execution or not raw_message:
            return
        
        try:
            # 1. 更新活跃性时间戳（收到任何消息都算活跃）
            self.current_execution.update_activity()
            
            # 2. 使用MessageProcessor处理消息
            if not self.message_processor:
                logger.warning("MessageProcessor未设置，跳过消息处理")
                return
                
            stream_chunk = self.message_processor.process_raw_message(
                raw_message=raw_message,
                command=self.current_execution.command,
                terminal_type=self.terminal_type
            )
            
            # 3. 检查是否完成（利用MessageProcessor的检测结果）
            if stream_chunk and stream_chunk.type.value == "complete":
                logger.debug(f"检测到命令完成：{self.terminal_type.value}")
                
                # 注入执行时间到metadata中
                if self.current_execution:
                    stream_chunk.metadata["execution_time"] = self.current_execution.execution_time
                    stream_chunk.metadata["command_success"] = True  # 能检测到完成说明命令成功
                
                self.current_execution.complete_event.set()
            
            # 4. 调用StreamChunk回调
            if stream_chunk and self.stream_callback:
                try:
                    self.stream_callback(stream_chunk)
                except Exception as e:
                    logger.error(f"StreamChunk 回调出错: {e}")
                        
        except Exception as e:
            logger.error(f"处理原始消息时出错: {e}")
            # 发送错误 StreamChunk
            if self.stream_callback:
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
            if not self.current_execution:
                return CommandResult.create_error_result("", "无执行上下文")

            command = self.current_execution.command
            execution_time = self.current_execution.execution_time
            
            if self.current_execution.timeout_occurred:
                # 超时结果
                silence_duration = self.current_execution.get_silence_duration()
                return CommandResult.create_timeout_result(command, execution_time, silence_duration)
            else:
                # 成功结果
                return CommandResult.create_success_result(command, execution_time)
            
        except Exception as e:
            logger.error(f"执行命令时出错: {e}")
            return CommandResult.create_error_result(
                command, str(e), self.current_execution.execution_time if self.current_execution else 0.0
            )
        finally:
            # 清理执行状态
            self.current_execution = None
