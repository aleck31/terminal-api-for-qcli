#!/usr/bin/env python3
"""
ttyd 问题诊断脚本
兼容 websockets 15.x 版本
"""

import asyncio
import websockets
import json
import base64
import sys
import time

async def diagnose_ttyd_connection(url: str, username: str, password: str):
    """诊断 ttyd 连接问题"""
    
    print("=== ttyd WebSocket 连接诊断 v3 ===\n")
    
    # 1. 创建认证令牌
    credential = f"{username}:{password}"
    auth_token = base64.b64encode(credential.encode()).decode()
    print(f"1. 认证信息:")
    print(f"   用户名: {username}")
    print(f"   密码: {password}")
    print(f"   Base64令牌: {auth_token}")
    print(f"   解码验证: {base64.b64decode(auth_token).decode()}")
    print()
    
    try:
        # 2. 建立 WebSocket 连接（包含认证头）
        print(f"2. 连接到: {url}")
        
        # 创建认证头
        auth_header = f"Basic {auth_token}"
        
        print(f"   认证头: {auth_header}")
        
        # 使用 websockets 15.x 的新 API
        websocket = await websockets.connect(
            url, 
            subprotocols=['tty'],
            additional_headers={
                "Authorization": auth_header
            }
        )
        print("   ✓ WebSocket 连接成功")
        print()
        
        # 3. 发送初始化消息
        init_message = {
            "AuthToken": auth_token,
            "columns": 80,
            "rows": 24
        }
        message_json = json.dumps(init_message)
        print(f"3. 发送初始化消息:")
        print(f"   消息内容: {message_json}")
        
        await websocket.send(message_json.encode())
        print("   ✓ 初始化消息已发送")
        print()
        
        # 4. 等待并分析服务器响应
        print("4. 等待服务器响应...")
        response_count = 0
        start_time = time.time()
        
        try:
            # 设置超时，等待初始响应
            while time.time() - start_time < 10:  # 10秒超时
                try:
                    message = await asyncio.wait_for(websocket.recv(), timeout=1.0)
                    response_count += 1
                    
                    print(f"   响应 #{response_count}:")
                    if isinstance(message, bytes):
                        if len(message) > 0:
                            command = chr(message[0])
                            data = message[1:] if len(message) > 1 else b''
                            
                            print(f"     命令类型: '{command}' (0x{ord(command):02x})")
                            print(f"     数据长度: {len(data)} 字节")
                            
                            if command == '0':  # OUTPUT
                                output = data.decode('utf-8', errors='ignore')
                                print(f"     终端输出: {repr(output)}")
                                if output.strip():
                                    print(f"     可见内容: {output}")
                            elif command == '1':  # SET_WINDOW_TITLE
                                title = data.decode('utf-8', errors='ignore')
                                print(f"     窗口标题: {title}")
                            elif command == '2':  # SET_PREFERENCES
                                prefs = data.decode('utf-8', errors='ignore')
                                print(f"     客户端偏好: {prefs}")
                            else:
                                print(f"     未知命令，原始数据: {data}")
                        else:
                            print("     空消息")
                    else:
                        print(f"     文本消息: {message}")
                    print()
                    
                    # 如果收到了初始消息，跳出等待循环
                    if response_count >= 2:  # 通常会收到 SET_WINDOW_TITLE 和 SET_PREFERENCES
                        break
                        
                except asyncio.TimeoutError:
                    continue
                    
        except websockets.exceptions.ConnectionClosed as e:
            print(f"   ✗ 连接被服务器关闭: {e}")
            print("   这通常表示认证失败或其他错误")
            return False
            
        if response_count == 0:
            print("   ✗ 10秒内未收到任何响应")
            print("   可能的原因:")
            print("     - 认证失败")
            print("     - 服务器配置问题")
            print("     - 网络问题")
            return False
        
        print(f"   ✓ 收到 {response_count} 个初始响应")
        print()
        
        # 5. 发送测试命令
        print("5. 发送测试命令...")
        test_commands = [
            "echo 'Hello World'\n",
            "pwd\n",
            "date\n",
            "whoami\n"
        ]
        
        for i, cmd in enumerate(test_commands, 1):
            print(f"   发送命令 #{i}: {repr(cmd.strip())}")
            message = b'0' + cmd.encode()
            await websocket.send(message)
            
            # 等待响应
            output_received = False
            for _ in range(5):  # 最多等待5次，每次1秒
                try:
                    response = await asyncio.wait_for(websocket.recv(), timeout=1.0)
                    if isinstance(response, bytes) and len(response) > 0:
                        command = chr(response[0])
                        data = response[1:]
                        if command == '0':  # OUTPUT
                            output = data.decode('utf-8', errors='ignore')
                            print(f"     收到输出: {repr(output)}")
                            if output.strip():
                                print(f"     内容: {output}", end='')
                            output_received = True
                        else:
                            print(f"     收到其他响应: {command}")
                    else:
                        print("     收到空响应")
                except asyncio.TimeoutError:
                    break
            
            if not output_received:
                print("     ✗ 未收到输出响应")
            
            await asyncio.sleep(0.5)
        
        print()
        print("6. 诊断完成")
        
        await websocket.close()
        return True
        
    except websockets.exceptions.InvalidURI:
        print(f"   ✗ 无效的 WebSocket URL: {url}")
        return False
    except ConnectionRefusedError:
        print(f"   ✗ 连接被拒绝，请检查:")
        print(f"     - ttyd 服务是否运行")
        print(f"     - 端口是否正确")
        print(f"     - 防火墙设置")
        return False
    except websockets.exceptions.WebSocketException as e:
        print(f"   ✗ WebSocket 错误: {e}")
        if "401" in str(e):
            print("   认证失败，请检查用户名和密码")
        elif "403" in str(e):
            print("   访问被禁止")
        return False
    except Exception as e:
        print(f"   ✗ 连接失败: {e}")
        print(f"   错误类型: {type(e).__name__}")
        return False

async def main():
    if len(sys.argv) < 4:
        print("用法: python diagnose_ttyd_issue_v3.py <ws_url> <username> <password>")
        print("示例: python diagnose_ttyd_issue_v3.py ws://localhost:7681/ws demo password123")
        sys.exit(1)
    
    url = sys.argv[1]
    username = sys.argv[2]
    password = sys.argv[3]
    
    success = await diagnose_ttyd_connection(url, username, password)
    
    if success:
        print("✓ 诊断完成，连接正常")
    else:
        print("✗ 诊断发现问题，请检查上述错误信息")

if __name__ == "__main__":
    asyncio.run(main())
