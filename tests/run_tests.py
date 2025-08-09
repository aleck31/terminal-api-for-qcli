#!/usr/bin/env python3
"""
测试运行器
运行各个测试脚本，包括统一数据流架构测试
"""

import subprocess
import sys
import os
from pathlib import Path

def run_test_script(script_path, description):
    """运行测试脚本"""
    print(f"\n{'='*50}")
    print(f"🚀 {description}")
    print('='*50)
    
    try:
        # 使用 uv run 运行测试脚本
        result = subprocess.run([
            "uv", "run", "python", str(script_path)
        ], cwd=Path(__file__).parent.parent, timeout=120)
        
        if result.returncode == 0:
            print(f"✅ {description} - 通过")
            return True
        else:
            print(f"❌ {description} - 失败")
            return False
            
    except subprocess.TimeoutError:
        print(f"⏰ {description} - 超时")
        return False
    except Exception as e:
        print(f"💥 {description} - 错误: {e}")
        return False

def main():
    """主函数"""
    print("🧪 开始运行测试套件")
    
    # 基础测试脚本列表
    basic_tests = [
        ("tests/test_formatted_output.py", "格式化输出测试"),
        ("tests/test_ttyd_service.py", "服务脚本测试"),
    ]
    
    # 统一数据流架构测试
    unified_tests = [
        ("tests/test_data_structures.py", "统一数据结构测试"),
        ("tests/test_output_processor.py", "输出处理器测试"),
        ("tests/test_command_executor.py", "命令执行器测试"),
        ("tests/test_terminal_api_client.py", "终端API客户端测试"),
    ]
    
    # 集成测试（需要服务运行）
    integration_tests = [
        ("tests/test_connect_state.py", "连接状态测试"),
        ("tests/test_state_mapping.py", "状态映射测试"),
        ("tests/test_event_driven.py", "事件驱动测试"),
        ("tests/test_gradio_webui.py", "Gradio WebUI测试"),
    ]
    
    # 根据参数决定运行哪些测试
    tests_to_run = []
    
    if len(sys.argv) > 1:
        if "--unified" in sys.argv:
            tests_to_run.extend(unified_tests)
            print("🎯 运行统一数据流架构测试")
        elif "--integration" in sys.argv:
            tests_to_run.extend(integration_tests)
            print("🔗 运行集成测试（需要ttyd服务）")
        elif "--all" in sys.argv:
            tests_to_run.extend(basic_tests)
            tests_to_run.extend(unified_tests)
            tests_to_run.extend(integration_tests)
            print("🚀 运行所有测试")
        else:
            print("❓ 未知参数，运行基础测试")
            tests_to_run.extend(basic_tests)
    else:
        # 默认运行统一数据流架构测试
        tests_to_run.extend(unified_tests)
        print("🎯 默认运行统一数据流架构测试")
    
    # 运行测试
    passed = 0
    total = len(tests_to_run)
    
    for script, description in tests_to_run:
        if run_test_script(script, description):
            passed += 1
    
    # 显示结果
    print(f"\n{'='*50}")
    print(f"📊 测试结果: {passed}/{total} 通过")
    print('='*50)
    
    if passed == total:
        print("🎉 所有测试通过！")
        
        # 提示其他测试选项
        if "--unified" in sys.argv or len(sys.argv) == 1:
            print("\n💡 其他测试选项:")
            print("   --integration  运行集成测试（需要先启动ttyd服务）")
            print("   --all         运行所有测试")
        elif "--integration" in sys.argv:
            print("\n💡 提示: 运行 'python tests/run_tests.py --unified' 来测试统一数据流架构")
        
        return True
    else:
        print("❌ 部分测试失败")
        return False

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
