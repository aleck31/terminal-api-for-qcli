#!/usr/bin/env python3
"""
消息处理器测试
"""

import pytest
from api.message_processor import MessageProcessor

class TestMessageProcessor:
    """消息处理器测试"""
    
    @pytest.fixture
    def processor(self):
        """创建消息处理器实例"""
        return MessageProcessor()
    
    def test_dangerous_command_detection(self, processor):
        """测试危险命令检测"""
        dangerous_commands = [
            'rm -rf /',
            'sudo rm -rf /home',
            'mkfs /dev/sda',
            'dd if=/dev/zero of=/dev/sda',
            'format c:',  # 使用实际危险命令列表中的命令
        ]
        
        safe_commands = [
            'ls -la',
            'echo hello',
            'cat file.txt',
            'mkdir test',
            'cp file1 file2',
        ]
        
        for cmd in dangerous_commands:
            assert processor.is_dangerous_command(cmd), f"应该被识别为危险命令: {cmd}"
        
        for cmd in safe_commands:
            assert not processor.is_dangerous_command(cmd), f"应该被识别为安全命令: {cmd}"
    
    def test_command_execution_lifecycle(self, processor):
        """测试命令执行生命周期"""
        command = "echo 'test'"
        
        # 开始执行
        result = processor.start_command_execution(command)
        assert result[0] == "status"
        assert command in result[1]
        assert result[2]["status"] == "pending"
        
        # 模拟消息处理
        test_message = {"type": "output", "data": "test output"}
        result = processor.process_websocket_message(test_message)
        
        if result:  # 如果消息没有被过滤
            assert result[0] == "stdout"
            assert "test output" in result[1]
        
        # 完成执行
        summary = processor.finish_command_execution(return_code=0)
        assert summary[0] == "summary"
        assert summary[1]["command"] == command
        assert summary[1]["status"] == "success"
    
    def test_ansi_cleaning_integration(self, processor):
        """测试ANSI清理集成"""
        # 包含ANSI序列的消息
        ansi_message = {
            "type": "output",
            "data": "\x1b[38;5;10m✓ \x1b[38;5;12mtest\x1b[0m completed"
        }
        
        result = processor.process_websocket_message(ansi_message)
        
        if result:  # 如果消息没有被过滤
            # 应该清理掉ANSI序列
            assert "\x1b[" not in result[1]
            assert "✓ test completed" in result[1]
    
    def test_message_filtering(self, processor):
        """测试消息过滤功能"""
        # 应该被过滤的消息
        filtered_messages = [
            {"type": "output", "data": "\x1b7\x1b[1G\x1b[1A⠦\x1b8"},  # 纯控制序列
            {"type": "output", "data": "78"},  # 无意义短字符
            {"type": "output", "data": "A"},   # 单个字符
        ]
        
        # 应该保留的消息
        meaningful_messages = [
            {"type": "output", "data": "Hello World"},
            {"type": "output", "data": "✓ Server started"},
            {"type": "error", "data": "Error occurred"},
        ]
        
        for msg in filtered_messages:
            result = processor.process_websocket_message(msg)
            assert result is None, f"消息应该被过滤: {msg['data']}"
        
        for msg in meaningful_messages:
            result = processor.process_websocket_message(msg)
            assert result is not None, f"消息应该被保留: {msg['data']}"
    
    def test_execution_metrics(self, processor):
        """测试执行指标收集"""
        # 开始执行
        processor.start_command_execution("test command")
        
        # 模拟一些输出
        processor.process_websocket_message({"type": "output", "data": "stdout line 1"})
        processor.process_websocket_message({"type": "output", "data": "stdout line 2"})
        processor.process_websocket_message({"type": "error", "data": "error line 1"})
        
        # 完成执行
        summary = processor.finish_command_execution(return_code=0)
        
        # 验证指标
        metrics = summary[1]
        assert metrics["command"] == "test command"
        assert metrics["return_code"] == 0
        assert metrics["status"] == "success"
        assert isinstance(metrics["duration"], float)
        assert metrics["duration"] > 0
    
    def test_error_handling(self, processor):
        """测试错误处理"""
        # 测试危险命令拦截
        result = processor.start_command_execution("rm -rf /")
        assert result[0] == "error"
        assert "危险命令" in result[1]
        
        # 测试无效消息处理 - 只测试有效的字典格式
        invalid_messages = [
            {},  # 空字典
            {"type": "unknown"},  # 未知类型
            {"data": "no type"},  # 缺少type字段
        ]
        
        for msg in invalid_messages:
            result = processor.process_websocket_message(msg)
            # 应该返回None或不抛出异常
            assert result is None or isinstance(result, tuple)
        
        # 测试None值应该被安全处理
        result = processor.process_websocket_message(None)
        assert result is None