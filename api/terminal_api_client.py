#!/usr/bin/env python3
"""
Terminal API Client
主要API接口 - 组合各个组件提供统一服务
"""

import asyncio
import logging
import time
from typing import Optional, Callable, Dict, Any, AsyncIterator
from enum import Enum
from .connection_manager import ConnectionManager
from .command_executor import CommandExecutor
from .message_processor import MessageProcessor
from .data_structures import StreamChunk, ChunkType, TerminalType

logger = logging.getLogger(__name__)

class TerminalBusinessState(Enum):
    """终端业务状态"""
    INITIALIZING = "initializing"  # 初始化中
    IDLE = "idle"                  # 空闲，可以接受命令
    BUSY = "busy"                  # 忙碌中，正在执行命令
    ERROR = "error"                # 错误状态
    UNAVAILABLE = "unavailable"    # 不可用（连接断开等）

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
        
        # 创建对应的 MessageProcessor
        self._output_processor = MessageProcessor(terminal_type=terminal_type)
        
        # 将 MessageProcessor 注入到 CommandExecutor
        self._command_executor.set_output_processor(self._output_processor)
        
        # 状态管理
        self.state = TerminalBusinessState.INITIALIZING
        
        # 流式输出回调（向后兼容）
        self.output_callback: Optional[Callable[[str], None]] = None
        self.error_callback: Optional[Callable[[Exception], None]] = None
        
        # 设置错误处理器
        self._connection_manager.set_error_handler(self._handle_error)
        
        # 订阅连接状态变化
        self._connection_manager.set_state_change_callback(self._handle_connection_state_change)
    
    @property
    def is_connected(self) -> bool:
        """检查连接状态 - 委托给 ConnectionManager"""
        return self._connection_manager.is_connected
    
    @property
    def terminal_state(self) -> TerminalBusinessState:
        """获取当前终端状态"""
        return self.state
    
    @property
    def can_execute_command(self) -> bool:
        """检查是否可以执行命令"""
        return self.is_connected and self.state == TerminalBusinessState.IDLE
    
    def set_output_callback(self, callback: Callable[[str], None]):
        """设置流式输出回调函数"""
        self.output_callback = callback
    
    def set_error_callback(self, callback: Callable[[Exception], None]):
        """设置错误回调函数"""
        self.error_callback = callback
    
    def _set_state(self, new_state: TerminalBusinessState):
        """设置终端状态"""
        if self.state != new_state:
            old_state = self.state
            self.state = new_state
            logger.debug(f"终端状态变化: {old_state.value} -> {new_state.value}")
    
    def _handle_error(self, error: Exception):
        """处理错误"""
        logger.error(f"终端错误: {error}")
        self._set_state(TerminalBusinessState.ERROR)
        
        if self.error_callback:
            try:
                self.error_callback(error)
            except Exception as e:
                logger.error(f"错误回调出错: {e}")
    
    def _handle_connection_state_change(self, conn_state):
        """处理连接状态变化，映射为业务状态"""
        from .connection_manager import ConnectionState

        logger.debug(f"收到连接状态变化: {conn_state.value}")
        
        if conn_state == ConnectionState.CONNECTED:
            # 连接建立/恢复
            if self.state == TerminalBusinessState.UNAVAILABLE:
                self._set_state(TerminalBusinessState.IDLE)
                logger.info("连接恢复，终端状态从不可用恢复为空闲")
            
        elif conn_state in [ConnectionState.FAILED, ConnectionState.DISCONNECTED]:
            # 连接失败或断开 - 避免覆盖ERROR状态
            if self.state not in [TerminalBusinessState.ERROR, TerminalBusinessState.UNAVAILABLE]:
                self._set_state(TerminalBusinessState.UNAVAILABLE)
                logger.info(f"连接断开，终端状态设置为不可用")

    async def _consume_initialization_messages(self):
        """消费初始化消息(不对外显示初始化消息)"""
        initialization_complete = False
        message_count = 0
        
        if self.terminal_type == TerminalType.QCLI:
            # Q CLI 模式：等待提示符
            from api.utils.ansi_formatter import ansi_formatter
            
            def qcli_initialization_collector(raw_message):
                nonlocal initialization_complete, message_count
                message_count += 1

                # 基于 ChunkType 检测结束标志
                _, chunk_type = ansi_formatter.parse_qcli_output(raw_message)
                if chunk_type.value == "complete":
                    initialization_complete = True
                    logger.info(f"检测到 Q CLI 提示符，初始化完成")
            
            collector = qcli_initialization_collector
            logger.info("开始消费 Q CLI 初始化消息...")
            
        else:
            # GENERIC 模式：消费固定时间的消息
            start_time = asyncio.get_event_loop().time()
            consume_duration = 1.0  # 消费1秒的消息
            
            def generic_initialization_collector(raw_message):
                nonlocal initialization_complete, message_count
                message_count += 1
                
                # 检查是否已经消费足够长时间
                elapsed = asyncio.get_event_loop().time() - start_time
                if elapsed >= consume_duration:
                    initialization_complete = True
                    logger.info(f"GENERIC 终端初始化消费完成，丢弃了 {message_count} 条消息")
            
            collector = generic_initialization_collector
            logger.info(f"开始消费 GENERIC 终端初始化消息（{consume_duration}秒）...")
        
        # 设置消息处理器
        self._connection_manager.set_primary_handler(lambda msg: None)  # 临时处理器
        
        # 使用事件驱动：添加临时监听器，不影响主处理器
        listener_id = self._connection_manager.add_temp_listener(collector)
        
        initialization_start_time = asyncio.get_event_loop().time()
        
        try:
            # 等待直到检测到结束标志
            check_interval = 0.1  # 检查间隔
            
            while not initialization_complete:
                await asyncio.sleep(check_interval)

                if self.terminal_type == TerminalType.GENERIC:
                    elapsed = asyncio.get_event_loop().time() - initialization_start_time
                    if elapsed > 1.1:  # 设置 1.1 秒超时
                        logger.info(f"GENERIC 终端初始化完成. 已耗时 {elapsed:.1f}s")
                        break
                
                # Q CLI 进度报告（每3秒报告一次）
                if self.terminal_type == TerminalType.QCLI:
                    elapsed = asyncio.get_event_loop().time() - initialization_start_time
                    if int(elapsed) % 3 == 0 and elapsed > 0:
                        logger.info(f"Q CLI 初始化进行中... 已耗时 {elapsed:.1f}s")
            
            total_time = asyncio.get_event_loop().time() - initialization_start_time
            terminal_type_name = "Q CLI" if self.terminal_type == TerminalType.QCLI else "GENERIC"
            logger.info(f"{terminal_type_name} 初始化完成: 丢弃 {message_count} 条消息，耗时 {total_time:.1f}s")
            
        finally:
            # 使用事件驱动：移除临时监听器
            self._connection_manager.remove_temp_listener(listener_id)
            logger.debug("已移除初始化消息监听器")
    
    def _setup_normal_message_handling(self):
        """设置正常的消息处理流程"""
        # 使用事件驱动：设置主要处理器
        self._connection_manager.set_primary_handler(
            self._command_executor._handle_raw_message
        )
        logger.debug("已设置正常消息处理流程")
    
    async def initialize(self) -> bool:
        """
        初始化终端（包含网络连接建立和业务初始化）
        
        Returns:
            bool: 初始化是否成功
        """
        logger.info(f"初始化终端: {self.host}:{self.port}, 类型: {self.terminal_type.value}")
        
        try:
            # 1. 检查并建立网络连接
            if not self.is_connected:
                success = await self._connection_manager.connect()
                if not success:
                    self._set_state(TerminalBusinessState.ERROR)
                    logger.error("网络连接建立失败")
                    return False

            logger.info("网络连接成功")
            
            # 2. 消费初始化消息（所有终端类型都需要）
            self._set_state(TerminalBusinessState.INITIALIZING)
            await self._consume_initialization_messages()
            
            # 3. 设置正常的消息处理流程
            self._setup_normal_message_handling()
            
            # 4. 进入空闲状态，可以接受命令
            self._set_state(TerminalBusinessState.IDLE)
            logger.info("终端初始化完成，可以开始用户交互")
            
            return True
        except Exception as e:
            logger.error(f"初始化终端时出错: {e}")
            self._set_state(TerminalBusinessState.ERROR)
            self._handle_error(e)
            return False
    
    async def shutdown(self):
        """关闭终端（断开网络连接并重置业务状态）"""
        logger.info("关闭终端")
        self._set_state(TerminalBusinessState.UNAVAILABLE)
        await self._connection_manager.disconnect()
    
    async def execute_command_stream(self, command: str, silence_timeout: float = 30.0) -> AsyncIterator[Dict[str, Any]]:
        """
        执行命令并返回流式输出（异步迭代器）- 基于统一数据流架构
        
        Args:
            command: 要执行的命令
            silence_timeout: 静默超时时间（秒）- 只有完全无响应时才超时
            
        Yields:
            Dict: 每个流式输出块，统一的API格式
        """
        # 检查是否可以执行命令
        if not self.can_execute_command:
            error_msg = f"无法执行命令: 连接状态={self.is_connected}, 终端状态={self.state.value}"
            logger.error(error_msg)
            
            # 使用统一的错误格式
            error_chunk = StreamChunk.create_error(error_msg, self.terminal_type.value, "command_execution_error")
            yield error_chunk.to_api_format()
            return
        
        # 设置忙碌状态
        self._set_state(TerminalBusinessState.BUSY)
        
        try:
            # 使用简化的流式处理 - 基于 StreamChunk 回调
            stream_chunks = []
            command_complete = asyncio.Event()
            execution_error = None
            
            def stream_chunk_handler(chunk: StreamChunk):
                """StreamChunk 回调处理器 - 统一接口"""
                try:
                    # 直接收集 StreamChunk，稍后转换为 API 格式
                    stream_chunks.append(chunk)
                except Exception as e:
                    logger.error(f"StreamChunk 处理出错: {e}")
                    # 创建错误 StreamChunk
                    error_chunk = StreamChunk.create_error(str(e), self.terminal_type.value, "stream_processing_error")
                    stream_chunks.append(error_chunk)
            
            # 设置 StreamChunk 回调
            self._command_executor.set_stream_callback(stream_chunk_handler)
            
            # 启动命令执行任务
            async def execute_task():
                nonlocal execution_error
                try:
                    result = await self._command_executor.execute_command(command, silence_timeout)
                    
                    # 创建完成 StreamChunk
                    complete_chunk = StreamChunk(
                        content="",
                        type=ChunkType.COMPLETE,
                        metadata={
                            "execution_time": result.execution_time,
                            "command_success": result.success,
                            "terminal_type": self.terminal_type.value
                        },
                        timestamp=time.time()
                    )
                    stream_chunks.append(complete_chunk)
                    
                except Exception as e:
                    execution_error = e
                    error_chunk = StreamChunk.create_error(str(e), self.terminal_type.value, "command_execution_error")
                    stream_chunks.append(error_chunk)
                finally:
                    command_complete.set()
            
            # 启动执行任务
            execute_task_handle = asyncio.create_task(execute_task())
            
            # 流式输出处理 - 简化的轮询机制
            last_processed = 0
            
            while not command_complete.is_set() or last_processed < len(stream_chunks):
                # 处理新的 StreamChunk
                while last_processed < len(stream_chunks):
                    chunk = stream_chunks[last_processed]
                    last_processed += 1
                    
                    # 转换为 API 格式并输出
                    api_chunk = chunk.to_api_format()
                    yield api_chunk
                    
                    # 如果是完成或错误块，结束流式输出
                    if chunk.type in [ChunkType.COMPLETE, ChunkType.ERROR]:
                        return
                
                # 如果命令还在执行，短暂等待
                if not command_complete.is_set():
                    await asyncio.sleep(0.1)
                    
        finally:
            # 恢复空闲状态
            self._set_state(TerminalBusinessState.IDLE)
    
    # 异步上下文管理器支持
    async def __aenter__(self):
        """异步上下文管理器入口"""
        await self.initialize()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """异步上下文管理器出口"""
        await self.shutdown()
