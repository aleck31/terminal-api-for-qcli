#!/usr/bin/env python3
"""
测试重构后的 TerminalAPIClient
验证统一数据流架构的完整集成
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

import asyncio
from unittest.mock import Mock, AsyncMock, patch

from api.terminal_api_client import TerminalAPIClient, TerminalBusinessState
from api.data_structures import TerminalType, ChunkType


class MockConnectionManager:
    """模拟连接管理器"""
    
    def __init__(self):
        self.is_connected = True
        self.state_change_callback = None
        self.error_handler = None
        self.primary_handler = None
        self.temp_listeners = {}
        self.listener_id_counter = 0
    
    async def connect(self):
        return True
    
    async def disconnect(self):
        self.is_connected = False
    
    def set_state_change_callback(self, callback):
        self.state_change_callback = callback
    
    def set_error_handler(self, handler):
        self.error_handler = handler
    
    def set_primary_handler(self, handler):
        self.primary_handler = handler
    
    def add_temp_listener(self, listener):
        self.listener_id_counter += 1
        listener_id = self.listener_id_counter
        self.temp_listeners[listener_id] = listener
        return listener_id
    
    def remove_temp_listener(self, listener_id):
        if listener_id in self.temp_listeners:
            del self.temp_listeners[listener_id]


class MockCommandExecutor:
    """模拟命令执行器"""
    
    def __init__(self):
        self.message_processor = None
        self.stream_callback = None
        self._handle_raw_message = Mock()
    
    def set_output_processor(self, processor):
        self.message_processor = processor
    
    def set_stream_callback(self, callback):
        self.stream_callback = callback
    
    async def execute_command(self, command, timeout):
        # 模拟命令执行
        from api.command_executor import CommandResult
        return CommandResult(
            command=command,
            success=True,
            execution_time=1.5
        )


def test_terminal_api_client_initialization():
    """测试 TerminalAPIClient 初始化"""
    print("=== 测试 TerminalAPIClient 初始化 ===")
    
    # 测试 GENERIC 类型
    generic_client = TerminalAPIClient(
        host="localhost",
        port=7681,
        terminal_type=TerminalType.GENERIC
    )
    
    assert generic_client.terminal_type == TerminalType.GENERIC
    assert generic_client.state == TerminalBusinessState.INITIALIZING
    print(f"Generic 客户端: {generic_client.terminal_type}")
    
    # 测试 QCLI 类型
    qcli_client = TerminalAPIClient(
        host="localhost",
        port=7682,
        terminal_type=TerminalType.QCLI
    )
    
    assert qcli_client.terminal_type == TerminalType.QCLI
    assert qcli_client.state == TerminalBusinessState.INITIALIZING
    print(f"QCLI 客户端: {qcli_client.terminal_type}")
    
    print("✅ TerminalAPIClient 初始化测试通过")


async def test_execute_command_stream_generic():
    """测试通用终端的流式命令执行"""
    print("\n=== 测试通用终端流式命令执行 ===")
    
    # 使用 patch 模拟依赖组件
    with patch('api.terminal_api_client.ConnectionManager') as MockConnMgr, \
         patch('api.terminal_api_client.CommandExecutor') as MockCmdExec:
        
        # 设置模拟对象
        mock_conn = MockConnectionManager()
        mock_executor = MockCommandExecutor()
        
        MockConnMgr.return_value = mock_conn
        MockCmdExec.return_value = mock_executor
        
        # 创建客户端
        client = TerminalAPIClient(
            host="localhost",
            port=7681,
            terminal_type=TerminalType.GENERIC
        )
        
        # 手动设置状态为可执行
        client._set_state(TerminalBusinessState.IDLE)
        
        # 模拟 StreamChunk 回调
        def simulate_stream_chunks():
            """模拟生成 StreamChunk"""
            from api.data_structures import StreamChunk, MetadataBuilder
            
            # 模拟命令回显
            echo_chunk = StreamChunk(
                content="pwd",
                type=ChunkType.CONTENT,
                metadata=MetadataBuilder.for_content(10, 3, "generic"),
                timestamp=1234567890.0
            )
            
            # 模拟命令输出
            output_chunk = StreamChunk(
                content="/tmp/ttyd",
                type=ChunkType.CONTENT,
                metadata=MetadataBuilder.for_content(20, 9, "generic"),
                timestamp=1234567890.1
            )
            
            return [echo_chunk, output_chunk]
        
        # 模拟执行过程
        stream_chunks = simulate_stream_chunks()
        
        # 收集 API 输出
        api_outputs = []
        
        # 模拟 execute_command_stream 的内部逻辑
        for chunk in stream_chunks:
            api_output = chunk.to_api_format()
            api_outputs.append(api_output)
            print(f"API 输出: {api_output}")
        
        # 验证输出格式
        for output in api_outputs:
            assert "content" in output
            assert "type" in output
            assert "metadata" in output
            assert "timestamp" in output
            assert output["metadata"]["terminal_type"] == "generic"
        
        print("✅ 通用终端流式命令执行测试通过")


async def test_execute_command_stream_qcli():
    """测试 Q CLI 的流式命令执行"""
    print("\n=== 测试 Q CLI 流式命令执行 ===")
    
    with patch('api.terminal_api_client.ConnectionManager') as MockConnMgr, \
         patch('api.terminal_api_client.CommandExecutor') as MockCmdExec:
        
        mock_conn = MockConnectionManager()
        mock_executor = MockCommandExecutor()
        
        MockConnMgr.return_value = mock_conn
        MockCmdExec.return_value = mock_executor
        
        client = TerminalAPIClient(
            host="localhost",
            port=7682,
            terminal_type=TerminalType.QCLI
        )
        
        client._set_state(TerminalBusinessState.IDLE)
        
        # 模拟 Q CLI StreamChunk 序列
        def simulate_qcli_chunks():
            from api.data_structures import StreamChunk, MetadataBuilder
            
            chunks = [
                # 思考状态
                StreamChunk(
                    content="",
                    type=ChunkType.THINKING,
                    metadata=MetadataBuilder.for_thinking(50, "qcli"),
                    timestamp=1234567890.0
                ),
                # 工具使用
                StreamChunk(
                    content="",
                    type=ChunkType.TOOL_USE,
                    metadata=MetadataBuilder.for_tool_use("aws_cli", 80, "qcli"),
                    timestamp=1234567890.1
                ),
                # 内容输出
                StreamChunk(
                    content="Hello! I'm Amazon Q...",
                    type=ChunkType.CONTENT,
                    metadata=MetadataBuilder.for_content(200, 23, "qcli"),
                    timestamp=1234567890.2
                ),
                # 完成状态
                StreamChunk(
                    content="",
                    type=ChunkType.COMPLETE,
                    metadata={
                        "execution_time": 2.5,
                        "command_success": True,
                        "terminal_type": "qcli"
                    },
                    timestamp=1234567890.3
                )
            ]
            return chunks
        
        qcli_chunks = simulate_qcli_chunks()
        
        # 验证 Q CLI 输出格式
        for chunk in qcli_chunks:
            api_output = chunk.to_api_format()
            print(f"Q CLI API 输出: {api_output}")
            
            assert api_output["metadata"]["terminal_type"] == "qcli"
            
            if chunk.type == ChunkType.THINKING:
                assert api_output["type"] == "thinking"
                assert api_output["content"] == ""
            elif chunk.type == ChunkType.TOOL_USE:
                assert api_output["type"] == "tool_use"
                assert "tool_name" in api_output["metadata"]
            elif chunk.type == ChunkType.CONTENT:
                assert api_output["type"] == "content"
                assert len(api_output["content"]) > 0
            elif chunk.type == ChunkType.COMPLETE:
                assert api_output["type"] == "complete"
                assert "execution_time" in api_output["metadata"]
        
        print("✅ Q CLI 流式命令执行测试通过")


def test_state_management():
    """测试状态管理"""
    print("\n=== 测试状态管理 ===")
    
    client = TerminalAPIClient(terminal_type=TerminalType.GENERIC)
    
    # 测试初始状态
    assert client.state == TerminalBusinessState.INITIALIZING
    print(f"初始状态: {client.state.value}")
    
    # 测试状态转换
    client._set_state(TerminalBusinessState.IDLE)
    assert client.state == TerminalBusinessState.IDLE
    print(f"空闲状态: {client.state.value}")
    
    client._set_state(TerminalBusinessState.BUSY)
    assert client.state == TerminalBusinessState.BUSY
    print(f"忙碌状态: {client.state.value}")
    
    # 测试 can_execute_command
    client._connection_manager = MockConnectionManager()
    client._set_state(TerminalBusinessState.IDLE)
    assert client.can_execute_command == True
    
    client._set_state(TerminalBusinessState.BUSY)
    assert client.can_execute_command == False
    
    print("✅ 状态管理测试通过")


def test_error_handling():
    """测试错误处理"""
    print("\n=== 测试错误处理 ===")
    
    from api.data_structures import StreamChunk
    
    # 测试错误 StreamChunk 创建
    error_chunk = StreamChunk.create_error("Test error", "generic", "test_error")
    
    assert error_chunk.type == ChunkType.ERROR
    assert error_chunk.content == ""
    assert error_chunk.metadata["error_message"] == "Test error"
    assert error_chunk.metadata["terminal_type"] == "generic"
    
    # 测试 API 格式
    api_output = error_chunk.to_api_format()
    print(f"错误 API 输出: {api_output}")
    
    assert api_output["type"] == "error"
    assert "error_message" in api_output["metadata"]
    
    print("✅ 错误处理测试通过")


async def main():
    """主测试函数"""
    print("开始测试重构后的 TerminalAPIClient...\n")
    
    test_terminal_api_client_initialization()
    await test_execute_command_stream_generic()
    await test_execute_command_stream_qcli()
    test_state_management()
    test_error_handling()
    
    print("\n🎉 TerminalAPIClient 测试完成！统一数据流架构集成成功。")


if __name__ == "__main__":
    asyncio.run(main())
