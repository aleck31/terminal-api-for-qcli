#!/usr/bin/env python3
"""
简单的测试运行器
直接运行各个测试脚本
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
        ], cwd=Path(__file__).parent, timeout=120)
        
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
    print("🧪 开始运行简单测试套件")
    
    # 测试脚本列表
    tests = [
        ("test_terminal_api.py", "终端API基础测试"),
        ("test_formatted_output.py", "格式化输出测试"),
        ("test_ttyd_service.py", "服务脚本测试"),
    ]
    
    # 检查是否运行集成测试
    if len(sys.argv) > 1 and sys.argv[1] == "--integration":
        tests.append(("tests/test_integration.py", "集成测试（需要ttyd服务）"))
    
    # 运行测试
    passed = 0
    total = len(tests)
    
    for script, description in tests:
        if run_test_script(script, description):
            passed += 1
    
    # 显示结果
    print(f"\n{'='*50}")
    print(f"📊 测试结果: {passed}/{total} 通过")
    print('='*50)
    
    if passed == total:
        print("🎉 所有测试通过！")
        if "--integration" not in sys.argv:
            print("\n💡 提示: 运行 'python run_tests.py --integration' 来测试完整功能")
            print("   （需要先启动ttyd服务: ./ttyd/ttyd-service.sh start）")
        return True
    else:
        print("❌ 部分测试失败")
        return False

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
