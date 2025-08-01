#!/usr/bin/env python3
"""
Terminal API Demo - Gradio ChatInterface WebUI
基于 TTYD 的终端聊天界面，支持流式输出和状态管理
"""

import sys
import os
import time
import asyncio
import logging
import threading
import queue
from typing import Generator, List, Dict, Any, Optional
import gradio as gr
from gradio import ChatMessage

# 添加项目根目录到Python路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from api import TerminalAPIClient

# 设置日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class TerminalChatBot:
    """终端聊天机器人"""
    
    def __init__(self):
        self.user_clients = {}  # 存储每个用户的客户端实例
        self.user_loops = {}    # 存储每个用户的事件循环
        self.terminal_context = {
            "working_directory": "/tmp/terminalbot",
            "last_command": None,
            "command_history": []
        }
    
    def get_or_create_client_for_session(self, session_id: str) -> TerminalAPIClient:
        """为指定会话获取或创建客户端"""
        if session_id not in self.user_clients:
            logger.info(f"为会话创建新的终端客户端: {session_id}")
            
            # 创建新的客户端实例
            client = TerminalAPIClient(
                host="localhost",
                port=7681,
                username="demo",
                password="password123",
                format_output=True
            )
            
            self.user_clients[session_id] = client
            logger.info(f"终端客户端创建成功: {session_id}")
        
        return self.user_clients[session_id]
    
    def get_or_create_loop_for_session(self, session_id: str):
        """为指定会话获取或创建事件循环"""
        if session_id not in self.user_loops:
            # 为每个会话创建独立的事件循环
            loop = asyncio.new_event_loop()
            self.user_loops[session_id] = loop
            logger.info(f"为会话创建新的事件循环: {session_id}")
        
        return self.user_loops[session_id]
    
    def get_help_message(self) -> str:
        """获取帮助信息"""
        return """🖥️ **Terminal API Chat 使用指南**

**交互方式说明：**
- 直接命令：输入终端命令，如 "ls -la", "pwd", "echo hello"
- 自然语言：描述你想做的事，如 "列出当前目录的所有文件"
- 系统命令：输入 "help" 查看此帮助信息

**输出显示说明：**
- 📤 **标准输出**: 命令的正常输出结果
- ⚠️ **错误输出**: 命令的错误信息
- ✅/❌ **执行状态**: 命令执行结果统计

**安全特性：**
- 实时命令执行
- Markdown格式化输出
- 连接状态监控
- 错误处理和重连

输入 `help` 或 `帮助` 查看此信息。
"""
    
    def get_connection_status(self, session_id: str) -> str:
        """获取连接状态信息"""
        if session_id not in self.user_clients:
            return "**🔌 连接状态**: 未初始化"
        
        client = self.user_clients[session_id]
        if client.is_connected:
            return f"**🔌 连接状态**: ✅ 已连接到 ttyd 服务 (localhost:7681)"
        else:
            return f"**🔌 连接状态**: ❌ 未连接 - 请检查 ttyd 服务是否启动"
    
    def cleanup_session(self, session_id: str):
        """清理会话资源"""
        if session_id in self.user_clients:
            client = self.user_clients[session_id]
            try:
                # 使用会话专用的事件循环
                if session_id in self.user_loops:
                    loop = self.user_loops[session_id]
                    if not loop.is_closed():
                        loop.run_until_complete(client.disconnect())
                        loop.close()
                    del self.user_loops[session_id]
                logger.info(f"会话 {session_id} 连接已断开")
            except Exception as e:
                logger.error(f"断开会话 {session_id} 连接时出错: {e}")
            finally:
                del self.user_clients[session_id]
    
    def chat_with_terminal(self, message: str, history: List[Dict], request: gr.Request) -> Generator[tuple, None, None]:
        """与终端聊天 - 支持流式输出，返回 (聊天消息, 连接状态)"""
        
        # 使用 Gradio 的 session_hash 作为 session ID
        session_id = (request.session_hash if request else None) or f"sid-{int(time.time())}"
        
        # 检查帮助请求
        if message.lower().strip() in ['help', '帮助', 'h', '?']:
            help_msg = ChatMessage(role="assistant", content=self.get_help_message())
            yield ([help_msg], self.get_connection_status(session_id))
            return
        
        # 为这个会话获取或创建客户端
        client = self.get_or_create_client_for_session(session_id)
        
        # 输入验证
        if not message or not message.strip():
            error_msg = ChatMessage(
                role="assistant",
                content="请输入有效的命令。",
                metadata={"title": "⚠️ 输入错误"}
            )
            yield ([error_msg], self.get_connection_status(session_id))
            return
        
        command = message.strip()
        self.terminal_context["last_command"] = command
        self.terminal_context["command_history"].append(command)
        
        # 显示初始状态
        stat_msg = ChatMessage(
            role="assistant",
            content=f"正在执行命令: `{command}`",
            metadata={
                "title": "🔄 执行状态",
                "status": "pending"
            }
        )
        yield ([stat_msg], self.get_connection_status(session_id))
        
        try:
            # 使用线程来运行异步代码，实现真正的流式输出
            start_time = time.time()
            
            # 创建队列来传递流式数据
            stream_queue = queue.Queue()
            exception_container: List[Optional[Exception]] = [None]
            
            def async_terminal_worker():
                """在独立线程中运行异步终端处理"""
                try:
                    # 为每个会话使用独立的事件循环
                    loop = self.get_or_create_loop_for_session(session_id)
                    asyncio.set_event_loop(loop)
                    
                    async def terminal_handler():
                        try:
                            # 确保连接
                            if not client.is_connected:
                                await client.connect()
                            
                            if not client.is_connected:
                                stream_queue.put({"error": "❌ 无法连接到 ttyd 服务，请检查服务是否启动"})
                                return
                            
                            # 执行命令
                            result = await client.execute_command(command)
                            
                            # 发送结果
                            stream_queue.put({
                                "result": result,
                                "success": result.success,
                                "execution_time": result.execution_time
                            })
                            
                        except Exception as e:
                            logger.error(f"终端处理失败: {e}")
                            error_msg = f"执行命令时遇到错误：\n\n```\n{str(e)}\n```\n\n请检查命令格式或网络连接。"
                            stream_queue.put({"error": error_msg})
                        
                        finally:
                            # 发送结束信号
                            stream_queue.put(None)
                    
                    # 运行异步处理
                    loop.run_until_complete(terminal_handler())
                
                except Exception as e:
                    exception_container[0] = e
                    stream_queue.put(None)
            
            # 启动异步处理线程
            thread = threading.Thread(target=async_terminal_worker)
            thread.daemon = True
            thread.start()
            
            # 实时从队列中获取并输出数据
            while True:
                try:
                    # 等待数据，设置超时避免无限等待
                    data = stream_queue.get(timeout=60)
                    
                    if data is None:
                        # 收到结束信号
                        break
                    
                    # 处理错误
                    if "error" in data:
                        stat_msg.content = f"命令执行失败: `{command}`"
                        stat_msg.metadata = {"title": "❌ 执行失败", "status": "done"}
                        
                        error_msg = ChatMessage(
                            role="assistant",
                            content=data["error"],
                            metadata={"title": "🚨 错误详情"}
                        )
                        yield ([stat_msg, error_msg], self.get_connection_status(session_id))
                        break
                    
                    # 处理成功结果
                    if "result" in data:
                        result = data["result"]
                        duration = data["execution_time"]
                        
                        if data["success"]:
                            # 更新状态消息
                            stat_msg.content = f"命令执行完成: `{command}` (耗时: {duration:.2f}秒)"
                            stat_msg.metadata = {"title": "✅ 执行成功", "status": "done"}
                            
                            # 创建内容消息 - 只显示命令输出，不包含状态信息
                            if result.output and result.output.strip():
                                # 使用原始输出，不使用 markdown（避免重复格式化）
                                content_msg = ChatMessage(
                                    role="assistant",
                                    content=f"```bash\n{result.output.strip()}\n```"
                                )
                            else:
                                content_msg = ChatMessage(
                                    role="assistant",
                                    content="命令执行完成，无输出内容"
                                )
                            
                            yield ([stat_msg, content_msg], self.get_connection_status(session_id))
                        else:
                            stat_msg.content = f"命令执行失败: `{command}`"
                            stat_msg.metadata = {"title": "❌ 执行失败", "status": "done"}
                            
                            error_content = f"**错误信息:** {result.error}\n\n**执行时间:** {duration:.2f}秒"
                            if result.output:
                                error_content += f"\n\n**输出内容:**\n```\n{result.output}\n```"
                            
                            error_msg = ChatMessage(
                                role="assistant",
                                content=error_content
                            )
                            yield ([stat_msg, error_msg], self.get_connection_status(session_id))
                        break
                
                except queue.Empty:
                    # 超时处理
                    if exception_container[0]:
                        error_msg = ChatMessage(
                            role="assistant",
                            content=f"处理异常: {exception_container[0]}",
                            metadata={"title": "🚨 异常详情"}
                        )
                        yield ([error_msg], self.get_connection_status(session_id))
                    else:
                        timeout_msg = ChatMessage(
                            role="assistant",
                            content="命令执行超时，请重试",
                            metadata={"title": "⏰ 超时"}
                        )
                        yield ([timeout_msg], self.get_connection_status(session_id))
                    break
            
            # 等待线程结束
            thread.join(timeout=10)
        
        except Exception as e:
            logger.error(f"聊天处理失败: {e}")
            # 显示错误信息
            error_msg = ChatMessage(
                role="assistant",
                content=f"处理过程中遇到错误：\n\n```\n{str(e)}\n```\n\n请重试或检查系统状态。",
                metadata={"title": "🚨 系统错误"}
            )
            yield ([error_msg], self.get_connection_status(session_id))

def create_demo():
    """创建 Gradio Demo UI"""
    
    # 初始化聊天机器人
    bot = TerminalChatBot()
    
    # 自定义CSS样式
    css = """
    footer {visibility: hidden}
    .gradio-container {
        max-width: 1200px !important;
    }
    .chat-message {
        font-family: 'Monaco', 'Menlo', 'Ubuntu Mono', monospace;
    }
    """
    
    with gr.Blocks(title="Terminal API Chat", css=css) as demo:
        gr.Markdown("""
            # 🖥️ Terminal API Chat
            **通过聊天界面与终端进行交互，支持实时命令执行和Markdown格式化输出**
            """)
        
        with gr.Row():
            with gr.Column(scale=2):
                gr.Markdown("""
                    本演示支持：
                    - 🖥️ **终端命令执行** (bash, shell 命令)
                    - 📝 **清晰格式化输出** (代码块显示)
                    - 🔄 **实时流式输出** (即时反馈)
                    - 🔌 **连接状态监控** (自动重连)
                    """)
            
            with gr.Column(scale=1):
                connection_status = gr.Markdown(
                    label="🔌 连接状态",
                    show_label=True,
                    container=True,
                    value="**🔌 连接状态**: 未初始化",
                    render=False
                )
        
        with gr.Row():
            with gr.Column(scale=2):
                # 定义Chatbot组件
                chatbot = gr.Chatbot(
                    type='messages',
                    show_copy_button=True,
                    min_height='60vh',
                    max_height='80vh',
                    allow_tags=True,
                    render=False
                )
                
                textbox = gr.Textbox(
                    placeholder="输入终端命令... (例如: ls -la, pwd, echo hello)",
                    submit_btn=True,
                    stop_btn=True,
                    render=False
                )
                
                # 创建聊天界面
                chat_interface = gr.ChatInterface(
                    fn=bot.chat_with_terminal,
                    type="messages",
                    chatbot=chatbot,
                    textbox=textbox,
                    additional_outputs=[connection_status],
                    examples=[
                        "help",
                        "pwd",
                        "ls -la",
                        "echo 'Hello Terminal API'",
                        "whoami",
                        "date",
                        "ps aux | head -5",
                        "df -h"
                    ],
                    theme='soft'
                )
            
            with gr.Column(scale=1):
                connection_status.render()
        
        # 页面加载时初始化状态
        def initialize_status(request: gr.Request):
            session_id = (request.session_hash if request else None) or f"sid-{int(time.time())}"
            return bot.get_connection_status(session_id)
        
        demo.load(
            fn=initialize_status,
            outputs=[connection_status]
        )
    
    return demo

def main():
    """主函数"""
    print("🚀 启动 Terminal API Chat 界面...")
    
    try:
        # 创建并启动 Demo
        demo = create_demo()
        
        # 启动服务
        demo.launch(
            server_name="0.0.0.0",
            server_port=7860,
            share=False,
            debug=False,
            show_error=True,
            show_api=False,
        )
    except KeyboardInterrupt:
        print("\n👋 用户中断，正在关闭...")
    except Exception as e:
        print(f"❌ 启动失败: {e}")
    finally:
        print("🔌 清理资源...")

if __name__ == "__main__":
    main()
