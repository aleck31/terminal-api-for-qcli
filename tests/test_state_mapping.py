#!/usr/bin/env python3
"""
测试状态映射机制
验证连接状态变化是否正确映射为业务状态
"""

import asyncio
import logging
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from api.terminal_api_client import TerminalAPIClient, TerminalBusinessState
from api.connection_manager import ConnectionState
from api.command_executor import TerminalType

# 设置日志
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

async def test_state_mapping():
    """测试状态映射机制"""
    print("\n=== 测试状态映射机制 ===")
    
    client = TerminalAPIClient(host="localhost", port=7681)
    
    # 记录状态变化
    business_state_changes = []
    connection_state_changes = []
    
    # 跟踪业务状态变化
    original_set_state = client._set_state
    def track_business_state(new_state):
        business_state_changes.append(new_state.value)
        print(f"业务状态变化: {new_state.value}")
        original_set_state(new_state)
    client._set_state = track_business_state
    
    # 跟踪连接状态变化
    original_set_conn_state = client._connection_manager._set_connection_state
    def track_connection_state(new_state):
        connection_state_changes.append(new_state.value)
        print(f"连接状态变化: {new_state.value}")
        original_set_conn_state(new_state)
    client._connection_manager._set_connection_state = track_connection_state
    
    try:
        print("1. 初始化终端...")
        success = await client.initialize()
        
        if success:
            print("2. 初始化成功，当前状态:")
            print(f"   业务状态: {client.state.value}")
            print(f"   连接状态: {client._connection_manager.state.value}")
            
            # 执行一个命令确保正常工作
            print("3. 执行测试命令...")
            async for chunk in client.execute_command_stream("echo 'test'"):
                if chunk.get("state") == "complete":
                    break
            
            print("4. 模拟连接断开...")
            # 直接断开连接来测试状态映射
            await client._connection_manager.disconnect()
            
            print("5. 断开后状态:")
            print(f"   业务状态: {client.state.value}")
            print(f"   连接状态: {client._connection_manager.state.value}")
            
            # 尝试重新连接
            print("6. 尝试重新连接...")
            reconnect_success = await client._connection_manager.connect()
            if reconnect_success:
                print("7. 重连成功，状态:")
                print(f"   业务状态: {client.state.value}")
                print(f"   连接状态: {client._connection_manager.state.value}")
            
        print(f"\n业务状态变化序列: {business_state_changes}")
        print(f"连接状态变化序列: {connection_state_changes}")
        
        # 验证状态映射是否正确
        if "unavailable" in business_state_changes:
            print("✅ 连接断开时正确设置为不可用状态")
        else:
            print("❌ 连接断开时未正确设置状态")
        
        # 检查是否有状态恢复
        unavailable_index = -1
        idle_after_unavailable = False
        for i, state in enumerate(business_state_changes):
            if state == "unavailable":
                unavailable_index = i
            elif state == "idle" and unavailable_index >= 0 and i > unavailable_index:
                idle_after_unavailable = True
                break
        
        if idle_after_unavailable:
            print("✅ 重连后正确恢复为空闲状态")
        else:
            print("❌ 重连后未正确恢复状态")
            
    except Exception as e:
        print(f"测试出错: {e}")
        import traceback
        traceback.print_exc()

async def test_error_state_handling():
    """测试错误状态处理"""
    print("\n=== 测试错误状态处理 ===")
    
    client = TerminalAPIClient(host="localhost", port=9999)  # 使用不存在的端口
    
    # 记录状态变化
    state_changes = []
    original_set_state = client._set_state
    def track_state(new_state):
        state_changes.append(new_state.value)
        print(f"状态变化: {new_state.value}")
        original_set_state(new_state)
    client._set_state = track_state
    
    try:
        print("1. 尝试连接到不存在的端口...")
        success = await client.initialize()
        
        print(f"2. 初始化结果: {success}")
        print(f"   当前状态: {client.state.value}")
        
        print(f"\n状态变化序列: {state_changes}")
        
        if "error" in state_changes:
            print("✅ 连接失败时正确设置为错误状态")
        else:
            print("❌ 连接失败时未正确设置错误状态")
            
    except Exception as e:
        print(f"测试出错: {e}")

async def main():
    """主测试函数"""
    print("开始状态映射测试...")
    
    await test_state_mapping()
    await test_error_state_handling()
    
    print("\n状态映射测试完成！")

if __name__ == "__main__":
    asyncio.run(main())
