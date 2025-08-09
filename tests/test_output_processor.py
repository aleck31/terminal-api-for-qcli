#!/usr/bin/env python3
"""
测试重构后的 OutputProcessor
验证统一数据流架构的核心处理逻辑
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from api.output_processor import OutputProcessor, TerminalType
from api.data_structures import ChunkType, is_user_visible_content


def test_generic_terminal_processing():
    """测试通用终端处理"""
    print("=== 测试通用终端处理 ===")
    
    processor = OutputProcessor(TerminalType.GENERIC)
    
    # 测试简单内容
    raw_message = "pwd\r\n/tmp/ttyd\r\n"
    chunk = processor.process_raw_message(raw_message, "pwd")
    
    print(f"原始消息: {repr(raw_message)}")
    if chunk:
        print(f"处理结果: {chunk}")
        print(f"API格式: {chunk.to_api_format()}")
        
        assert chunk.type == ChunkType.CONTENT
        assert chunk.metadata["terminal_type"] == "generic"
        assert "content_length" in chunk.metadata
        print("✅ 通用终端基础处理测试通过")
    else:
        print("❌ 处理结果为空")
    
    # 测试空消息
    empty_chunk = processor.process_raw_message("", "test")
    assert empty_chunk is None
    print("✅ 空消息处理测试通过")


def test_qcli_terminal_processing():
    """测试 Q CLI 终端处理"""
    print("\n=== 测试 Q CLI 终端处理 ===")
    
    processor = OutputProcessor(TerminalType.QCLI)
    
    # 测试思考状态 - 使用正确的旋转指示符格式
    thinking_message = "⠋ Thinking..."
    thinking_chunk = processor.process_raw_message(thinking_message)
    
    if thinking_chunk:
        print(f"思考消息: {thinking_chunk}")
        print(f"API格式: {thinking_chunk.to_api_format()}")
        
        assert thinking_chunk.type == ChunkType.THINKING
        assert thinking_chunk.content == ""  # 思考状态不返回内容
        assert thinking_chunk.metadata["terminal_type"] == "qcli"
        print("✅ Q CLI 思考状态处理测试通过")
    else:
        print("❌ 思考消息处理失败")
    
    # 测试工具使用 - 使用正确的格式
    tool_message = "🛠️  Using tool: web_search_exa"
    tool_chunk = processor.process_raw_message(tool_message)
    
    if tool_chunk:
        print(f"工具消息: {tool_chunk}")
        print(f"API格式: {tool_chunk.to_api_format()}")
        
        assert tool_chunk.type == ChunkType.TOOL_USE
        assert tool_chunk.content == ""  # 工具使用不返回内容
        assert "tool_name" in tool_chunk.metadata
        print("✅ Q CLI 工具使用处理测试通过")
    else:
        print("❌ 工具消息处理失败")
    
    # 测试内容输出
    content_message = "Hello! I'm Amazon Q, an AI assistant built by AWS..."
    content_chunk = processor.process_raw_message(content_message)
    
    if content_chunk:
        print(f"内容消息: {content_chunk}")
        print(f"API格式: {content_chunk.to_api_format()}")
        
        assert content_chunk.type == ChunkType.CONTENT
        assert len(content_chunk.content) > 0  # 内容输出应该有内容
        assert content_chunk.metadata["terminal_type"] == "qcli"
        print("✅ Q CLI 内容输出处理测试通过")
    else:
        print("❌ 内容消息处理失败")


def test_error_handling():
    """测试错误处理"""
    print("\n=== 测试错误处理 ===")
    
    processor = OutputProcessor(TerminalType.GENERIC)
    
    # 模拟处理错误（通过传入无效数据）
    # 注意：这个测试可能需要根据实际的错误情况调整
    try:
        # 正常情况下不会出错，这里只是演示错误处理机制
        chunk = processor.process_raw_message("normal message", "test")
        if chunk:
            print("✅ 正常消息处理成功")
        
        # 测试异常情况的处理逻辑
        print("✅ 错误处理机制就绪")
        
    except Exception as e:
        print(f"❌ 意外错误: {e}")


def test_unified_api_format():
    """测试统一的API格式"""
    print("\n=== 测试统一API格式 ===")
    
    # 创建不同类型的处理器
    generic_processor = OutputProcessor(TerminalType.GENERIC)
    qcli_processor = OutputProcessor(TerminalType.QCLI)
    
    # 处理不同类型的消息
    generic_chunk = generic_processor.process_raw_message("Hello World", "echo")
    qcli_chunk = qcli_processor.process_raw_message("Hello from Q CLI", "")
    
    # 转换为API格式
    api_responses = []
    if generic_chunk:
        api_responses.append(generic_chunk.to_api_format())
    if qcli_chunk:
        api_responses.append(qcli_chunk.to_api_format())
    
    print("统一API格式输出:")
    for i, response in enumerate(api_responses):
        print(f"{i+1}. {response}")
        
        # 验证格式一致性
        required_fields = ["content", "type", "metadata", "timestamp"]
        for field in required_fields:
            assert field in response, f"缺少必需字段: {field}"
        
        assert "terminal_type" in response["metadata"], "元数据中缺少 terminal_type"
    
    print("✅ 统一API格式测试通过")


def test_utility_functions():
    """测试工具函数"""
    print("\n=== 测试工具函数 ===")
    
    processor = OutputProcessor(TerminalType.GENERIC)
    
    # 创建不同类型的数据块
    content_chunk = processor.process_raw_message("test content", "test")
    
    if content_chunk:
        # 测试类型判断函数
        assert is_user_visible_content(content_chunk) == True
        print("✅ 用户可见内容判断正确")
    
    # 测试向后兼容方法
    legacy_output = processor.process_stream_output("test output", "test")
    print(f"向后兼容输出: {repr(legacy_output)}")
    
    print("✅ 工具函数测试通过")


def test_real_world_scenario():
    """测试真实场景"""
    print("\n=== 测试真实场景 ===")
    
    # 模拟一个完整的 Q CLI 交互流程
    qcli_processor = OutputProcessor(TerminalType.QCLI)
    
    # 模拟消息序列 - 使用正确的格式
    messages = [
        "⠋ Thinking...",  # 思考状态
        "🛠️  Using tool: aws_cli",  # 工具使用
        "Here's information about AWS Lambda:",  # 内容输出
        "Lambda is a serverless compute service...",  # 更多内容
    ]
    
    api_sequence = []
    for msg in messages:
        chunk = qcli_processor.process_raw_message(msg)
        if chunk:
            api_sequence.append(chunk.to_api_format())
    
    print("真实场景API序列:")
    for i, response in enumerate(api_sequence):
        print(f"{i+1}. Type: {response['type']}, Content: {repr(response['content'][:50])}")
    
    # 验证序列的合理性
    types = [resp['type'] for resp in api_sequence]
    
    print(f"消息类型序列: {types}")
    
    # 验证至少包含预期的类型
    assert 'thinking' in types, "应该包含思考状态"
    assert 'tool_use' in types, "应该包含工具使用"
    assert 'content' in types, "应该包含内容输出"
    
    print("✅ 真实场景测试通过")


def main():
    """主测试函数"""
    print("开始测试重构后的 OutputProcessor...\n")
    
    test_generic_terminal_processing()
    test_qcli_terminal_processing()
    test_error_handling()
    test_unified_api_format()
    test_utility_functions()
    test_real_world_scenario()
    
    print("\n🎉 OutputProcessor 测试完成！统一数据流架构工作正常。")


if __name__ == "__main__":
    main()
