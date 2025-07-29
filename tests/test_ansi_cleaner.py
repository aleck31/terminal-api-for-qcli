#!/usr/bin/env python3
"""
ANSI清理器测试
"""

import pytest
from utils.ansi_cleaner import ansi_cleaner

class TestANSICleaner:
    """ANSI清理器测试"""
    
    def test_spinner_character_removal(self):
        """测试加载动画字符清理"""
        test_cases = [
            ('\x1b7\x1b[1G\x1b[1A⠦\x1b8', ''),  # 纯控制序列
            ('⠦⠧⠇⠏⠋⠙⠹⠸⠼⠴', ''),  # 纯动画字符
            ('Loading ⠦ please wait', 'Loading please wait'),  # 混合内容
        ]
        
        for input_text, expected in test_cases:
            result = ansi_cleaner.clean(input_text)
            assert result == expected, f"输入: {repr(input_text)}, 期望: {repr(expected)}, 实际: {repr(result)}"
    
    def test_ansi_sequence_removal(self):
        """测试ANSI转义序列清理"""
        test_cases = [
            ('\x1b[38;5;10m✓ \x1b[38;5;12mexa_search\x1b[0m loaded', '✓ exa_search loaded'),
            ('\x1b[1mWelcome to \x1b[96mAmazon Q\x1b[39m!\x1b[22m', 'Welcome to Amazon Q!'),
            ('\x1b[92mctrl + j\x1b[90m new lines', 'ctrl + j new lines'),
        ]
        
        for input_text, expected in test_cases:
            result = ansi_cleaner.clean(input_text)
            assert result == expected, f"输入: {repr(input_text)}, 期望: {repr(expected)}, 实际: {repr(result)}"
    
    def test_meaningful_content_detection(self):
        """测试有意义内容检测"""
        meaningful_cases = [
            'Hello World',
            '✓ exa_search loaded in 1.04 s',
            'Welcome to Amazon Q!',
            'Error: command not found',
            'Loading please wait for server',
        ]
        
        meaningless_cases = [
            '78',
            'A',
            '[1',
            '',
            '   ',
            '\x1b7\x1b[1G\x1b[1A⠦\x1b8',
        ]
        
        for text in meaningful_cases:
            assert ansi_cleaner.is_meaningful_content(text), f"应该被识别为有意义: {repr(text)}"
        
        for text in meaningless_cases:
            assert not ansi_cleaner.is_meaningful_content(text), f"应该被识别为无意义: {repr(text)}"
    
    def test_batch_processing(self):
        """测试批量处理功能"""
        test_messages = [
            'Hello World',
            '\x1b7\x1b[1G\x1b[1A⠦\x1b8',  # 应该被过滤
            '✓ Server loaded',
            '78',  # 应该被过滤
        ]
        
        # 测试批量清理
        cleaned = ansi_cleaner.clean_batch(test_messages)
        expected_cleaned = ['Hello World', '', '✓ Server loaded', '78']
        assert cleaned == expected_cleaned
        
        # 测义消息过滤
        meaningful = ansi_cleaner.filter_meaningful_messages(test_messages)
        expected_meaningful = ['Hello World', '✓ Server loaded']
        assert meaningful == expected_meaningful
    
    def test_edge_cases(self):
        """测试边界情况"""
        edge_cases = [
            ('', ''),  # 空字符串
            ('   ', ''),  # 纯空白
            ('\n\n\n', ''),  # 多个换行
            ('a\x1b[1mb\x1b[0mc', 'abc'),  # 混合内容
        ]
        
        for input_text, expected in edge_cases:
            result = ansi_cleaner.clean(input_text)
            assert result == expected, f"输入: {repr(input_text)}, 期望: {repr(expected)}, 实际: {repr(result)}"
    
    def test_performance_baseline(self):
        """测试性能基准"""
        # 生成测试数据
        test_data = [
            '\x1b7\x1b[1G\x1b[1A⠦\x1b8',
            '\x1b[38;5;10m✓ test\x1b[0m loaded',
            '⠦⠧⠇⠏⠋⠙⠹⠸⠼⠴',
            'Normal text with ⠦ spinner',
        ] * 100  # 400条消息
        
        import time
        start_time = time.time()
        
        # 批量处理
        results = ansi_cleaner.clean_batch(test_data)
        
        end_time = time.time()
        processing_time = end_time - start_time
        
        # 验证结果数量
        assert len(results) == len(test_data)
        
        # 性能应该在合理范围内（400条消息应该在1秒内完成）
        assert processing_time < 1.0, f"处理时间过长: {processing_time:.3f}秒"