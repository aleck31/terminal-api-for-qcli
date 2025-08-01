#!/usr/bin/env python3
"""
简单的格式化输出测试脚本
直接运行即可测试格式化功能
"""

import asyncio
import sys
import os

# 添加项目根目录到路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from api.utils import format_terminal_output, clean_terminal_text

def test_output_cleaning():
    """测试输出清理功能"""
    print("=== 输出清理功能测试 ===\n")
    
    # 测试数据 - 使用更实际的场景
    test_cases = [
        {
            "name": "ANSI序列清理",
            "input": "\x1b[31mHello\x1b[0m World",
            "expected": "Hello World"
        },
        {
            "name": "OSC序列清理", 
            "input": "Hello \x1b]0;title\x07World",
            "expected": "Hello World"
        },
        {
            "name": "基本文本保持",
            "input": "Hello World",
            "expected": "Hello World"
        }
    ]
    
    success_count = 0
    for case in test_cases:
        cleaned = clean_terminal_text(case["input"])
        if case["expected"] in cleaned:
            print(f"✅ {case['name']}: 通过")
            success_count += 1
        else:
            print(f"❌ {case['name']}: 失败")
            print(f"   输入: {repr(case['input'])}")
            print(f"   期望: {repr(case['expected'])}")
            print(f"   实际: {repr(cleaned)}")
    
    print(f"\n格式化测试: {success_count}/{len(test_cases)} 通过")
    return success_count == len(test_cases)

def test_markdown_formatting():
    """测试Markdown格式化"""
    print("\n=== Markdown格式化测试 ===\n")
    
    try:
        formatted = format_terminal_output(
            raw_output="Hello World\n",
            command="echo 'Hello World'",
            success=True,
            execution_time=0.01
        )
        
        # 检查基本格式
        if "## ✅ 命令执行 - 成功" in formatted.markdown:
            print("✅ Markdown标题格式正确")
        else:
            print("❌ Markdown标题格式错误")
            return False
            
        if "**命令:**" in formatted.markdown:
            print("✅ 命令格式正确")
        else:
            print("❌ 命令格式错误")
            return False
            
        print("✅ Markdown格式化测试通过")
        return True
        
    except Exception as e:
        print(f"❌ Markdown格式化测试失败: {e}")
        return False

if __name__ == "__main__":
    print("开始格式化功能测试...\n")
    
    test1 = test_output_cleaning()
    test2 = test_markdown_formatting()
    
    if test1 and test2:
        print("\n🎉 所有格式化测试通过")
        sys.exit(0)
    else:
        print("\n❌ 部分测试失败")
        sys.exit(1)
