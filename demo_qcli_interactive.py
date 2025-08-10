#!/usr/bin/env python3
"""
Q CLI 交互式演示
专门用于测试 Q CLI 的流式输出和消息类型识别
"""

import asyncio
import sys
import os
import signal
from typing import Optional

# 添加项目根目录到路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from api import TerminalAPIClient
from api.data_structures import TerminalType

class QCLIInteractiveDemo:
    """Q CLI 交互式演示"""
    
    def __init__(self):
        self.client: Optional[TerminalAPIClient] = None
        self.running = True
        
    async def setup_client(self):
        """设置 Q CLI 客户端连接"""
        print("🔌 正在连接到 Q CLI Terminal API...")
        
        self.client = TerminalAPIClient(
            host="localhost",
            port=7682,  # Q CLI 端口
            username="demo",
            password="password123",
            terminal_type=TerminalType.QCLI,
            format_output=True
        )
        
        print(f"📡 当前业务状态: {self.client.terminal_state.value}")
        print("⏳ 开始初始化连接...")
        
        success = await self.client.initialize()
        
        print(f"📡 初始化后业务状态: {self.client.terminal_state.value}")
        
        if success:
            print("✅ Q CLI 连接成功！")
            print("💡 提示：输入 '/help' 查看帮助，输入 '/quit' 或 '/exit' 退出")
            return True
        else:
            print("❌ Q CLI 连接失败，请检查 Q CLI ttyd 服务是否启动")
            print("   启动命令: ./ttyd/ttyd-service.sh start qcli 7682")
            return False
    
    def show_help(self):
        """显示帮助信息"""
        help_text = """
🤖 Q CLI 交互式演示

📝 使用方法:
   - 直接输入任何问题或命令，Q CLI 会智能回答
   - 输出将实时显示思考过程、工具使用和回复内容
   - 输入 '/help' 显示此帮助
   - 输入 '/quit' 或 '/exit' 退出程序
   - 按 Ctrl+C 也可以退出

🌟 示例问题:
   What is AWS Lambda?                    # 询问 AWS 服务
   How to create an S3 bucket?            # 询问操作步骤
   Show me the current time               # 简单查询
   What are the benefits of serverless?   # 概念性问题
   Create a Lambda function               # 请求创建资源
   List my EC2 instances                  # 查询资源

🎯 消息类型说明:
   🤔 thinking   - AI 正在思考
   🔧 tool_use   - 正在使用工具
   💬 content    - 回复内容
   ✅ complete   - 回复完成
   ❌ error      - 出现错误

⚠️  注意:
   - Q CLI 可能需要一些时间来思考和回复
   - 某些问题可能需要使用工具来获取信息
   - 请耐心等待完整的回复
        """
        print(help_text)
    
    def setup_signal_handler(self):
        """设置信号处理器"""
        def signal_handler(signum, frame):
            print("\n\n👋 收到退出信号，正在清理...")
            self.running = False
            # 立即退出，不等待清理完成
            import sys
            sys.exit(0)
        
        signal.signal(signal.SIGINT, signal_handler)
        signal.signal(signal.SIGTERM, signal_handler)
    
    async def execute_qcli_command_with_stream(self, question: str):
        """执行 Q CLI 命令并显示详细的流式输出"""
        if not self.client:
            print("❌ 客户端未连接")
            return
        
        print("🤖 Q CLI 回复:")
        print("=" * 60)
        
        try:
            start_time = asyncio.get_event_loop().time()
            success = False
            error_msg = None
            execution_time = 0
            content_received = False
            
            # 使用统一数据流架构API处理 Q CLI 消息
            async for chunk in self.client.execute_command_stream(question, silence_timeout=120.0):
                chunk_type = chunk.get("type")
                content = chunk.get("content", "")
                metadata = chunk.get("metadata", {})
                
                # 根据消息类型显示不同的状态
                if chunk_type == "thinking":
                    print("🤔 AI 正在思考...", flush=True)
                
                elif chunk_type == "tool_use":
                    tool_name = metadata.get("tool_name", "unknown")
                    print(f"🔧 正在使用工具: {tool_name}", flush=True)
                
                elif chunk_type == "content":
                    if not content_received:
                        print("💬 回复内容:")
                        print("-" * 40)
                        content_received = True
                    
                    # 不要使用 strip()，直接输出内容以保留空格
                    if content:
                        print(content, end='', flush=True)
                
                elif chunk_type == "complete":
                    success = metadata.get("command_success", True)
                    execution_time = metadata.get("execution_time", 
                                                 asyncio.get_event_loop().time() - start_time)
                    break
                
                elif chunk_type == "error":
                    success = False
                    error_msg = metadata.get("error_message", "未知错误")
                    execution_time = asyncio.get_event_loop().time() - start_time
                    break
            
            # 确保输出完整
            if content_received:
                print()  # 换行
                print("-" * 40)
            
            print("=" * 60)
            
            if success:
                print(f"✅ Q CLI 回复完成 (耗时: {execution_time:.3f}秒)")
            else:
                print(f"❌ Q CLI 回复失败: {error_msg or '未知错误'}")
            
        except Exception as e:
            print(f"\n❌ 执行出错: {e}")
        
        print()  # 额外换行，分隔下一个问题
    
    async def run_interactive_loop(self):
        """运行 Q CLI 交互式循环"""
        print("\n🎯 进入 Q CLI 交互模式...")
        print("=" * 60)
        
        while self.running:
            try:
                # 获取用户输入
                question = input("🤖 问题 > ").strip()
                
                if not question:
                    continue
                
                # 处理特殊命令
                if question.lower() in ['/quit', '/exit', 'exit']:
                    break
                elif question.lower() in ['/help', 'h', '?']:
                    self.show_help()
                    continue
                elif question.lower() == 'clear':
                    os.system('clear' if os.name == 'posix' else 'cls')
                    continue
                
                # 执行 Q CLI 问题
                await self.execute_qcli_command_with_stream(question)
                
                # 短暂等待，确保输出完整
                await asyncio.sleep(0.1)
                
            except EOFError:
                # Ctrl+D
                print("\n👋 收到 EOF，退出程序")
                break
            except KeyboardInterrupt:
                # Ctrl+C
                print("\n👋 收到中断信号，退出程序")
                break
            except Exception as e:
                print(f"❌ 交互循环出错: {e}")
                continue
    
    async def cleanup(self):
        """清理资源"""
        if self.client:
            print("🔌 断开 Q CLI 连接...")
            try:
                # 添加超时保护，避免清理过程阻塞
                await asyncio.wait_for(self.client.shutdown(), timeout=3.0)
                print("✅ Q CLI 连接已断开")
            except asyncio.TimeoutError:
                print("⚠️ 清理超时，强制退出")
            except Exception as e:
                print(f"⚠️ 清理过程出错: {e}")
                print("✅ 强制断开连接")
    
    async def run(self):
        """运行 Q CLI 演示"""
        print("🤖 Q CLI 交互式演示")
        print("=" * 60)
        
        # 设置信号处理
        self.setup_signal_handler()
        
        try:
            # 建立 Q CLI 连接
            if not await self.setup_client():
                return
            
            # 运行交互循环
            await self.run_interactive_loop()
            
        except Exception as e:
            print(f"❌ 程序运行出错: {e}")
        finally:
            # 清理资源
            await self.cleanup()

async def main():
    """主函数"""
    demo = QCLIInteractiveDemo()
    await demo.run()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n👋 程序被中断")
    except Exception as e:
        print(f"❌ 程序启动失败: {e}")
        print("\n💡 请确保 Q CLI ttyd 服务已启动:")
        print("   ./ttyd/ttyd-service.sh start qcli 7682")
