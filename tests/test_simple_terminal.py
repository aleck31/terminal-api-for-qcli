#!/usr/bin/env python3
"""
测试简单终端接口（端口7681）
验证基本的命令执行和状态转换功能
"""

import asyncio
import logging
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from api.terminal_api_client import TerminalAPIClient, TerminalBusinessState
from api.command_executor import TerminalType

# 设置日志
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

async def test_simple_terminal_commands():
    """测试简单终端命令执行"""
    print("\n=== 测试简单终端命令执行 ===")
    
    # 使用端口7681的通用终端
    client = TerminalAPIClient(
        host="localhost", 
        port=7681,
        terminal_type=TerminalType.GENERIC
    )
    
    # 记录状态变化
    state_changes = []
    original_set_state = client._set_state
    
    def track_state_change(new_state):
        state_changes.append(new_state.value)
        print(f"状态变化: {new_state.value}")
        original_set_state(new_state)
    
    client._set_state = track_state_change
    
    try:
        print("1. 初始化终端...")
        success = await client.initialize()
        
        if not success:
            print("❌ 终端初始化失败")
            return
        
        print("✅ 终端初始化成功")
        
        # 测试简单命令
        test_commands = [
            "pwd",
            "echo 'Hello World'", 
            "date",
            "whoami",
            "ls -la /tmp"
        ]
        
        for i, cmd in enumerate(test_commands, 1):
            print(f"\n{i}. 执行命令: {cmd}")
            
            if not client.can_execute_command:
                print(f"❌ 无法执行命令，当前状态: {client.terminal_state.value}")
                break
            
            # 收集命令输出
            output_chunks = []
            command_success = False
            
            async for chunk in client.execute_command_stream(cmd):
                if chunk.get("content"):
                    output_chunks.append(chunk["content"])
                
                if chunk.get("state") == "complete":
                    command_success = chunk.get("command_success", False)
                    print(f"   命令完成，成功: {command_success}")
                    break
                elif chunk.get("state") == "error":
                    print(f"   命令错误: {chunk.get('error', '未知错误')}")
                    break
            
            # 显示输出
            if output_chunks:
                output = "".join(output_chunks).strip()
                print(f"   输出: {output[:100]}{'...' if len(output) > 100 else ''}")
            else:
                print("   无输出")
            
            # 短暂等待
            await asyncio.sleep(0.5)
        
        print(f"\n状态变化序列: {state_changes}")
        
        # 验证状态转换
        if len(state_changes) >= 2:
            if state_changes[0] == "initializing" and state_changes[1] == "idle":
                print("✅ 初始化状态转换正确")
            else:
                print("❌ 初始化状态转换异常")
        
        # 检查 busy/idle 交替
        busy_idle_count = state_changes.count("busy") + state_changes.count("idle")
        if busy_idle_count > 2:  # 至少有一次命令执行
            print("✅ 发现命令执行状态变化")
        else:
            print("❌ 未发现命令执行状态变化")
        
        # 关闭连接
        print("\n关闭连接...")
        await client.shutdown()
        
    except Exception as e:
        print(f"测试出错: {e}")
        import traceback
        traceback.print_exc()

async def test_connection_info():
    """测试连接信息"""
    print("\n=== 测试连接信息 ===")
    
    client = TerminalAPIClient(
        host="localhost", 
        port=7681,
        terminal_type=TerminalType.GENERIC
    )
    
    try:
        print("初始化前连接信息:")
        info = client._connection_manager.get_connection_info()
        print(f"  {info}")
        
        success = await client.initialize()
        if success:
            print("\n初始化后连接信息:")
            info = client._connection_manager.get_connection_info()
            print(f"  {info}")
            
            print(f"\n业务状态: {client.terminal_state.value}")
            print(f"可执行命令: {client.can_execute_command}")
            
            await client.shutdown()
            
            print("\n关闭后连接信息:")
            info = client._connection_manager.get_connection_info()
            print(f"  {info}")
        
    except Exception as e:
        print(f"连接信息测试出错: {e}")

async def test_event_driven_messaging():
    """测试事件驱动消息处理"""
    print("\n=== 测试事件驱动消息处理 ===")
    
    client = TerminalAPIClient(
        host="localhost", 
        port=7681,
        terminal_type=TerminalType.GENERIC
    )
    
    try:
        # 初始化
        success = await client.initialize()
        if not success:
            print("❌ 初始化失败")
            return
        
        # 添加临时监听器测试
        received_messages = []
        
        def test_listener(msg):
            received_messages.append(msg[:50] + "..." if len(msg) > 50 else msg)
        
        # 添加监听器
        listener_id = client._connection_manager.add_temp_listener(test_listener)
        print(f"添加临时监听器: ID={listener_id}")
        
        # 执行一个命令
        print("执行测试命令: echo 'test message'")
        async for chunk in client.execute_command_stream("echo 'test message'"):
            if chunk.get("state") == "complete":
                break
        
        # 移除监听器
        client._connection_manager.remove_temp_listener(listener_id)
        print(f"移除临时监听器: ID={listener_id}")
        
        print(f"监听器收到 {len(received_messages)} 条消息")
        if received_messages:
            print("前几条消息:")
            for i, msg in enumerate(received_messages[:3]):
                print(f"  {i+1}: {repr(msg)}")
        
        await client.shutdown()
        
    except Exception as e:
        print(f"事件驱动消息测试出错: {e}")

async def main():
    """主测试函数"""
    print("开始简单终端测试...")
    
    await test_simple_terminal_commands()
    await test_connection_info()
    await test_event_driven_messaging()
    
    print("\n简单终端测试完成！")

if __name__ == "__main__":
    asyncio.run(main())
