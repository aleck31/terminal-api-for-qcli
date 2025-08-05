#!/usr/bin/env python3
"""
Q CLI 交互演示应用 - 使用 TerminalAPIClient 的连接复用功能
"""

import asyncio
import sys
import time

from api import TerminalAPIClient, TerminalType

class QCLIInteractiveDemo:
    """Q CLI 交互演示类 - 使用连接复用"""
    
    def __init__(self, host: str = "localhost", port: int = 8081, 
                 username: str = "demo", password: str = "password123"):
        self.client = TerminalAPIClient(
            host=host,
            port=port,
            username=username,
            password=password,
            terminal_type=TerminalType.QCLI,
            format_output=True
        )
        self.session_start_time = time.time()
        
        # 设置流式输出回调
        self.client.set_output_callback(self._on_streaming_output)
    
    def _on_streaming_output(self, output: str):
        """流式输出回调"""
        # 只显示有意义的输出片段，过滤控制字符
        if output.strip() and len(output.strip()) > 2:
            # 过滤掉旋转指示器和控制字符
            if not any(char in output for char in '⠸⠼⠴⠦⠧⠇⠏⠋⠙⠹'):
                print(f"📤 {repr(output[:50])}", end="", flush=True)
    
    async def start_interactive_session(self):
        """启动交互式会话"""
        print("🚀 Q CLI 交互演示启动 (连接复用版)")
        print("=" * 60)
        
        print("⏳ 正在连接并初始化 Q CLI...")
        print("💡 提示: Q CLI 需要加载 MCP 服务器，大约需要 30 秒，请耐心等待...")
        
        async with self.client:
            print("✅ 终端客户端已启动")
            
            print("\n" + "=" * 60)
            print("💬 Q CLI 交互会话开始")
            print("=" * 60)
            print("💡 提示:")
            print("  - 直接输入问题与 Q CLI 对话")
            print("  - 输入 'new' 重新连接（连接到同一个 Q CLI 实例）")
            print("  - 输入 'stats' 查看会话信息")
            print("  - 输入 'test' 运行测试问题")
            print("  - 输入 'quit' 或 'exit' 退出")
            print("  💡 连接复用通过 tmux 会话共享实现")
            print("=" * 60)
            
            while True:
                try:
                    user_input = input("\n🤔 你: ").strip()
                    
                    if not user_input:
                        continue
                    
                    if user_input.lower() in ['quit', 'exit', 'q']:
                        print("👋 结束会话")
                        break
                    
                    if user_input.lower() == 'new':
                        await self._create_new_connection()
                        continue
                    
                    if user_input.lower() == 'stats':
                        self._show_stats()
                        continue
                    
                    if user_input.lower() == 'test':
                        await self._run_test_questions()
                        continue
                    
                    # 执行查询
                    await self._execute_query(user_input)
                    
                except KeyboardInterrupt:
                    print("\n\n👋 用户中断，结束会话")
                    break
                except Exception as e:
                    print(f"\n❌ 会话错误: {e}")
    
    async def _create_new_connection(self):
        """创建新连接（实际上每次都是新连接，这个功能由 tmux 会话共享实现）"""
        print("\n🆕 重新连接到 Q CLI...")
        print("💡 提示: 由于使用了 tmux 会话共享，你将连接到同一个 Q CLI 实例")
        
        try:
            # 断开当前连接
            if self.client.is_connected:
                await self.client.disconnect()
            
            # 重新连接
            await self.client.connect()
            print("✅ 重新连接成功！")
        except Exception as e:
            print(f"❌ 重新连接失败: {e}")
    
    async def _execute_query(self, question: str):
        """执行查询"""
        print(f"\n⏳ 正在查询...")
        
        try:
            result = await self.client.execute_command(question, timeout=45.0)
            
            if result.success:
                print(f"\n🤖 Q CLI 回复 ({result.execution_time:.1f}s):")
                print("-" * 50)
                print(result.formatted_output)
                print("-" * 50)
                print(f"📊 响应长度: {len(result.output)} 字符")
                
            else:
                print(f"\n❌ 查询失败 ({result.execution_time:.1f}s): {result.error}")
                if result.output:
                    print(f"部分输出: {result.output[:200]}...")
                    
        except Exception as e:
            print(f"\n❌ 查询异常: {e}")
    
    async def _run_test_questions(self):
        """运行测试问题"""
        test_questions = [
            "What is 2+2?",
            "Hello, how are you?",
            "What is Python?",
            "Explain AWS Lambda in one sentence"
        ]
        
        print(f"\n🧪 运行测试问题 ({len(test_questions)} 个)...")
        print("💡 所有查询都连接到同一个 Q CLI 实例（通过 tmux 会话共享）")
        
        for i, question in enumerate(test_questions, 1):
            print(f"\n--- 测试 {i}/{len(test_questions)} ---")
            print(f"问题: {question}")
            await self._execute_query(question)
            
            if i < len(test_questions):
                print("⏳ 等待 2 秒...")
                await asyncio.sleep(2)
        
        print(f"\n✅ 测试完成")
    
    def _show_stats(self):
        """显示真实的连接信息"""
        session_duration = time.time() - self.session_start_time
        
        print(f"\n📊 会话信息:")
        print(f"  🔗 连接状态: {'已连接' if self.client.is_connected else '未连接'}")
        print(f"  🎯 终端类型: {self.client.terminal_type.value}")
        print(f"  🕐 会话时长: {session_duration:.1f}秒")
        print(f"  💡 连接复用: 通过 tmux 会话共享实现")
        print(f"  📝 说明: 每次运行应用都会创建新的 WebSocket 连接，")
        print(f"       但连接到同一个持久化的 Q CLI 实例")

async def main():
    """主函数"""
    demo = QCLIInteractiveDemo()
    
    try:
        await demo.start_interactive_session()
        
    except Exception as e:
        print(f"❌ 程序异常: {e}")
        import traceback
        traceback.print_exc()
        return 1
    
    finally:
        # 显示最终统计
        print("\n" + "=" * 60)
        print("📋 最终统计")
        print("=" * 60)
        demo._show_stats()
    
    return 0

if __name__ == "__main__":
    try:
        exit_code = asyncio.run(main())
        sys.exit(exit_code)
    except KeyboardInterrupt:
        print("\n👋 程序被用户中断")
        sys.exit(1)
    except Exception as e:
        print(f"❌ 程序错误: {e}")
        sys.exit(1)
