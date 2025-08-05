#!/usr/bin/env python3
"""
Terminal API 交互式流式输出演示
用户输入命令，实时显示流式输出结果
"""

import asyncio
import sys
import os
import signal
from typing import Optional

# 添加项目根目录到路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from api import TerminalAPIClient

class InteractiveTerminalDemo:
    """交互式终端演示"""
    
    def __init__(self):
        self.client: Optional[TerminalAPIClient] = None
        self.running = True
        self.current_output = ""
        
    async def setup_client(self):
        """设置客户端连接"""
        print("🔌 正在连接到 Terminal API...")
        
        self.client = TerminalAPIClient(
            host="localhost",
            port=7681,
            username="demo",
            password="password123",
            format_output=False  # 使用原始输出，便于流式显示
        )
        
        # 设置实时输出回调
        self.client.set_output_callback(self.on_output_received)
        
        success = await self.client.connect()
        if success:
            print("✅ 连接成功！")
            print("💡 提示：输入 'help' 查看帮助，输入 'quit' 或 'exit' 退出")
            return True
        else:
            print("❌ 连接失败，请检查 ttyd 服务是否启动")
            return False
    
    def on_output_received(self, output: str):
        """实时输出回调 - 流式显示"""
        if output and output.strip():
            # 清理输出，移除控制字符
            from api.utils.formatter import clean_terminal_text
            cleaned = clean_terminal_text(output)
            if cleaned and cleaned.strip():
                # 实时打印输出，不换行
                print(cleaned, end='', flush=True)
                self.current_output += cleaned
    
    def show_help(self):
        """显示帮助信息"""
        help_text = """
🖥️  Terminal API 交互式演示

📝 使用方法:
   - 直接输入任何 bash 命令，如: pwd, ls -la, echo hello
   - 输出将实时流式显示
   - 输入 'help' 显示此帮助
   - 输入 'quit' 或 'exit' 退出程序
   - 按 Ctrl+C 也可以退出

🌟 示例命令:
   pwd                    # 显示当前目录
   ls -la                 # 列出文件详情
   echo 'Hello World'     # 输出文本
   date                   # 显示当前时间
   whoami                 # 显示当前用户
   ps aux | head -5       # 显示进程列表
   df -h                  # 显示磁盘使用情况

⚠️  注意:
   - 避免运行交互式程序 (如 vim, nano, top)
   - 长时间运行的命令可能需要等待
        """
        print(help_text)
    
    def setup_signal_handler(self):
        """设置信号处理器"""
        def signal_handler(signum, frame):
            print("\n\n👋 收到退出信号，正在清理...")
            self.running = False
        
        signal.signal(signal.SIGINT, signal_handler)
        signal.signal(signal.SIGTERM, signal_handler)
    
    async def execute_command_with_stream(self, command: str):
        """执行命令并显示流式输出"""
        if not self.client:
            print("❌ 客户端未连接")
            return
        
        # 清空当前输出缓冲
        self.current_output = ""
        
        print("📤 输出:")
        print("-" * 50)
        
        try:
            # 执行命令，输出会通过回调实时显示
            result = await self.client.execute_command(command, timeout=30.0)
            
            # 确保输出完整
            print()  # 换行
            print("-" * 50)
            
            if result.success:
                print(f"✅ 命令执行成功 (耗时: {result.execution_time:.3f}秒)")
            else:
                print(f"❌ 命令执行失败: {result.error}")
                if result.output:
                    print(f"输出: {result.output}")
            
        except Exception as e:
            print(f"\n❌ 执行出错: {e}")
        
        print()  # 额外换行，分隔下一个命令
    
    async def run_interactive_loop(self):
        """运行交互式循环"""
        print("\n🎯 进入交互模式...")
        print("=" * 60)
        
        while self.running:
            try:
                # 获取用户输入
                command = input("💻 输入 > ").strip()
                
                if not command:
                    continue
                
                # 处理特殊命令
                if command.lower() in ['quit', 'exit', 'q']:
                    break
                elif command.lower() in ['help', 'h', '?']:
                    self.show_help()
                    continue
                elif command.lower() == 'clear':
                    os.system('clear' if os.name == 'posix' else 'cls')
                    continue
                
                # 执行命令
                await self.execute_command_with_stream(command)
                
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
            print("🔌 断开连接...")
            await self.client.disconnect()
            print("✅ 连接已断开")
    
    async def run(self):
        """运行演示"""
        print("🖥️  Terminal API 交互式流式输出演示")
        print("=" * 60)
        
        # 设置信号处理
        self.setup_signal_handler()
        
        try:
            # 建立连接
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
    demo = InteractiveTerminalDemo()
    await demo.run()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n👋 程序被中断")
    except Exception as e:
        print(f"❌ 程序启动失败: {e}")
