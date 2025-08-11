#!/usr/bin/env python3
"""
测试统一数据流架构的基础数据结构
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from api.data_structures import StreamChunk, ChunkType, MetadataBuilder
from api.data_structures import is_user_visible_content, is_status_indicator, is_completion_marker


def test_chunk_types():
    """测试数据块类型"""
    print("=== 测试数据块类型 ===")
    
    # 测试所有类型
    for chunk_type in ChunkType:
        print(f"{chunk_type.name}: {chunk_type.value}")
    
    print("✅ 数据块类型测试通过")


def test_metadata_builder():
    """测试元数据构建器"""
    print("\n=== 测试元数据构建器 ===")
    
    # 测试内容元数据
    content_meta = MetadataBuilder.for_content(100, 50, "qcli")
    print(f"内容元数据: {content_meta}")
    assert content_meta["raw_length"] == 100
    assert content_meta["content_length"] == 50
    assert content_meta["terminal_type"] == "qcli"
    
    # 测试工具使用元数据
    tool_meta = MetadataBuilder.for_tool_use("aws_cli", 80, "qcli")
    print(f"工具元数据: {tool_meta}")
    assert tool_meta["tool_name"] == "aws_cli"
    
    # 测试错误元数据
    error_meta = MetadataBuilder.for_error("Connection failed", "generic", "network_error")
    print(f"错误元数据: {error_meta}")
    assert error_meta["error_message"] == "Connection failed"
    assert error_meta["error_type"] == "network_error"
    
    print("✅ 元数据构建器测试通过")


def test_stream_chunk():
    """测试流式数据块"""
    print("\n=== 测试流式数据块 ===")
    
    # 测试内容块
    content_chunk = StreamChunk.create_content("Hello World", "qcli", 50)
    print(f"内容块: {content_chunk}")
    assert content_chunk.content == "Hello World"
    assert content_chunk.type == ChunkType.CONTENT
    assert content_chunk.metadata["terminal_type"] == "qcli"
    
    # 测试API格式转换
    api_format = content_chunk.to_api_format()
    print(f"API格式: {api_format}")
    assert api_format["content"] == "Hello World"
    assert api_format["type"] == "content"
    assert "metadata" in api_format
    assert "timestamp" in api_format
    
    # 测试错误块
    error_chunk = StreamChunk.create_error("Test error", "generic")
    print(f"错误块: {error_chunk}")
    assert error_chunk.type == ChunkType.ERROR
    assert error_chunk.content == ""
    
    print("✅ 流式数据块测试通过")


def test_utility_functions():
    """测试工具函数"""
    print("\n=== 测试工具函数 ===")
    
    # 创建不同类型的数据块
    content_chunk = StreamChunk.create_content("test", "qcli")
    error_chunk = StreamChunk.create_error("error", "qcli")
    
    thinking_chunk = StreamChunk(
        content="",
        type=ChunkType.THINKING,
        metadata=MetadataBuilder.for_thinking(50, "qcli"),
        timestamp=1234567890.0
    )
    
    complete_chunk = StreamChunk(
        content="",
        type=ChunkType.COMPLETE,
        metadata={
            "execution_time": 2.5,
            "command_success": True,
            "terminal_type": "qcli"
        },
        timestamp=1234567890.0
    )
    
    # 测试用户可见内容
    assert is_user_visible_content(content_chunk) == True
    assert is_user_visible_content(error_chunk) == True
    assert is_user_visible_content(thinking_chunk) == False
    
    # 测试状态指示器
    assert is_status_indicator(thinking_chunk) == True
    assert is_status_indicator(content_chunk) == False
    
    # 测试完成标记
    assert is_completion_marker(complete_chunk) == True
    assert is_completion_marker(content_chunk) == False
    
    print("✅ 工具函数测试通过")


def test_real_world_scenarios():
    """测试真实场景"""
    print("\n=== 测试真实场景 ===")
    
    # 模拟 Q CLI 思考状态
    thinking = StreamChunk(
        content="",
        type=ChunkType.THINKING,
        metadata=MetadataBuilder.for_thinking(45, "qcli"),
        timestamp=1234567890.0
    )
    
    # 模拟工具使用
    tool_use = StreamChunk(
        content="",
        type=ChunkType.TOOL_USE,
        metadata=MetadataBuilder.for_tool_use("web_search", 67, "qcli"),
        timestamp=1234567890.1
    )
    
    # 模拟内容输出
    content = StreamChunk.create_content("Hello! I'm Amazon Q...", "qcli", 156)
    
    # 模拟完成
    complete = StreamChunk(
        content="",
        type=ChunkType.COMPLETE,
        metadata={
            "execution_time": 2.34,
            "command_success": True,
            "terminal_type": "qcli"
        },
        timestamp=1234567890.2
    )
    
    # 转换为API格式
    api_responses = [chunk.to_api_format() for chunk in [thinking, tool_use, content, complete]]
    
    print("API响应序列:")
    for i, response in enumerate(api_responses):
        print(f"{i+1}. {response}")
    
    # 验证格式一致性
    for response in api_responses:
        assert "content" in response
        assert "type" in response
        assert "metadata" in response
        assert "timestamp" in response
        assert response["metadata"]["terminal_type"] == "qcli"
    
    print("✅ 真实场景测试通过")


def main():
    """主测试函数"""
    print("开始测试统一数据流架构的基础数据结构...\n")
    
    test_chunk_types()
    test_metadata_builder()
    test_stream_chunk()
    test_utility_functions()
    test_real_world_scenarios()
    
    print("\n🎉 所有测试通过！基础数据结构工作正常。")


if __name__ == "__main__":
    main()
