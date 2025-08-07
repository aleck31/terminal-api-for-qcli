#!/usr/bin/env python3
"""
Terminal API Client
主要API接口 - 组合各个组件提供统一服务
职责：组件协调、状态管理、对外接口
"""

import asyncio
import logging
import json
from typing import Optional, Callable, Dict, Any, AsyncIterator
from enum import Enum
from dataclasses import dataclass

from .connection_manager import ConnectionManager
from .command_executor import CommandExecutor, CommandResult, TerminalType
from .output_processor import OutputProcessor

logger = logging.getLogger(__name__)

class TerminalState(Enum):
    """终端状态"""
    DISCONNECTED = "disconnected"
    CONNECTING = "connecting"
    IDLE = "idle"
    BUSY = "busy"
    ERROR = "error"

@dataclass
class EnhancedCommandResult:
    """增强的命令执行结果"""
    command: str
    output: str                     # 清理后的输出
    formatted_output: Dict[str, Any]  # JSON 格式的格式化输出
    success: bool
    execution_time: float
    exit_code: int                  # 命令退出码 (0=成功, 非0=失败)
    error: Optional[str] = None

class TerminalAPIClient:
    """终端API客户端 - 主要接口"""
    
    def __init__(self, host: str = "localhost", port: int = 7681,
                 username: str = "demo", password: str = "password123",
                 use_ssl: bool = False, terminal_type: TerminalType = TerminalType.GENERIC,
                 format_output: bool = True):
        """
        初始化终端API客户端
        
        Args:
            host: 主机地址
            port: 端口
            username: 用户名
            password: 密码
            use_ssl: 是否使用SSL
            terminal_type: 终端类型
            format_output: 是否格式化输出
        """
        self.host = host
        self.port = port
        self.terminal_type = terminal_type
        self.format_output = format_output
        
        # 初始化组件
        self._connection_manager = ConnectionManager(
            host=host, port=port, username=username, password=password,
            use_ssl=use_ssl, terminal_type=terminal_type.value
        )
        
        self._command_executor = CommandExecutor(
            connection_manager=self._connection_manager,
            terminal_type=terminal_type
        )
        
        # 根据终端类型创建对应的 OutputProcessor
        from .output_processor import TerminalType as ProcessorTerminalType
        processor_type = ProcessorTerminalType.QCLI if terminal_type == TerminalType.QCLI else ProcessorTerminalType.BASH
        
        self._output_processor = OutputProcessor(
            terminal_type=processor_type,
            enable_formatting=format_output
        )
        
        # 将 OutputProcessor 注入到 CommandExecutor
        self._command_executor.set_output_processor(self._output_processor)
        
        # 状态管理
        self.state = TerminalState.DISCONNECTED
        
        # 流式输出回调（向后兼容）
        self.output_callback: Optional[Callable[[str], None]] = None
        self.error_callback: Optional[Callable[[Exception], None]] = None
        
        # 设置错误处理器
        self._connection_manager.set_error_handler(self._handle_error)
    
    @property
    def is_connected(self) -> bool:
        """检查连接状态"""
        return self._connection_manager.is_connected and self.state != TerminalState.DISCONNECTED
    
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
    
    def _handle_error(self, error: Exception):
        """处理错误"""
        logger.error(f"终端错误: {error}")
        self._set_state(TerminalState.ERROR)
        
        if self.error_callback:
            try:
                self.error_callback(error)
            except Exception as e:
                logger.error(f"错误回调出错: {e}")
    
    async def connect(self, force_new: bool = False) -> bool:
        """
        连接到终端
        
        Args:
            force_new: 保留参数以保持API兼容性
        """
        logger.info(f"连接到ttyd终端: {self.host}:{self.port}")
        
        try:
            self._set_state(TerminalState.CONNECTING)
            
            success = await self._connection_manager.connect()
            if success:
                self._set_state(TerminalState.IDLE)
                logger.info("终端连接成功")
                
                # 终端初始化
                await self._initialize_terminal()
                
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
        """断开连接"""
        logger.info("断开终端连接")
        
        try:
            await self._connection_manager.disconnect()
            self._set_state(TerminalState.DISCONNECTED)
            
            # 清理状态
            self._output_processor.clear_all_states()
            
            logger.info("终端连接已断开")
        except Exception as e:
            logger.error(f"断开连接时出错: {e}")
    
    async def execute_command_stream(self, command: str, silence_timeout: float = 30.0) -> AsyncIterator[Dict[str, Any]]:
        """
        执行命令并返回流式输出（异步迭代器）
        
        Args:
            command: 要执行的命令
            silence_timeout: 静默超时时间（秒）- 只有完全无响应时才超时
            
        Yields:
            Dict: 每个流式输出块，包含 content, state, metadata 等信息
        """
        # 设置状态
        self._set_state(TerminalState.BUSY)
        
        try:
            # 创建队列来收集流式输出
            output_queue = asyncio.Queue()
            command_complete = asyncio.Event()
            
            def stream_handler(raw_chunk: str):
                """处理流式输出块"""
                try:
                    # 处理输出块
                    processed_chunk = self._output_processor.process_stream_output(
                        raw_output=raw_chunk,
                        command=command
                    )
                    
                    # 生成格式化的流式块
                    if self.terminal_type == TerminalType.QCLI:
                        qcli_chunk = self._output_processor.process_qcli_chunk(raw_chunk)
                        
                        stream_chunk = {
                            "content": processed_chunk,
                            "state": qcli_chunk.state.value,
                            "metadata": qcli_chunk.metadata or {},
                            "is_content": qcli_chunk.is_content,
                            "raw_length": len(raw_chunk)
                        }
                    else:
                        stream_chunk = {
                            "content": processed_chunk,
                            "terminal_type": self.terminal_type.value,
                            "raw_length": len(raw_chunk)
                        }
                    
                    # 放入队列
                    output_queue.put_nowait(stream_chunk)
                    
                except Exception as e:
                    logger.error(f"处理流式输出时出错: {e}")
            
            # 设置流式回调
            self._command_executor.set_stream_callback(stream_handler)
            
            # 启动命令执行任务
            async def execute_task():
                try:
                    result = await self._command_executor.execute_command(command, silence_timeout)
                    # 命令完成，发送完成信号
                    output_queue.put_nowait({"_command_complete": True, "result": result})
                except Exception as e:
                    output_queue.put_nowait({"_command_error": True, "error": str(e)})
                finally:
                    command_complete.set()
            
            # 启动执行任务
            execute_task_handle = asyncio.create_task(execute_task())
            
            # 流式返回输出
            while True:
                try:
                    # 等待输出或超时
                    chunk = await asyncio.wait_for(output_queue.get(), timeout=1.0)
                    
                    # 检查是否是控制消息
                    if "_command_complete" in chunk:
                        # 命令完成，发送最终状态
                        final_result = chunk["result"]
                        yield {
                            "content": "",
                            "state": "complete",
                            "command_success": final_result.success,
                            "execution_time": final_result.execution_time,
                            "error": final_result.error
                        }
                        break
                    elif "_command_error" in chunk:
                        # 命令出错
                        yield {
                            "content": "",
                            "state": "error",
                            "error": chunk["error"]
                        }
                        break
                    else:
                        # 正常的流式输出块
                        yield chunk
                        
                except asyncio.TimeoutError:
                    # 检查命令是否已完成
                    if command_complete.is_set():
                        break
                    # 继续等待
                    continue
                    
        finally:
            self._set_state(TerminalState.IDLE)
    
    async def send_input(self, data: str) -> bool:
        """
        发送输入数据
        
        Args:
            data: 要发送的数据
            
        Returns:
            bool: 是否发送成功
        """
        return await self._connection_manager.send_input(data)
    
    async def _initialize_terminal(self):
        """初始化终端 - 统一方法"""
        if self.terminal_type == TerminalType.QCLI:
            logger.info("⏳ Q CLI 连接就绪，可以发送消息")
        else:
            logger.info("⏳ 终端连接就绪，可以发送命令")
        
        # 简单等待，让初始消息处理完成
        await asyncio.sleep(1)
        
        # 检查连接是否仍然活跃
        if not self.is_connected:
            terminal_name = "Q CLI" if self.terminal_type == TerminalType.QCLI else "终端"
            raise ConnectionError(f"{terminal_name}连接在初始化过程中断开")
    
    # 异步上下文管理器支持
    async def __aenter__(self):
        """异步上下文管理器入口"""
        await self.connect()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """异步上下文管理器出口"""
        await self.disconnect()
