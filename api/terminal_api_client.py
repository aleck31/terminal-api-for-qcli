#!/usr/bin/env python3
"""
Terminal API Client
主要API接口 - 组合各个组件提供统一服务
职责：组件协调、状态管理、对外接口
"""

import asyncio
import logging
import time
from typing import Optional, Callable, Dict, Any, AsyncIterator
from enum import Enum
from dataclasses import dataclass

from .connection_manager import ConnectionManager
from .command_executor import CommandExecutor, CommandResult, TerminalType
from .output_processor import OutputProcessor

logger = logging.getLogger(__name__)

class TerminalBusinessState(Enum):
    """终端业务状态"""
    INITIALIZING = "initializing"  # 初始化中
    IDLE = "idle"                  # 空闲，可以接受命令
    BUSY = "busy"                  # 忙碌中，正在执行命令
    ERROR = "error"                # 错误状态
    UNAVAILABLE = "unavailable"    # 不可用（连接断开等）

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
        processor_type = ProcessorTerminalType.QCLI if terminal_type == TerminalType.QCLI else ProcessorTerminalType.GENERIC
        
        self._output_processor = OutputProcessor(
            terminal_type=processor_type,
            enable_formatting=format_output
        )
        
        # 将 OutputProcessor 注入到 CommandExecutor
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
            # 连接失败或断开
            if self.state not in [TerminalBusinessState.ERROR, TerminalBusinessState.UNAVAILABLE]:
                self._set_state(TerminalBusinessState.UNAVAILABLE)
                logger.info(f"连接断开，终端状态设置为不可用")

    async def _consume_initialization_messages(self):
        """
        消费 Q CLI 初始化消息直到流结束 - 使用事件驱动模式
        
        基于活跃性检测，只要有消息持续输出就继续等待，
        只有在完全静默时才认为初始化完成，不设置硬性时间限制
        """
        messages = []
        silence_time = 3.0  # 静默检测时间
        
        # 设置临时监听器收集初始化消息
        def initialization_collector(msg):
            messages.append(msg)
        
        # 使用事件驱动：添加临时监听器，不影响主处理器
        listener_id = self._connection_manager.add_temp_listener(initialization_collector)
        
        logger.info("开始消费 Q CLI 初始化消息...")
        start_time = asyncio.get_event_loop().time()
        
        try:
            # 基于活跃性的初始化检测 - 只要有消息就继续等待
            last_count = 0
            last_progress_report = 0
            
            while True:
                await asyncio.sleep(silence_time)
                
                current_time = asyncio.get_event_loop().time()
                elapsed_time = current_time - start_time
                
                # 检查是否有新消息
                if len(messages) == last_count:
                    logger.info(f"检测到 {silence_time}s 无新消息，Q CLI 初始化流结束")
                    break
                
                # 定期报告初始化进度（每10秒报告一次，避免日志过多）
                if elapsed_time - last_progress_report >= 10.0:
                    logger.info(f"Q CLI 初始化进行中... 已耗时 {elapsed_time:.1f}s，收到 {len(messages)} 条消息")
                    last_progress_report = elapsed_time
                
                last_count = len(messages)
            
            total_time = asyncio.get_event_loop().time() - start_time
            logger.info(f"Q CLI 初始化完成: 丢弃 {len(messages)} 条消息，耗时 {total_time:.1f}s")
            
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
        初始化终端（包含网络连接建立和 Q CLI 业务初始化）
        
        Returns:
            bool: 初始化是否成功
        """
        logger.info(f"初始化终端: {self.host}:{self.port}")
        
        try:
            # 1. 检查并建立网络连接
            if not self.is_connected:
                success = await self._connection_manager.connect()
                if not success:
                    self._set_state(TerminalBusinessState.ERROR)
                    logger.error("网络连接建立失败")
                    return False

            logger.info("网络连接成功")
            
            # 2. 处理 Q CLI 业务初始化
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
        执行命令并返回流式输出（异步迭代器）
        
        Args:
            command: 要执行的命令
            silence_timeout: 静默超时时间（秒）- 只有完全无响应时才超时
            
        Yields:
            Dict: 每个流式输出块，包含 content, state, metadata 等信息
        """
        # 检查是否可以执行命令
        if not self.can_execute_command:
            error_msg = f"无法执行命令: 连接状态={self.is_connected}, 终端状态={self.state.value}"
            logger.error(error_msg)
            yield {
                "content": "",
                "state": "error",
                "is_content": False,
                "metadata": {"error": error_msg},
                "timestamp": time.time()
            }
            return
        
        # 设置忙碌状态
        self._set_state(TerminalBusinessState.BUSY)
        
        try:
            # 创建队列来收集流式输出
            output_queue = asyncio.Queue()
            command_complete = asyncio.Event()
            
            def stream_handler(raw_chunk: str):
                """处理流式输出块 - 优化版本"""
                try:
                    # 根据终端类型处理输出
                    if self.terminal_type == TerminalType.QCLI:
                        # Q CLI 特殊处理：使用状态检测
                        qcli_chunk = self._output_processor.process_qcli_chunk(raw_chunk)
                        
                        # 生成优化的流式块格式
                        stream_chunk = {
                            "content": qcli_chunk.content,
                            "state": qcli_chunk.state.value,
                            "is_content": qcli_chunk.is_content,
                            "metadata": self._build_qcli_metadata(qcli_chunk, raw_chunk),
                            "timestamp": time.time()
                        }
                    else:
                        # 通用终端处理
                        processed_content = self._output_processor.process_stream_output(
                            raw_output=raw_chunk,
                            command=command
                        )
                        
                        stream_chunk = {
                            "content": processed_content,
                            "terminal_type": self.terminal_type.value,
                            "is_content": bool(processed_content.strip()),
                            "metadata": {"raw_length": len(raw_chunk)},
                            "timestamp": time.time()
                        }
                    
                    # 放入队列
                    output_queue.put_nowait(stream_chunk)
                    
                except Exception as e:
                    logger.error(f"处理流式输出时出错: {e}")
                    # 发送错误块
                    error_chunk = {
                        "content": "",
                        "state": "error",
                        "is_content": False,
                        "metadata": {"error": str(e)},
                        "timestamp": time.time()
                    }
                    output_queue.put_nowait(error_chunk)
            
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
            
            # 流式输出处理循环
            while not command_complete.is_set() or not output_queue.empty():
                try:
                    # 等待输出或超时
                    chunk = await asyncio.wait_for(output_queue.get(), timeout=1.0)
                    
                    # 检查是否是控制消息
                    if isinstance(chunk, dict) and "_command_complete" in chunk:
                        # 发送最终完成块
                        final_chunk = {
                            "content": "",
                            "state": "complete",
                            "is_content": False,
                            "metadata": {"final": True},
                            "timestamp": time.time()
                        }
                        yield final_chunk
                        break
                    elif isinstance(chunk, dict) and "_command_error" in chunk:
                        # 发送错误块
                        error_chunk = {
                            "content": "",
                            "state": "error", 
                            "is_content": False,
                            "metadata": {"error": chunk["error"], "final": True},
                            "timestamp": time.time()
                        }
                        yield error_chunk
                        break
                    else:
                        # 正常的流式输出块
                        yield chunk
                        
                except asyncio.TimeoutError:
                    # 超时检查，但继续等待
                    continue
                    
        finally:
            self._set_state(TerminalBusinessState.IDLE)
    
    def _build_qcli_metadata(self, qcli_chunk, raw_chunk: str) -> Dict[str, Any]:
        """构建 Q CLI 流式输出的元数据"""
        metadata = {
            "raw_length": len(raw_chunk),
            "content_length": len(qcli_chunk.content),
        }
        
        # 合并 chunk 自带的元数据
        if qcli_chunk.metadata:
            metadata.update(qcli_chunk.metadata)
        
        # 添加状态特定的元数据
        if qcli_chunk.state.value == "thinking":
            metadata["status_indicator"] = "🤔"
        elif qcli_chunk.state.value == "tool_use":
            metadata["status_indicator"] = "🔧"
        elif qcli_chunk.state.value == "streaming":
            metadata["status_indicator"] = "💬"
        elif qcli_chunk.state.value == "complete":
            metadata["status_indicator"] = "✅"
        
        return metadata
    
    # 异步上下文管理器支持
    async def __aenter__(self):
        """异步上下文管理器入口"""
        await self.initialize()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """异步上下文管理器出口"""
        await self.shutdown()
