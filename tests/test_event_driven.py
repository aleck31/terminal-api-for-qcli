#!/usr/bin/env python3
"""
测试事件驱动消息处理机制
验证 ConnectionManager 的事件分发和 TerminalAPIClient 的初始化流程
"""

import asyncio
import logging
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from api.connection_manager import ConnectionManager
from api.terminal_api_client import TerminalAPIClient, TerminalBusinessState
from api.command_executor import TerminalType

# 设置日志
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

async def test_connection_manager_event_dispatch():
    """测试 ConnectionManager 的事件分发机制"""
    print("\n=== 测试 ConnectionManager 事件分发机制 ===")
    
    manager = ConnectionManager(host="localhost", port=7682)
    
    # 收集消息的列表
    primary_messages = []
    listener1_messages = []
    listener2_messages = []
    
    # 主要处理器
    def primary_handler(msg):
        primary_messages.append(f"PRIMARY: {msg}")
        print(f"主要处理器收到: {msg[:50]}...")
    
    # 临时监听器1
    def temp_listener1(msg):
        listener1_messages.append(f"LISTENER1: {msg}")
        print(f"监听器1收到: {msg[:50]}...")
    
    # 临时监听器2
    def temp_listener2(msg):
        listener2_messages.append(f"LISTENER2: {msg}")
        print(f"监听器2收到: {msg[:50]}...")
    
    # 设置主要处理器
    manager.set_primary_handler(primary_handler)
    
    # 添加临时监听器
    listener1_id = manager.add_temp_listener(temp_listener1)
    listener2_id = manager.add_temp_listener(temp_listener2)
    
    print(f"添加了监听器: ID1={listener1_id}, ID2={listener2_id}")
    
    try:
        # 建立连接测试消息分发
        success = await manager.connect()
        if success:
            print("连接成功，等待消息...")
            await asyncio.sleep(2)  # 等待一些消息
            
            print(f"主要处理器收到 {len(primary_messages)} 条消息")
            print(f"监听器1收到 {len(listener1_messages)} 条消息")
            print(f"监听器2收到 {len(listener2_messages)} 条消息")
            
            # 移除一个监听器
            manager.remove_temp_listener(listener1_id)
            print("移除监听器1")
            
            await asyncio.sleep(1)  # 再等待一些消息
            
            await manager.disconnect()
        else:
            print("连接失败（可能服务未启动）")
            
    except Exception as e:
        print(f"测试出错: {e}")

async def test_terminal_api_client_initialization():
    """测试 TerminalAPIClient 的初始化流程"""
    print("\n=== 测试 TerminalAPIClient 初始化流程 ===")
    
    # 测试通用终端
    print("\n--- 测试通用终端 ---")
    client = TerminalAPIClient(
        host="localhost", 
        port=7682,
        terminal_type=TerminalType.GENERIC
    )
    
    print(f"初始状态: {client.terminal_state.value}")
    
    try:
        success = await client.initialize()
        if success:
            print(f"初始化成功，当前状态: {client.terminal_state.value}")
            print(f"可以执行命令: {client.can_execute_command}")
            
            await client.shutdown()
            print(f"关闭后状态: {client.terminal_state.value}")
        else:
            print("初始化失败")
    except Exception as e:
        print(f"测试出错: {e}")
    
    # 测试 Q CLI（如果需要）
    print("\n--- 测试 Q CLI ---")
    qcli_client = TerminalAPIClient(
        host="localhost", 
        port=7682,  # 假设7682是Q CLI端口
        terminal_type=TerminalType.QCLI
    )
    
    print(f"Q CLI 初始状态: {qcli_client.terminal_state.value}")
    
    try:
        success = await qcli_client.initialize()
        if success:
            print(f"Q CLI 初始化成功，当前状态: {qcli_client.terminal_state.value}")
            print(f"Q CLI 可以执行命令: {qcli_client.can_execute_command}")
            
            await qcli_client.shutdown()
            print(f"Q CLI 关闭后状态: {qcli_client.terminal_state.value}")
        else:
            print("Q CLI 初始化失败")
    except Exception as e:
        print(f"Q CLI 测试出错: {e}")

async def test_business_state_transitions():
    """测试业务状态转换"""
    print("\n=== 测试业务状态转换 ===")
    
    client = TerminalAPIClient(host="localhost", port=7682)
    
    # 记录状态变化
    state_changes = []
    original_set_state = client._set_state
    
    def track_state_change(new_state):
        state_changes.append(new_state.value)
        print(f"状态变化: {new_state.value}")
        original_set_state(new_state)
    
    client._set_state = track_state_change
    
    try:
        print("开始初始化...")
        success = await client.initialize()
        
        if success:
            print("初始化成功")
            await asyncio.sleep(1)
            
            # 测试命令执行状态变化
            if client.can_execute_command:
                print("测试命令执行...")
                async for chunk in client.execute_command_stream("echo 'test'"):
                    if chunk.get("state") == "complete":
                        break
            
            await client.shutdown()
        
        print(f"\n状态变化序列: {state_changes}")
        
        # 验证状态变化是否合理
        expected_states = ["initializing", "idle"]
        if any(state in state_changes for state in expected_states):
            print("✅ 状态变化正常")
        else:
            print("❌ 状态变化异常")
            
    except Exception as e:
        print(f"状态转换测试出错: {e}")

async def main():
    """主测试函数"""
    print("开始事件驱动机制测试...")
    
    await test_connection_manager_event_dispatch()
    await test_terminal_api_client_initialization()
    await test_business_state_transitions()
    
    print("\n事件驱动机制测试完成！")

if __name__ == "__main__":
    asyncio.run(main())
