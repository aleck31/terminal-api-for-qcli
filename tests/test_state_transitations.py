#!/usr/bin/env python3
"""
测试正确的业务状态转换
验证 TerminalAPIClient 的状态转换是否符合预期
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

async def test_correct_state_transitions():
    """测试正确的业务状态转换"""
    print("\n=== 测试正确的业务状态转换 ===")
    
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
        print("1. 开始初始化...")
        success = await client.initialize()
        
        if success:
            print("2. 初始化成功，开始执行多个命令...")
            
            # 执行第一个命令
            print("3. 执行第一个命令: pwd")
            async for chunk in client.execute_command_stream("pwd"):
                if chunk.get("state") == "complete":
                    print("   第一个命令完成")
                    break
            
            # 短暂等待
            await asyncio.sleep(0.5)
            
            # 执行第二个命令
            print("4. 执行第二个命令: echo 'hello'")
            async for chunk in client.execute_command_stream("echo 'hello'"):
                if chunk.get("state") == "complete":
                    print("   第二个命令完成")
                    break
            
            # 短暂等待
            await asyncio.sleep(0.5)
            
            # 执行第三个命令
            print("5. 执行第三个命令: date")
            async for chunk in client.execute_command_stream("date"):
                if chunk.get("state") == "complete":
                    print("   第三个命令完成")
                    break
            
            print("6. 所有命令执行完成")
            
            # 最后关闭连接
            print("7. 关闭连接...")
            await client.shutdown()
        
        print(f"\n实际状态变化序列: {state_changes}")
        
        # 验证状态变化是否正确
        expected_pattern = ["initializing", "idle", "busy", "idle", "busy", "idle", "busy", "idle", "unavailable"]
        
        print(f"期望状态变化模式: {expected_pattern}")
        
        # 检查关键状态转换
        if len(state_changes) >= 3:
            if (state_changes[0] == "initializing" and 
                state_changes[1] == "idle" and 
                state_changes[2] == "busy"):
                print("✅ 初始化和第一次命令执行状态转换正确")
            else:
                print("❌ 初始化和第一次命令执行状态转换错误")
        
        # 检查是否有重复的初始化
        init_count = state_changes.count("initializing")
        if init_count == 1:
            print("✅ 只有一次初始化，符合预期")
        else:
            print(f"❌ 发现 {init_count} 次初始化，不符合预期")
        
        # 检查 busy/idle 交替模式
        busy_idle_pattern = []
        for i, state in enumerate(state_changes):
            if state in ["busy", "idle"] and i > 0:  # 跳过初始化后的第一个idle
                busy_idle_pattern.append(state)
        
        print(f"busy/idle 交替模式: {busy_idle_pattern}")
        
        # 验证交替模式
        is_alternating = True
        for i in range(1, len(busy_idle_pattern)):
            if busy_idle_pattern[i] == busy_idle_pattern[i-1]:
                is_alternating = False
                break
        
        if is_alternating and len(busy_idle_pattern) > 0:
            print("✅ busy/idle 状态正确交替")
        else:
            print("❌ busy/idle 状态交替异常")
            
    except Exception as e:
        print(f"状态转换测试出错: {e}")
        import traceback
        traceback.print_exc()

async def test_connection_persistence():
    """测试连接持久性"""
    print("\n=== 测试连接持久性 ===")
    
    client = TerminalAPIClient(host="localhost", port=7682)
    
    try:
        # 初始化
        success = await client.initialize()
        if not success:
            print("❌ 初始化失败")
            return
        
        print("✅ 初始化成功")
        
        # 记录连接信息
        initial_connection_info = client._connection_manager.get_connection_info()
        print(f"初始连接信息: {initial_connection_info}")
        
        # 执行多个命令，检查连接是否保持
        commands = ["pwd", "echo 'test1'", "echo 'test2'", "date"]
        
        for i, cmd in enumerate(commands):
            print(f"执行命令 {i+1}: {cmd}")
            
            # 检查连接状态
            if not client.is_connected:
                print(f"❌ 执行命令 {i+1} 前连接已断开")
                break
            
            # 执行命令
            async for chunk in client.execute_command_stream(cmd):
                if chunk.get("state") == "complete":
                    break
            
            # 检查连接是否仍然存在
            current_connection_info = client._connection_manager.get_connection_info()
            
            if (current_connection_info['connection_state'] == initial_connection_info['connection_state'] and
                current_connection_info['is_connected'] == initial_connection_info['is_connected']):
                print(f"✅ 命令 {i+1} 执行后连接状态保持正常")
            else:
                print(f"❌ 命令 {i+1} 执行后连接状态发生变化")
                print(f"   初始: {initial_connection_info}")
                print(f"   当前: {current_connection_info}")
        
        print("✅ 连接持久性测试完成")
        
        # 最后关闭
        await client.shutdown()
        
    except Exception as e:
        print(f"连接持久性测试出错: {e}")

async def main():
    """主测试函数"""
    print("开始正确的状态转换测试...")
    
    await test_correct_state_transitions()
    await test_connection_persistence()
    
    print("\n正确的状态转换测试完成！")

if __name__ == "__main__":
    asyncio.run(main())
