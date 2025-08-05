#!/usr/bin/env python3
"""
Terminal API Client
主要API接口 - 组合各个组件提供统一服务
职责：组件协调、状态管理、对外接口
"""

import asyncio
import logging
from typing import Optional, Callable
from enum import Enum
from dataclasses import dataclass

from .connection_manager import ConnectionManager
from .command_executor import CommandExecutor, CommandResult, TerminalType
from .output_processor import OutputProcessor
from .qcli_state_detector import QCLIStateDetector, QCLIState, QCLIStateChange

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
    output: str              # 清理后的输出
    formatted_output: str    # 格式化后的输出
    success: bool
    execution_time: float
    exit_code: int           # 命令退出码 (0=成功, 非0=失败)
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
            use_ssl=use_ssl
        )
        
        self._command_executor = CommandExecutor(
            connection_manager=self._connection_manager,
            terminal_type=terminal_type
        )
        
        self._output_processor = OutputProcessor(
            enable_formatting=format_output
        )
        
        # 将 OutputProcessor 注入到 CommandExecutor
        self._command_executor.set_output_processor(self._output_processor)
        
        # 状态管理
        self.state = TerminalState.DISCONNECTED
        
        # 流式输出回调（向后兼容）
        self.output_callback: Optional[Callable[[str], None]] = None
        self.error_callback: Optional[Callable[[Exception], None]] = None
        
        # Q CLI 相关（特殊处理）
        self.qcli_detector: Optional[QCLIStateDetector] = None
        self.qcli_state_callback: Optional[Callable[[QCLIState, str], None]] = None
        
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
                
                # 根据终端类型进行初始化
                if self.terminal_type == TerminalType.QCLI:
                    await self._initialize_qcli()
                else:
                    await self._initialize_generic_terminal()
                
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
    
    async def execute_command(self, command: str, timeout: float = 30.0) -> EnhancedCommandResult:
        """
        执行命令并返回增强的结果
        
        Args:
            command: 要执行的命令
            timeout: 超时时间（秒）
            
        Returns:
            EnhancedCommandResult: 增强的命令执行结果
        """
        # 设置状态
        self._set_state(TerminalState.BUSY)
        
        try:
            # 设置流式输出回调
            if self.output_callback:
                self._command_executor.set_stream_callback(self.output_callback)
            
            # 使用命令执行器执行命令（返回原始结果）
            raw_result = await self._command_executor.execute_command(command, timeout)
            
            # 处理输出：基础清理
            cleaned_output = self._output_processor.process_raw_output(raw_result.raw_output)
            
            # 处理输出：移除命令回显
            formatted_output = cleaned_output
            if raw_result.command and raw_result.command in cleaned_output:
                formatted_output = cleaned_output.replace(raw_result.command, "", 1).strip()
            
            # 创建增强的结果
            return EnhancedCommandResult(
                command=raw_result.command,
                output=cleaned_output,
                formatted_output=formatted_output,
                success=raw_result.success,
                execution_time=raw_result.execution_time,
                exit_code=0 if raw_result.success else 1,  # 基于 success 推导
                error=raw_result.error
            )
            
        finally:
            # 恢复状态
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
    
    async def _initialize_qcli(self):
        """初始化 Q CLI"""
        logger.info("🔍 检测 Q CLI 状态...")
        
        # 检查是否是持久化会话（已经初始化完成）
        if await self._is_qcli_ready():
            logger.info("✅ 检测到 Q CLI 已就绪，跳过初始化等待")
            return
        
        # 如果不是持久化会话，需要等待初始化
        logger.info("⏳ 等待 Q CLI 加载 MCP 服务器...")
        
        # 分段等待，提供进度反馈
        total_wait = 30
        step = 5
        for i in range(0, total_wait, step):
            await asyncio.sleep(step)
            
            # 每次等待后检查是否已经就绪
            if await self._is_qcli_ready():
                logger.info(f"✅ Q CLI 提前就绪！耗时: {i + step}秒")
                return
                
            progress = ((i + step) / total_wait) * 100
            logger.info(f"📊 Q CLI 初始化进度: {progress:.0f}% ({i + step}/{total_wait}秒)")
        
        # 检查连接是否仍然活跃
        if not self.is_connected:
            raise ConnectionError("Q CLI 连接在初始化过程中断开")
    
    async def _initialize_generic_terminal(self):
        """初始化通用终端"""
        # 通用终端通常很快就绪
        await asyncio.sleep(2)
        
        # 检查连接是否活跃
        if not self.is_connected:
            raise ConnectionError("终端连接在初始化过程中断开")
    
    async def _is_qcli_ready(self) -> bool:
        """检测 Q CLI 是否已经就绪"""
        try:
            # 发送一个简单的测试命令
            result = await self._command_executor.execute_command("help", timeout=5.0)
            
            # 如果命令成功执行且输出包含帮助信息，说明 Q CLI 已就绪
            if result.success and result.raw_output:
                cleaned_output = self._output_processor.process_raw_output(result.raw_output)
                if any(keyword in cleaned_output.lower() for keyword in ['help', 'command', 'usage']):
                    return True
            
            return False
        except Exception as e:
            logger.debug(f"Q CLI 就绪检测失败: {e}")
            return False
    
    # 异步上下文管理器支持
    async def __aenter__(self):
        """异步上下文管理器入口"""
        await self.connect()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """异步上下文管理器出口"""
        await self.disconnect()
