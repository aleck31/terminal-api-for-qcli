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
from api.command_executor import TerminalType

class InteractiveTerminalDemo:
    """交互式终端演示"""
    
    def __init__(self):
        self.client: Optional[TerminalAPIClient] = None
        self.running = True
        
    async def setup_client(self):
        """设置客户端连接"""
        print("🔌 正在连接到 Terminal API...")
        
        self.client = TerminalAPIClient(
            host="localhost",
            port=7681,
            username="demo",
            password="password123",
            format_output=True  # 启用格式化输出
        )
        
        success = await self.client.connect()
        if success:
            print("✅ 连接成功！")
            print("💡 提示：输入 'help' 查看帮助，输入 'quit' 或 'exit' 退出")
            return True
        else:
            print("❌ 连接失败，请检查 ttyd 服务是否启动")
            return False
    
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
        
        print("📤 输出:")
        print("-" * 50)
        
        try:
            start_time = asyncio.get_event_loop().time()
            success = False
            error_msg = None
            
            # 使用新的流式接口
            async for chunk in self.client.execute_command_stream(command, timeout=30.0):
                # 显示有效内容
                if chunk.get("content") and chunk.get("content").strip():
                    print(chunk["content"], end='', flush=True)
                
                # 检查完成状态
                if chunk.get("state") == "complete":
                    success = chunk.get("command_success", False)
                    error_msg = chunk.get("error")
                    execution_time = chunk.get("execution_time", 0)
                    break
                elif chunk.get("state") == "error":
                    success = False
                    error_msg = chunk.get("error", "未知错误")
                    execution_time = asyncio.get_event_loop().time() - start_time
                    break
            
            # 确保输出完整
            print()  # 换行
            print("-" * 50)
            
            if success:
                print(f"✅ 命令执行成功 (耗时: {execution_time:.3f}秒)")
            else:
                print(f"❌ 命令执行失败: {error_msg or '未知错误'}")
            
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
