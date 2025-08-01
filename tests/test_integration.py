#!/usr/bin/env python3
"""
简单的集成测试脚本
需要先启动ttyd服务才能运行
"""

import asyncio
import sys
import os

# 添加项目根目录到路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from api import TerminalAPIClient

async def test_integration():
    """集成测试 - 需要ttyd服务运行"""
    print("=== 集成测试（需要ttyd服务运行）===\n")
    
    try:
        async with TerminalAPIClient(
            host="localhost", 
            port=7681, 
            username="demo", 
            password="password123",
            format_output=True
        ) as client:
            
            if not client.is_connected:
                print("❌ 无法连接到ttyd服务")
                print("请先运行: ./ttyd/ttyd-service.sh start")
                return False
            
            print("✅ 连接到ttyd服务成功")
            
            # 测试基本命令
            test_commands = [
                'echo "Hello Integration Test"',
                'pwd',
                'whoami'
            ]
            
            success_count = 0
            for cmd in test_commands:
                result = await client.execute_command(cmd)
                if result.success:
                    print(f"✅ 命令 '{cmd}' 执行成功")
                    success_count += 1
                else:
                    print(f"❌ 命令 '{cmd}' 执行失败: {result.error}")
            
            # 测试格式化输出
            result = await client.execute_command('echo "Format Test"')
            if result.success and "## ✅ 命令执行 - 成功" in result.markdown:
                print("✅ Markdown格式化正常")
                success_count += 1
            else:
                print("❌ Markdown格式化异常")
            
            print(f"\n集成测试结果: {success_count}/{len(test_commands)+1} 通过")
            return success_count == len(test_commands) + 1
            
    except Exception as e:
        print(f"❌ 集成测试失败: {e}")
        print("请确保ttyd服务正在运行: ./ttyd/ttyd-service.sh start")
        return False

if __name__ == "__main__":
    print("开始集成测试...\n")
    print("注意: 此测试需要ttyd服务运行")
    print("如果服务未启动，请运行: ./ttyd/ttyd-service.sh start\n")
    
    success = asyncio.run(test_integration())
    
    if success:
        print("\n🎉 集成测试全部通过")
        sys.exit(0)
    else:
        print("\n❌ 集成测试失败")
        sys.exit(1)
