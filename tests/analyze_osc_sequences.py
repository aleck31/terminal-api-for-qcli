#!/usr/bin/env python3
"""
分析 ttyd 输出中的 OSC 序列，寻找命令完成的标准标志
"""

import asyncio
import sys
import os
import re

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from api import TerminalAPIClient

class OSCAnalyzer:
    """OSC 序列分析器"""
    
    def __init__(self):
        self.raw_messages = []
        self.osc_sequences = []
    
    def analyze_message(self, message):
        """分析单个消息中的 OSC 序列"""
        self.raw_messages.append(message)
        
        if isinstance(message, (str, bytes)):
            # 处理字节消息
            if isinstance(message, bytes):
                try:
                    data = message.decode('utf-8', errors='replace')
                except:
                    return
            else:
                data = message
            
            print(f"📨 原始消息: {repr(data)}")
            
            if len(data) > 1 and data[0] == '0':
                payload = data[1:]
                print(f"📦 载荷数据: {repr(payload)}")
                
                # 查找 OSC 序列 (ESC ] ... BEL) - 修复正则表达式
                # OSC 序列格式: \x1b] ... \x07
                osc_pattern = r'\x1b\]([^\x07]*)\x07'
                matches = re.findall(osc_pattern, payload)
                
                for match in matches:
                    self.osc_sequences.append(match)
                    print(f"🔍 发现 OSC 序列: {match}")
                
                # 也检查是否有其他控制序列
                if '\x1b' in payload:
                    print(f"🎛️  包含转义序列的载荷: {repr(payload)}")
            
            elif len(data) > 1:
                print(f"📋 非输出消息 (类型 {data[0]}): {repr(data[1:])}")
    
    def get_summary(self):
        """获取分析摘要"""
        print(f"\n📊 分析摘要:")
        print(f"   总消息数: {len(self.raw_messages)}")
        print(f"   OSC 序列数: {len(self.osc_sequences)}")
        
        # 统计 OSC 序列类型
        osc_types = {}
        for seq in self.osc_sequences:
            if ';' in seq:
                seq_type = seq.split(';')[0]
            else:
                seq_type = seq
            osc_types[seq_type] = osc_types.get(seq_type, 0) + 1
        
        print(f"   OSC 序列类型统计:")
        for seq_type, count in sorted(osc_types.items()):
            print(f"     {seq_type}: {count} 次")

async def analyze_command_lifecycle(command: str):
    """分析单个命令的完整生命周期"""
    print(f"🚀 分析命令生命周期: {command}")
    print("=" * 60)
    
    analyzer = OSCAnalyzer()
    
    client = TerminalAPIClient(
        host="localhost",
        port=7681,
        username="demo",
        password="password123",
        format_output=False
    )
    
    # 修改 WebSocket 客户端的消息处理
    original_handle_message = client.ws_client._handle_message
    
    async def tracking_handle_message(message):
        analyzer.analyze_message(message)
        await original_handle_message(message)
    
    client.ws_client._handle_message = tracking_handle_message
    
    try:
        await client.connect()
        print("✅ 连接成功，开始执行命令\n")
        
        # 执行命令
        result = await client.execute_command(command, timeout=10.0)
        
        print(f"\n📋 命令执行结果:")
        print(f"   成功: {result.success}")
        print(f"   执行时间: {result.execution_time:.3f}秒")
        print(f"   输出: {repr(result.output)}")
        
        # 分析 OSC 序列
        analyzer.get_summary()
        
        # 查找可能的命令完成标志
        print(f"\n🎯 寻找命令完成标志:")
        completion_indicators = []
        
        for seq in analyzer.osc_sequences:
            if any(keyword in seq.lower() for keyword in ['end', 'complete', 'done', 'prompt', 'newcmd']):
                completion_indicators.append(seq)
        
        if completion_indicators:
            print("   可能的完成标志:")
            for indicator in completion_indicators:
                print(f"     - {indicator}")
        else:
            print("   未找到明显的完成标志")
        
    except Exception as e:
        print(f"❌ 错误: {e}")
    finally:
        await client.disconnect()

async def main():
    """主函数"""
    test_commands = [
        "echo 'hello'",
        "pwd", 
        "date"
    ]
    
    for command in test_commands:
        await analyze_command_lifecycle(command)
        print("\n" + "="*80 + "\n")
        await asyncio.sleep(1)

if __name__ == "__main__":
    asyncio.run(main())
