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
from api.command_executor import TerminalType

# 设置日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class CompatResult:
    """兼容的结果对象"""
    def __init__(self, output, success, execution_time, error):
        self.output = output
        self.success = success
        self.execution_time = execution_time
        self.error = error

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
                port=7682,  # Q CLI ttyd 服务端口
                username="demo",
                password="password123",
                terminal_type=TerminalType.QCLI,  # 使用 Q CLI 类型
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

    
    def get_connection_status(self, session_id: str) -> str:
        """获取连接状态信息"""
        if session_id not in self.user_clients:
            return "**🔌 连接状态**: 未初始化"
        
        client = self.user_clients[session_id]
        if client.is_connected:
            return f"**🔌 连接状态**: ✅ 已连接到 Q CLI ttyd 服务 (localhost:7682)"
        else:
            return f"**🔌 连接状态**: ❌ 未连接 - 请检查 Q CLI ttyd 服务是否启动"
    
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
    
    def chat_with_qcli(self, message: str, history: List[Dict], request: gr.Request) -> Generator[tuple, None, None]:
        """与终端聊天 - 支持流式输出，返回 (聊天消息, 连接状态)"""
        
        # 使用 Gradio 的 session_hash 作为 session ID
        session_id = (request.session_hash if request else None) or f"sid-{int(time.time())}"
        
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
                "status": "pending"  # 只能是 'pending' 或 'done'
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
                                stream_queue.put({"error": "❌ 无法连接到 Q CLI ttyd 服务，请检查服务是否启动"})
                                return
                            
                            # 使用新的流式接口
                            final_success = False
                            final_execution_time = 0.0
                            final_error = None
                            
                            async for chunk in client.execute_command_stream(command, silence_timeout=120.0):
                                # 实时发送流式内容
                                if chunk.get("content") and chunk.get("is_content"):
                                    stream_queue.put({
                                        "stream_content": chunk["content"],
                                        "state": chunk.get("state", "responding")
                                    })
                                
                                # 发送状态更新
                                elif chunk.get("state") == "thinking":
                                    stream_queue.put({
                                        "status_update": "thinking",
                                        "state": "thinking"
                                    })
                                
                                # 检查完成状态
                                if chunk.get("state") == "complete":
                                    final_success = chunk.get("command_success", False)
                                    final_execution_time = chunk.get("execution_time", 0.0)
                                    final_error = chunk.get("error")
                                    break
                                elif chunk.get("state") == "error":
                                    final_success = False
                                    final_error = chunk.get("error", "未知错误")
                                    final_execution_time = chunk.get("execution_time", 0.0)
                                    break
                            
                            # 发送最终结果
                            stream_queue.put({
                                "result": CompatResult("", final_success, final_execution_time, final_error),
                                "success": final_success,
                                "execution_time": final_execution_time
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
            response_content = ""  # 累积响应内容用于显示
            content_msg = None     # 内容消息对象
            
            while True:
                try:
                    # 等待数据，设置超时避免无限等待
                    data = stream_queue.get(timeout=120)
                    
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
                    
                    # 处理流式内容
                    if "stream_content" in data:
                        content = data["stream_content"]
                        response_content += content
                        
                        # 创建或更新内容消息
                        if content_msg is None:
                            content_msg = ChatMessage(
                                role="assistant",
                                content=response_content,
                                metadata={"title": "💬 Q CLI 回复"}
                            )
                        else:
                            content_msg.content = response_content
                        
                        # 实时输出流式内容
                        yield ([stat_msg, content_msg], self.get_connection_status(session_id))
                    
                    # 处理状态更新
                    elif "status_update" in data:
                        if data["status_update"] == "thinking":
                            stat_msg.content = f"Q CLI 正在思考: `{command}`"
                            stat_msg.metadata = {"title": "🤔 思考中", "status": "pending"}  # 使用 pending
                            yield ([stat_msg], self.get_connection_status(session_id))
                    
                    # 处理最终结果
                    elif "result" in data:
                        result = data["result"]
                        duration = data["execution_time"]
                        
                        if data["success"]:
                            # 更新状态消息
                            stat_msg.content = f"命令执行完成: `{command}` (耗时: {duration:.2f}秒)"
                            stat_msg.metadata = {"title": "✅ 执行成功", "status": "done"}
                            
                            # 如果有内容消息，保持显示；否则显示无内容
                            if content_msg is None:
                                content_msg = ChatMessage(
                                    role="assistant",
                                    content="命令执行完成，无输出内容"
                                )
                            
                            yield ([stat_msg, content_msg], self.get_connection_status(session_id))
                        else:
                            stat_msg.content = f"命令执行失败: `{command}`"
                            stat_msg.metadata = {"title": "❌ 执行失败", "status": "done"}
                            
                            error_content = f"**错误信息:** {result.error}\n\n**执行时间:** {duration:.2f}秒"
                            
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
    
    with gr.Blocks(title="Q CLI Chat Interface", css=css) as demo:
        gr.Markdown("""
            # 🤖 Q CLI Chat Interface
            **通过聊天界面与 Amazon Q CLI 进行交互，获得 AWS 专业建议和技术支持**
            """)
        
        with gr.Row():
            with gr.Column(scale=4):
                # WebSocket 连接状态控制面板
                with gr.Group():
                    gr.Markdown("### 🔌 Q CLI 连接控制")

                    # 添加连接状态文本框
                    connection_status = gr.Textbox(
                        label="连接状态",
                        value="**🔌 连接状态**: 未初始化",
                        interactive=False,
                        max_lines=1
                    )
                    
                    with gr.Row():
                        connect_btn = gr.Button("🔗 连接", variant="primary", size="sm")
                        disconnect_btn = gr.Button("🔌 断开", variant="secondary", size="sm")
                        refresh_btn = gr.Button("🔄 刷新", variant="secondary", size="sm")
                    
                    status_message = gr.Textbox(
                        label="状态消息",
                        value="等待操作...",
                        interactive=False,
                        max_lines=2
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
                    placeholder="询问 AWS 相关问题... (例如: 什么是 Lambda? 如何创建 S3 存储桶?)",
                    submit_btn=True,
                    stop_btn=True,
                    render=False
                )
                
                # 创建聊天界面
                chat_interface = gr.ChatInterface(
                    fn=bot.chat_with_qcli,
                    type="messages",
                    chatbot=chatbot,
                    textbox=textbox,
                    additional_outputs=[connection_status],
                    examples=[
                        "Hello",
                        "What is AWS Lambda?",
                        "How to create an S3 bucket?",
                        "Explain EC2 instance types",
                        "What is CloudFormation?",
                        "AWS best practices",
                        "How to use AWS CLI?",
                        "What is VPC?"
                    ],
                    theme='soft'
                )
            
            with gr.Column(scale=1):
                gr.Markdown("""
                ### 💡 使用提示

                **交互方式：**
                - 直接提问：询问 AWS 相关问题，如 "什么是 Lambda？"
                - 技术咨询：请求帮助，如 "如何创建 S3 存储桶？"
                - 最佳实践：询问建议，如 "AWS 安全最佳实践"

                **输出显示：**
                - 🤔 **思考状态**: Q CLI 正在处理您的问题
                - 💬 **实时回复**: Q CLI 的流式回答
                - ✅/❌ **执行状态**: 问答完成状态

                **连接状态：**
                - 🟢 已连接 - 可以开始对话
                - 🔴 未连接 - 需要点击连接按钮
                
                **连接问题：**
                如果连接断开，请：
                1. 点击"刷新"查看状态
                2. 点击"连接"重新连接
                3. 检查 Q CLI ttyd 服务是否运行
                
                **示例问题：**
                - "什么是 AWS Lambda？"
                - "如何设置 VPC？"
                - "S3 的存储类别有哪些？"
                - "EC2 实例类型如何选择？"
                """)
        
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
