#!/usr/bin/env python3
"""
Terminal API Demo - Gradio WebUI
基于Gradio UI的Q CLI聊天界面，支持原生异步和流式输出
"""

import sys
import os
import asyncio
import logging
from typing import List, AsyncGenerator, Optional
import gradio as gr
from gradio import ChatMessage

# 添加项目根目录到Python路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from api import TerminalAPIClient
from api.data_structures import TerminalType

# 设置日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class TerminalChatBot:
    """终端聊天机器人"""
    
    def __init__(self):
        self.client: Optional[TerminalAPIClient] = None
        self.is_initializing = False
    
    async def ensure_client_ready(self) -> bool:
        """确保客户端已准备就绪"""
        if self.client and self.client.is_connected:
            return True
        
        if self.is_initializing:
            # 等待初始化完成
            while self.is_initializing:
                await asyncio.sleep(0.1)
            return bool(self.client and self.client.is_connected)
        
        try:
            self.is_initializing = True
            logger.info("初始化Q CLI客户端...")
            
            self.client = TerminalAPIClient(
                host="localhost",
                port=7682,  # Q CLI ttyd 服务端口
                username="demo",
                password="password123",
                terminal_type=TerminalType.QCLI
            )
            
            await self.client.initialize()
            
            if self.client.is_connected:
                logger.info("✅ Q CLI客户端连接成功")
                return True
            else:
                logger.error("❌ Q CLI客户端连接失败")
                return False
                
        except Exception as e:
            logger.error(f"初始化客户端失败: {e}")
            return False
        finally:
            self.is_initializing = False
    
    
    async def chat_with_qcli(self, message: str, history: List[ChatMessage]) -> AsyncGenerator[List[ChatMessage], None]:
        """Q CLI聊天处理 - 使用原生异步生成器"""
        
        # 输入验证
        if not message or not message.strip():
            status_msg = ChatMessage(
                role="assistant",
                content="⚠️ 请输入有效的问题或命令。",
                metadata={"title": "输入错误"}
            )
            yield [status_msg]
            return
        
        command = message.strip()
        
        # 确保客户端连接
        if not await self.ensure_client_ready():
            status_msg = ChatMessage(
                role="assistant",
                content="❌ 无法连接到Q CLI服务。请确保ttyd服务正在运行：\n\n```bash\n./ttyd/ttyd-service.sh start qcli 7682\n```",
                metadata={"title": "连接失败"}
            )
            yield [status_msg]
            return
        
        # 显示初始状态
        status_msg = ChatMessage(
            role="assistant",
            metadata={"title": "🤔 思考中", "status": "pending"},
            content="Q Cli 正在处理您的请求..."
        )
        yield [status_msg]
        
        try:
            # 使用异步流式处理
            response_content = ""
            content_length = 0
            content_msg = ChatMessage(
                role="assistant",
                content= ""
            )
            
            # 确保客户端不为None
            if not self.client:
                return

            async for chunk in self.client.execute_command_stream(command, silence_timeout=120.0):
                chunk_type = chunk.get("type")
                content = chunk.get("content", "")
                metadata = chunk.get("metadata", {})
                
                if chunk_type == "thinking":
                    # 更新思考状态
                    status_msg.content = "Q CLI正在思考您的问题..."
                    yield [status_msg, content_msg]
                
                elif chunk_type == "tool_use":
                    # 显示工具使用
                    tool_name = metadata.get("tool_name", "unknown")
                    status_msg.content = f"🛠️ 正在使用工具: {tool_name}"
                    yield [status_msg, content_msg]
                
                elif chunk_type == "content":
                    # 累积内容并实时显示
                    if content:
                        response_content += content
                        content_length += metadata.get("content_length")
                        content_msg.content = response_content

                        # 更新状态消息
                        status_msg.metadata = {"title": "💬 回复中", "status": "pending"}
                        status_msg.content = f"回复消息长度：{content_length}"
                        
                        # 实时流式输出
                        yield [status_msg, content_msg]
                
                elif chunk_type == "complete":
                    # 命令完成
                    execution_time = metadata.get("execution_time", 0)

                    # 更新状态消息
                    status_msg.metadata = {"title": "✅ 回复完成", "status": "done"}
                    status_msg.content = f"Q Cli 回复耗时: {execution_time:.2f}s"

                    if content_msg is None:
                        content_msg.content="<无输出内容>"
                    
                    yield [status_msg, content_msg]
                    break
                
                elif chunk_type == "error":
                    # 错误处理
                    error_message = metadata.get("error_message", "未知错误")
                    status_msg = ChatMessage(
                        role="assistant",
                        content=f"❌ 执行出错：\n\n```\n{error_message}\n```",
                        metadata={"title": "执行错误"}
                    )
                    yield history + [status_msg]
                    break
        
        except Exception as e:
            logger.error(f"聊天处理失败: {e}")
            status_msg = ChatMessage(
                role="assistant",
                content=f"🚨 处理过程中遇到系统错误：\n\n```\n{str(e)}\n```\n\n请重试或检查系统状态。",
                metadata={"title": "系统错误"}
            )
            yield history + [status_msg]
    
    async def get_connection_status(self) -> str:
        """获取连接状态"""
        if not self.client:
            return "🔴 **未连接** - 客户端未初始化"
        
        if self.client.is_connected:
            return "🟢 **已连接** - Q CLI ttyd 服务 (localhost:7682)"
        else:
            return "🔴 **未连接** - 请检查Q CLI ttyd服务是否启动"
    
    async def connect_to_qcli(self) -> str:
        """手动连接到Q CLI"""
        try:
            if await self.ensure_client_ready():
                return "🟢 **连接成功** - Q CLI服务已就绪"
            else:
                return "🔴 **连接失败** - 请检查Q CLI ttyd服务是否启动"
        except Exception as e:
            return f"🔴 **连接错误** - {str(e)}"
    
    async def disconnect_from_qcli(self) -> str:
        """断开Q CLI连接"""
        try:
            if self.client:
                await self.client.shutdown()
                self.client = None
            return "🔴 **已断开连接**"
        except Exception as e:
            return f"🔴 **断开连接时出错** - {str(e)}"
    
    async def cleanup(self):
        """清理资源"""
        if self.client:
            try:
                await self.client.shutdown()
            except Exception as e:
                logger.error(f"清理客户端时出错: {e}")
            finally:
                self.client = None


def create_webui_demo():
    """创建Gradio Demo UI"""
    
    # 初始化聊天机器人
    qbot = TerminalChatBot()
    
    # CSS样式
    css = """
    footer {visibility: hidden}
    .chat-message {
        font-family: 'SF Pro Display', -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
    }
    .connection-status {
        padding: 6px;
        border-radius: 8px;
        margin: 2px 0;
    }
    """
    
    with gr.Blocks(
        title="Q CLI Chat Interface", 
        css=css,
        theme='soft'
    ) as demo:
        
        # 标题和描述
        gr.Markdown("""
        # 🤖 Q CLI Chat Interface
        **与Amazon Q CLI进行实时聊天交互，获得AWS专业建议和技术支持**
        """)

        qchabot = gr.Chatbot(
            min_height=600,
            render=False
        )
        
        with gr.Row():
            with gr.Column(scale=6):
                # 主聊天界面 
                chat_interface = gr.ChatInterface(
                    fn=qbot.chat_with_qcli,
                    type="messages",
                    examples=[
                        "Hello! What can you help me with?",
                        "What is AWS Lambda and how does it work?",
                        "How do I create an S3 bucket using AWS CLI?",
                        "What are AWS best practices for security?",
                        "How to set up a VPC with public and private subnets?",
                        "What is CloudFormation and how to use it?",
                        "How to configure AWS CLI credentials?"
                    ],
                    example_labels=[
                        "👋 问候",
                        "🔧 Lambda服务",
                        "📦 S3存储",
                        "🔒 安全最佳实践",
                        "🌐 网络配置",
                        "📋 基础设施即代码",
                        "⚙️ CLI配置"
                    ],
                    title="💬 与Q CLI对话",
                    description="输入您的AWS相关问题，Q CLI将为您提供专业的建议和解决方案",
                    chatbot=qchabot,
                    submit_btn="发送",
                    stop_btn="停止",
                    autofocus=True,
                    autoscroll=True,
                    show_progress="minimal"
                )
            
            with gr.Column(scale=2):
                # 连接状态面板
                with gr.Group():
                    gr.Markdown("### 🔌 连接状态")
                    
                    connection_status = gr.Markdown(
                        value="🔴 **未连接** - 点击连接按钮开始",
                        elem_classes=["connection-status"]
                    )
                    
                    with gr.Row():
                        connect_btn = gr.Button("🔗 连接", variant="primary", size="sm")
                        disconnect_btn = gr.Button("🔌 断开", variant="secondary", size="sm")
                        refresh_btn = gr.Button("🔄 刷新", variant="secondary", size="sm")

                gr.Markdown("""
                ### 💡 使用指南
                
                **🚀 快速开始**
                1. 点击"🔗 连接"按钮
                2. 等待连接状态变为绿色
                3. 开始提问AWS相关问题
                
                **💬 交互方式**
                - **直接提问**: "什么是Lambda？"
                - **技术咨询**: "如何创建S3存储桶？"
                - **最佳实践**: "AWS安全建议"
                - **故障排除**: "EC2实例无法启动"
                
                **🎯 功能特性**
                - 🔄 **实时流式回复**
                - 🤔 **思考过程可视化**
                - 🛠️ **工具使用提示**
                - ⚡ **异步处理**
                """)
        
        # 连接按钮事件处理
        connect_btn.click(
            fn=qbot.connect_to_qcli,
            outputs=[connection_status]
        )
        
        disconnect_btn.click(
            fn=qbot.disconnect_from_qcli,
            outputs=[connection_status]
        )
        
        refresh_btn.click(
            fn=qbot.get_connection_status,
            outputs=[connection_status]
        )
        
        # 页面加载时初始化状态
        demo.load(
            fn=qbot.get_connection_status,
            outputs=[connection_status]
        )
    
    return demo, qbot


def main():
    """主函数"""
    print("🚀 启动Q CLI Chat界面...")
    
    # 初始化变量
    qbot = None
    
    try:
        # 创建Demo
        demo, qbot = create_webui_demo()
        
        # 启动服务
        demo.launch(
            server_name="0.0.0.0",
            server_port=8080,
            share=False,
            debug=False,
            show_error=True,
            show_api=False,
            favicon_path=None,
            app_kwargs={
                "docs_url": None,
                "redoc_url": None,
            }
        )
    except KeyboardInterrupt:
        print("\n👋 用户中断，正在关闭...")
    except Exception as e:
        print(f"❌ 启动失败: {e}")
        import traceback
        traceback.print_exc()
    finally:
        print("🔌 清理资源...")
        try:
            # 确保qbot已初始化
            if qbot:
                import asyncio
                asyncio.run(qbot.cleanup())
        except Exception as e:
            print(f"清理时出错: {e}")


if __name__ == "__main__":
    main()
