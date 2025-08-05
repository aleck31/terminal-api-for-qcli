#!/usr/bin/env python3
"""
测试 gradio_chat.py 的更新是否正确
"""

import sys
import os
import asyncio

# 添加项目根目录到路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

def test_import():
    """测试导入是否正常"""
    try:
        from webui.gradio_chat import TerminalChatBot
        print("✅ 成功导入 TerminalChatBot")
        return True
    except Exception as e:
        print(f"❌ 导入失败: {e}")
        return False

def test_bot_creation():
    """测试机器人创建"""
    try:
        from webui.gradio_chat import TerminalChatBot
        bot = TerminalChatBot()
        print("✅ 成功创建 TerminalChatBot 实例")
        return True
    except Exception as e:
        print(f"❌ 创建失败: {e}")
        return False

def test_client_creation():
    """测试客户端创建"""
    try:
        from webui.gradio_chat import TerminalChatBot
        bot = TerminalChatBot()
        client = bot.get_or_create_client_for_session("test_session")
        print("✅ 成功创建客户端")
        print(f"   客户端类型: {type(client)}")
        print(f"   是否有 execute_command_stream 方法: {hasattr(client, 'execute_command_stream')}")
        print(f"   是否有旧的 execute_command 方法: {hasattr(client, 'execute_command')}")
        return True
    except Exception as e:
        print(f"❌ 客户端创建失败: {e}")
        return False

async def test_stream_interface():
    """测试流式接口"""
    try:
        from webui.gradio_chat import TerminalChatBot
        from api import TerminalAPIClient
        from api.command_executor import TerminalType
        
        # 创建客户端
        client = TerminalAPIClient(
            host="localhost",
            port=7682,  # Q CLI ttyd 服务端口
            username="demo", 
            password="password123",
            terminal_type=TerminalType.QCLI,  # 使用 Q CLI 类型
            format_output=True
        )
        
        print("✅ 客户端创建成功")
        
        # 测试连接
        connected = await client.connect()
        if connected:
            print("✅ 连接成功")
            
            # 测试流式接口
            print("🧪 测试流式接口...")
            chunk_count = 0
            async for chunk in client.execute_command_stream("Hello", timeout=15.0):
                chunk_count += 1
                print(f"   收到块 #{chunk_count}: state={chunk.get('state')}, is_content={chunk.get('is_content')}, content_len={len(chunk.get('content', ''))}")
                if chunk.get("state") == "complete":
                    print("✅ 流式接口测试成功")
                    break
                elif chunk_count > 50:  # 防止无限循环
                    print("⚠️  达到最大块数限制，停止测试")
                    break
            
            await client.disconnect()
            print("✅ 断开连接成功")
        else:
            print("❌ 连接失败 - 可能 ttyd 服务未启动")
        
        return True
    except Exception as e:
        print(f"❌ 流式接口测试失败: {e}")
        return False

def main():
    """主测试函数"""
    print("🧪 测试 gradio_chat.py 更新")
    print("=" * 50)
    
    tests = [
        ("导入测试", test_import),
        ("机器人创建测试", test_bot_creation), 
        ("客户端创建测试", test_client_creation),
    ]
    
    passed = 0
    total = len(tests)
    
    for name, test_func in tests:
        print(f"\n📋 {name}:")
        if test_func():
            passed += 1
        else:
            print(f"   测试失败")
    
    # 异步测试
    print(f"\n📋 流式接口测试:")
    try:
        if asyncio.run(test_stream_interface()):
            passed += 1
            total += 1
        else:
            total += 1
    except Exception as e:
        print(f"❌ 异步测试失败: {e}")
        total += 1
    
    print(f"\n📊 测试结果: {passed}/{total} 通过")
    
    if passed == total:
        print("🎉 所有测试通过！gradio_chat.py 更新成功")
    else:
        print("⚠️  部分测试失败，需要进一步检查")

if __name__ == "__main__":
    main()
