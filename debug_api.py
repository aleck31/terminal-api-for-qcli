#!/usr/bin/env python3
"""
调试API返回内容的格式
"""

import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), 'web'))

from web.api.terminal_client import TerminalAPIClient

def debug_api_output():
    """调试API输出格式"""
    print("🔍 调试API输出格式...")
    
    client = TerminalAPIClient()
    
    # 测试简单命令
    command = "echo 'Hello World'"
    print(f"执行命令: {command}")
    print("=" * 50)
    
    try:
        count = 0
        for output_type, content, metadata in client.execute_command(command, timeout=15):
            count += 1
            print(f"\n--- 消息 {count} ---")
            print(f"类型: {output_type}")
            print(f"内容类型: {type(content)}")
            print(f"内容长度: {len(str(content))}")
            print(f"原始内容: {repr(content)}")
            
            # 如果是字符串，尝试检查是否是base64
            if isinstance(content, str) and len(content) > 10:
                try:
                    import base64
                    decoded = base64.b64decode(content).decode('utf-8')
                    print(f"Base64解码: {repr(decoded)}")
                    print(f"可读内容: {decoded}")
                except:
                    print("不是有效的base64")
            
            if metadata:
                print(f"元数据: {metadata}")
            
            # 只显示前10条消息
            if count >= 10:
                print("\n... (限制显示前10条消息)")
                break
                
    except Exception as e:
        print(f"❌ 调试失败: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    debug_api_output()