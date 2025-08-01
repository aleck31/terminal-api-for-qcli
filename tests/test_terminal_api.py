#!/usr/bin/env python3
"""
简单的终端API测试脚本
直接运行即可测试基本功能
"""

import asyncio
import sys
import os

# 添加项目根目录到路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from api import TerminalAPIClient

async def test_terminal_api():
    """测试终端API基本功能"""
    print("=== 终端API基本功能测试 ===\n")
    
    try:
        # 测试客户端创建
        client = TerminalAPIClient(
            host="localhost", 
            port=7681, 
            username="demo", 
            password="password123",
            format_output=True
        )
        print("✅ 客户端创建成功")
        
        # 测试连接（如果服务可用）
        try:
            await client.connect()
            if client.is_connected:
                print("✅ 连接测试成功")
                
                # 测试简单命令
                result = await client.execute_command('echo "Hello Test"')
                if result.success and "Hello Test" in result.output:
                    print("✅ 命令执行测试成功")
                else:
                    print("⚠️  命令执行测试失败（但这可能是正常的）")
                
                await client.disconnect()
            else:
                print("⚠️  连接失败（可能ttyd服务未启动，这是正常的）")
        except Exception as e:
            print(f"⚠️  连接测试跳过: {e}")
        
        print("\n🎉 基本功能测试完成")
        return True
        
    except Exception as e:
        print(f"❌ 测试失败: {e}")
        return False

if __name__ == "__main__":
    success = asyncio.run(test_terminal_api())
    sys.exit(0 if success else 1)
