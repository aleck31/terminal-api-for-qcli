#!/usr/bin/env python3
"""
测试新的流式接口
"""

import asyncio
import json
from api import TerminalAPIClient
from api.command_executor import TerminalType

async def test_qcli_stream():
    """测试 Q CLI 流式接口"""
    print("🧪 测试 Q CLI 流式接口")
    print("=" * 60)
    
    async with TerminalAPIClient(
        host="localhost",
        port=7682,
        username="demo",
        password="password123",
        terminal_type=TerminalType.QCLI,
        format_output=True
    ) as client:
        
        print("✅ 连接成功")
        
        # 等待初始化
        await asyncio.sleep(3)
        
        question = "What is Lambda?"
        print(f"📤 发送问题: {question}")
        print("-" * 40)
        
        response_parts = []
        chunk_count = 0
        
        try:
            async for chunk in client.execute_command_stream(question, timeout=30.0):
                chunk_count += 1
                
                # 显示流式输出
                if chunk.get("state") == "thinking":
                    print("🤔 思考中...", end="\r", flush=True)
                
                elif chunk.get("is_content") and chunk.get("content"):
                    content = chunk["content"]
                    response_parts.append(content)
                    current_response = " ".join(response_parts)
                    print(f"\r💬 回复: {current_response[:100]}{'...' if len(current_response) > 100 else ''}", end="", flush=True)
                
                elif chunk.get("state") == "complete":
                    final_response = " ".join(response_parts)
                    print(f"\n\n✅ 完成!")
                    print(f"📊 执行时间: {chunk.get('execution_time', 0):.2f}秒")
                    print(f"📈 总块数: {chunk_count}")
                    print(f"📝 回复长度: {len(final_response)} 字符")
                    print(f"🎯 成功: {chunk.get('command_success', False)}")
                    
                    if chunk.get("error"):
                        print(f"❌ 错误: {chunk['error']}")
                    
                    print("\n" + "-" * 40)
                    print("完整回复:")
                    print(final_response[:500] + ("..." if len(final_response) > 500 else ""))
                    break
                
                elif chunk.get("state") == "error":
                    print(f"\n❌ 执行出错: {chunk.get('error')}")
                    break
                
                # 显示调试信息（可选）
                if chunk_count <= 5 or chunk_count % 20 == 0:
                    print(f"\n[调试] 块 #{chunk_count}: {json.dumps(chunk, ensure_ascii=False)[:100]}...")
        
        except Exception as e:
            print(f"\n❌ 流式处理出错: {e}")

async def test_bash_stream():
    """测试 Bash 流式接口"""
    print("\n🧪 测试 Bash 流式接口")
    print("=" * 60)
    
    async with TerminalAPIClient(
        host="localhost",
        port=7681,
        username="demo",
        password="password123",
        terminal_type=TerminalType.GENERIC,
        format_output=True
    ) as client:
        
        print("✅ 连接成功")
        
        command = "echo 'Hello World' && sleep 1 && echo 'Done'"
        print(f"📤 执行命令: {command}")
        print("-" * 40)
        
        output_parts = []
        chunk_count = 0
        
        try:
            async for chunk in client.execute_command_stream(command, timeout=10.0):
                chunk_count += 1
                
                if chunk.get("content"):
                    content = chunk["content"]
                    output_parts.append(content)
                    print(f"📄 输出: {repr(content)}")
                
                elif chunk.get("state") == "complete":
                    print(f"\n✅ 完成!")
                    print(f"📊 执行时间: {chunk.get('execution_time', 0):.2f}秒")
                    print(f"📈 总块数: {chunk_count}")
                    print(f"🎯 成功: {chunk.get('command_success', False)}")
                    
                    final_output = "".join(output_parts)
                    print(f"完整输出: {repr(final_output)}")
                    break
        
        except Exception as e:
            print(f"\n❌ 流式处理出错: {e}")

async def main():
    try:
        await test_qcli_stream()
        await test_bash_stream()
    except Exception as e:
        print(f"❌ 测试失败: {e}")
        raise

if __name__ == "__main__":
    asyncio.run(main())
