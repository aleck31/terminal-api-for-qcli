#!/usr/bin/env python3
import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

from api.terminal_client import TerminalAPIClient

def test_api_decode():
    client = TerminalAPIClient()
    command = "echo 'test'"
    
    count = 0
    for output_type, content, metadata in client.execute_command(command, timeout=10):
        count += 1
        if count > 5:
            break
        content_repr = repr(content)
        if len(content_repr) > 100:
            content_repr = content_repr[:100] + "..."
        print(f"[{output_type}] {content_repr}")
        
        # 检查是否是解码后的UTF-8文本
        if isinstance(content, str):
            try:
                import base64
                base64.b64decode(content)
                print("  ❌ 仍是base64编码")
            except:
                print("  ✅ 已解码为UTF-8文本")
        
        if output_type == "summary":
            break

if __name__ == "__main__":
    test_api_decode()