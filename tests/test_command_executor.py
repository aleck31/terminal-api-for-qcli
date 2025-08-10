#!/usr/bin/env python3
"""
测试更新后的 CommandExecutor
验证 StreamChunk 回调接口和统一数据流架构
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

import asyncio
import time
from unittest.mock import Mock, AsyncMock

from api.command_executor import CommandExecutor
from api.message_processor import MessageProcessor
from api.data_structures import StreamChunk, ChunkType, TerminalType


class MockConnectionManager:
    """模拟连接管理器"""
    
    def __init__(self):
        self.is_connected = True
        self.sent_commands = []
    
    async def send_command(self, command: str) -> bool:
        """模拟发送命令"""
        self.sent_commands.append(command)
        return True


def test_stream_chunk_callback():
    """测试 StreamChunk 回调接口"""
    print("=== 测试 StreamChunk 回调接口 ===")
    
    # 创建模拟组件
    mock_conn_manager = MockConnectionManager()
    message_processor = MessageProcessor(TerminalType.GENERIC)
    
    # 创建 CommandExecutor
    executor = CommandExecutor(mock_conn_manager, TerminalType.GENERIC)
    executor.set_output_processor(message_processor)
    
    # 创建执行上下文（重要！）
    from api.command_executor import CommandExecution
    executor.current_execution = CommandExecution("test command")
    
    # 收集回调结果
    received_chunks = []
    
    def chunk_callback(chunk: StreamChunk):
        """StreamChunk 回调函数"""
        received_chunks.append(chunk)
        print(f"收到 StreamChunk: type={chunk.type.value}, content={repr(chunk.content[:50])}")
    
    executor.set_stream_callback(chunk_callback)
    
    # 模拟处理原始消息
    test_messages = [
        "echo 'Hello World'\r\n",
        "Hello World\r\n",
        "$ "  # 提示符
    ]
    
    for msg in test_messages:
        executor._handle_raw_message(msg)
    
    print(f"总共收到 {len(received_chunks)} 个 StreamChunk")
    
    # 验证回调结果
    for i, chunk in enumerate(received_chunks):
        print(f"{i+1}. {chunk.to_api_format()}")
        
        # 验证基本结构
        assert isinstance(chunk, StreamChunk)
        assert hasattr(chunk, 'content')
        assert hasattr(chunk, 'type')
        assert hasattr(chunk, 'metadata')
        assert hasattr(chunk, 'timestamp')
    
    print("✅ StreamChunk 回调接口测试通过")


def test_qcli_message_processing():
    """测试 Q CLI 消息处理"""
    print("\n=== 测试 Q CLI 消息处理 ===")
    
    # 创建 Q CLI 类型的组件 - 确保类型一致！
    mock_conn_manager = MockConnectionManager()
    
    # 重要：CommandExecutor 和 MessageProcessor 必须使用相同的终端类型
    executor = CommandExecutor(mock_conn_manager, TerminalType.QCLI)
    message_processor = MessageProcessor(TerminalType.QCLI)  # 与 CommandExecutor 类型一致
    
    executor.set_output_processor(message_processor)
    
    print(f"CommandExecutor 类型: {executor.terminal_type}")
    print(f"MessageProcessor 类型: {message_processor.terminal_type}")
    
    # 创建执行上下文（重要！）
    from api.command_executor import CommandExecution
    executor.current_execution = CommandExecution("test qcli command")
    
    # 收集不同类型的消息
    message_types = []
    all_chunks = []
    
    def type_collector(chunk: StreamChunk):
        message_types.append(chunk.type.value)
        all_chunks.append(chunk)
        print(f"Q CLI 消息: {chunk.type.value} - {repr(chunk.content[:30])}")
    
    executor.set_stream_callback(type_collector)
    
    # 模拟 Q CLI 消息序列
    qcli_messages = [
        "⠋ Thinking...",  # 思考状态
        "🛠️  Using tool: aws_cli",  # 工具使用
        "Here's information about AWS Lambda:",  # 内容
        "Lambda is a serverless compute service.",  # 更多内容
    ]
    
    for msg in qcli_messages:
        print(f"处理消息: {repr(msg)}")
        executor._handle_raw_message(msg)
    
    print(f"Q CLI 消息类型序列: {message_types}")
    
    # 打印详细信息用于调试
    for i, chunk in enumerate(all_chunks):
        print(f"  {i+1}. {chunk.to_api_format()}")
    
    # 验证包含预期的消息类型
    assert 'thinking' in message_types, f"应该包含思考状态，实际收到: {message_types}"
    assert 'tool_use' in message_types, f"应该包含工具使用，实际收到: {message_types}"
    assert 'content' in message_types, f"应该包含内容输出，实际收到: {message_types}"
    
    print("✅ Q CLI 消息处理测试通过")


def test_error_handling():
    """测试错误处理"""
    print("\n=== 测试错误处理 ===")
    
    mock_conn_manager = MockConnectionManager()
    
    # 创建一个会出错的 MessageProcessor
    class ErrorMessageProcessor:
        def process_raw_message(self, raw_message, command, terminal_type=None):
            raise Exception("模拟处理错误")
    
    executor = CommandExecutor(mock_conn_manager, TerminalType.GENERIC)
    executor.set_output_processor(ErrorMessageProcessor())
    
    # 创建执行上下文（重要！）
    from api.command_executor import CommandExecution
    executor.current_execution = CommandExecution("test error command")
    
    # 收集错误消息
    error_chunks = []
    
    def error_collector(chunk: StreamChunk):
        if chunk.type == ChunkType.ERROR:
            error_chunks.append(chunk)
            print(f"收到错误 StreamChunk: {chunk.metadata.get('error_message', 'Unknown error')}")
    
    executor.set_stream_callback(error_collector)
    
    # 触发错误
    executor._handle_raw_message("test message")
    
    # 验证错误处理
    assert len(error_chunks) > 0, "应该收到错误 StreamChunk"
    
    error_chunk = error_chunks[0]
    assert error_chunk.type == ChunkType.ERROR
    assert "error_message" in error_chunk.metadata
    
    print("✅ 错误处理测试通过")


def test_activity_and_completion_detection():
    """测试活跃性检测和完成检测"""
    print("\n=== 测试活跃性检测和完成检测 ===")
    
    mock_conn_manager = MockConnectionManager()
    message_processor = MessageProcessor(TerminalType.GENERIC)
    
    executor = CommandExecutor(mock_conn_manager, TerminalType.GENERIC)
    executor.set_output_processor(message_processor)
    
    # 创建执行上下文
    from api.command_executor import CommandExecution
    executor.current_execution = CommandExecution("test command")
    
    initial_time = executor.current_execution.last_message_time
    
    # 模拟消息处理
    executor._handle_raw_message("some output")
    
    # 验证活跃性更新
    assert executor.current_execution.last_message_time > initial_time, "活跃性时间应该更新"
    
    # 测试完成检测（使用通用终端的完成标志）
    completion_message = "\x1b]697;NewCmd=test\x07"  # OSC 序列
    executor._handle_raw_message(completion_message)
    
    # 验证完成检测
    assert executor.current_execution.complete_event.is_set(), "应该检测到命令完成"
    
    print("✅ 活跃性检测和完成检测测试通过")


async def test_full_command_execution():
    """测试完整的命令执行流程"""
    print("\n=== 测试完整命令执行流程 ===")
    
    mock_conn_manager = MockConnectionManager()
    message_processor = MessageProcessor(TerminalType.GENERIC)
    
    executor = CommandExecutor(mock_conn_manager, TerminalType.GENERIC)
    executor.set_output_processor(message_processor)
    
    # 收集执行过程中的所有 StreamChunk
    execution_chunks = []
    
    def execution_collector(chunk: StreamChunk):
        execution_chunks.append(chunk)
        print(f"执行过程: {chunk.type.value} - {repr(chunk.content[:30])}")
    
    executor.set_stream_callback(execution_collector)
    
    # 模拟完整的命令执行（不实际执行，只测试数据流）
    print("模拟命令执行数据流...")
    
    # 模拟命令输出序列
    command_output_sequence = [
        "pwd\r\n",  # 命令回显
        "/tmp/ttyd\r\n",  # 命令输出
        "\x1b]697;NewCmd=next\x07",  # 完成标志
    ]
    
    # 创建执行上下文
    from api.command_executor import CommandExecution
    executor.current_execution = CommandExecution("pwd")
    
    for output in command_output_sequence:
        executor._handle_raw_message(output)
        await asyncio.sleep(0.01)  # 模拟时间间隔
    
    print(f"执行过程中收到 {len(execution_chunks)} 个 StreamChunk")
    
    # 验证执行流程
    assert len(execution_chunks) > 0, "应该收到执行过程中的 StreamChunk"
    
    # 验证最终状态
    assert executor.current_execution.complete_event.is_set(), "命令应该完成"
    
    print("✅ 完整命令执行流程测试通过")


def main():
    """主测试函数"""
    print("开始测试更新后的 CommandExecutor...\n")
    
    test_stream_chunk_callback()
    test_qcli_message_processing()
    test_error_handling()
    test_activity_and_completion_detection()
    
    # 运行异步测试
    asyncio.run(test_full_command_execution())
    
    print("\n🎉 CommandExecutor 测试完成！StreamChunk 回调接口工作正常。")


if __name__ == "__main__":
    main()
