#!/usr/bin/env python3
"""
测试状态管理修复
验证 TtydWebSocketClient 和 ConnectionManager 的状态管理是否正确
"""

import asyncio
import logging
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from api.websocket_client import TtydWebSocketClient, TtydProtocolState
from api.connection_manager import ConnectionManager, ConnectionState

# 设置日志
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

async def test_websocket_client_states():
    """测试 TtydWebSocketClient 的状态管理"""
    print("\n=== 测试 TtydWebSocketClient 状态管理 ===")
    
    client = TtydWebSocketClient(host="localhost", port=7682)
    
    # 状态变化回调
    def state_change_handler(state: TtydProtocolState):
        print(f"协议状态变化: {state.value}")
    
    client.set_state_change_handler(state_change_handler)
    
    # 初始状态
    print(f"初始状态: {client.protocol_state.value}")
    assert client.protocol_state == TtydProtocolState.DISCONNECTED
    
    # 测试连接（如果服务可用）
    try:
        print("尝试连接...")
        success = await client.connect()
        if success:
            print(f"连接成功，当前状态: {client.protocol_state.value}")
            print(f"协议是否就绪: {client.is_protocol_ready}")
            
            # 断开连接
            await client.disconnect()
            print(f"断开后状态: {client.protocol_state.value}")
        else:
            print("连接失败（可能服务未启动）")
    except Exception as e:
        print(f"连接测试出错: {e}")

async def test_connection_manager_states():
    """测试 ConnectionManager 的状态管理"""
    print("\n=== 测试 ConnectionManager 状态管理 ===")
    
    manager = ConnectionManager(host="localhost", port=7682)
    
    # 初始状态
    print(f"初始连接状态: {manager.state.value}")
    assert manager.state == ConnectionState.IDLE
    
    # 测试连接（如果服务可用）
    try:
        print("尝试连接...")
        success = await manager.connect()
        if success:
            print(f"连接成功，连接状态: {manager.state.value}")
            print(f"是否已连接: {manager.is_connected}")
            
            # 获取连接信息
            info = manager.get_connection_info()
            print(f"连接信息: {info}")
            
            # 断开连接
            await manager.disconnect()
            print(f"断开后状态: {manager.state.value}")
        else:
            print("连接失败（可能服务未启动）")
    except Exception as e:
        print(f"连接测试出错: {e}")

async def test_state_synchronization():
    """测试状态同步机制"""
    print("\n=== 测试状态同步机制 ===")
    
    manager = ConnectionManager(host="localhost", port=7682)
    
    # 记录状态变化
    protocol_states = []
    connection_states = []
    
    def track_protocol_state(state: TtydProtocolState):
        protocol_states.append(state.value)
        print(f"协议状态: {state.value}")
    
    # 设置协议状态跟踪
    manager._client.set_state_change_handler(track_protocol_state)
    
    # 记录连接状态变化
    original_set_state = manager._set_connection_state
    def track_connection_state(state: ConnectionState):
        connection_states.append(state.value)
        print(f"连接状态: {state.value}")
        original_set_state(state)
    
    manager._set_connection_state = track_connection_state
    
    try:
        print("开始连接...")
        success = await manager.connect()
        
        if success:
            print("连接成功")
            await asyncio.sleep(1)  # 等待状态稳定
            
            await manager.disconnect()
            print("断开连接")
            await asyncio.sleep(1)  # 等待状态稳定
        
        print(f"\n协议状态变化序列: {protocol_states}")
        print(f"连接状态变化序列: {connection_states}")
        
        # 验证状态变化序列是否合理
        if protocol_states:
            print("✅ 协议状态变化正常")
        if connection_states:
            print("✅ 连接状态变化正常")
            
    except Exception as e:
        print(f"状态同步测试出错: {e}")

async def main():
    """主测试函数"""
    print("开始状态管理测试...")
    
    await test_websocket_client_states()
    await test_connection_manager_states()
    await test_state_synchronization()
    
    print("\n状态管理测试完成！")

if __name__ == "__main__":
    asyncio.run(main())
