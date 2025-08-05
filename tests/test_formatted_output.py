#!/usr/bin/env python3
"""
简化的格式化输出测试脚本
测试核心的清理功能
"""

import asyncio
import sys
import os

# 添加项目根目录到路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from api.utils.formatter import format_terminal_output, clean_terminal_text

def test_output_cleaning():
    """测试输出清理功能"""
    print("=== 输出清理功能测试 ===\n")
    
    # 测试数据 - 使用实际场景中的数据
    test_cases = [
        {
            "name": "ANSI序列清理",
            "input": "\x1b[31m红色文本\x1b[0m",
            "expected": "红色文本"
        },
        {
            "name": "OSC序列清理", 
            "input": "\x1b]0;窗口标题\x07正常文本",
            "expected": "正常文本"
        },
        {
            "name": "基本文本保持",
            "input": "普通文本内容",
            "expected": "普通文本内容"
        }
    ]
    
    passed = 0
    total = len(test_cases)
    
    for case in test_cases:
        cleaned = clean_terminal_text(case["input"])
        if cleaned == case["expected"]:
            print(f"✅ {case['name']}: 通过")
            passed += 1
        else:
            print(f"❌ {case['name']}: 失败")
            print(f"   输入: {repr(case['input'])}")
            print(f"   期望: {repr(case['expected'])}")
            print(f"   实际: {repr(cleaned)}")
    
    print(f"\n清理测试: {passed}/{total} 通过")
    return passed == total

def test_format_function():
    """测试格式化函数"""
    print("\n=== 格式化函数测试 ===\n")
    
    # 测试基本格式化
    formatted = format_terminal_output(
        raw_output="test output",
        command="echo test",
        success=True,
        execution_time=0.1
    )
    
    # 检查返回的数据结构
    checks = [
        ("plain_text 字段", formatted.plain_text == "test output"),
        ("command 字段", formatted.command == "echo test"),
        ("exit_code 字段", formatted.exit_code == 0)
    ]
    
    passed = 0
    for name, result in checks:
        if result:
            print(f"✅ {name}: 通过")
            passed += 1
        else:
            print(f"❌ {name}: 失败")
    
    print(f"\n格式化测试: {passed}/{len(checks)} 通过")
    return passed == len(checks)

def main():
    """主测试函数"""
    print("开始简化版格式化功能测试...\n")
    
    test1_passed = test_output_cleaning()
    test2_passed = test_format_function()
    
    if test1_passed and test2_passed:
        print("\n🎉 所有测试通过！")
        return True
    else:
        print("\n❌ 部分测试失败")
        return False

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
