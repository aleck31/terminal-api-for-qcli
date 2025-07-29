#!/usr/bin/env python3
"""
Terminal API Demo - Gradio ChatInterface WebUI
"""

import sys
import os
import time
import logging
from typing import Generator, List, Dict, Any
import gradio as gr
from gradio import ChatMessage

# 添加项目根目录到Python路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from api.terminal_client import TerminalAPIClient

class TerminalChatBot:
    """终端聊天机器人"""
    
    def __init__(self):
        self.api_client = TerminalAPIClient()
        self.current_directory = "/tmp/terminalbot"
        self.terminal_context = {
            "working_directory": self.current_directory,
            "last_command": None,
            "command_history": []
        }
    
    def get_help_message(self) -> str:
        """获取帮助信息"""
        return """🖥️ **Terminal API Chat 使用指南**

**交互方式说明：**
- 聊天交互：直接输入问题，如 "帮我写一个Python脚本"
- 命令翻译：输入自然语言描述，如 "列出当前目录的所有文件"
- 系统诊断：输入 "/clear" 清空对话历史
- 帮助信息：输入 "/help" 查看Q CLI帮助

**输出显示说明：**
- 📤 **标准输出**: 命令的正常输出结果（普通消息）
- ⚠️ **错误输出**: 命令的错误信息（可折叠显示）
- ✅/❌ **执行完成**: 命令执行统计信息（可折叠显示）

**安全特性：**
- 危险命令自动拦截
- 实时流式输出
- 命令历史记录
- WebSocket连接支持

输入 `help` 或 `帮助` 查看此信息。
"""
    
    def format_summary(self, summary: dict) -> str:
        """格式化执行摘要"""
        return self.api_client.message_processor.format_summary(summary)
    
    def chat_function(self, message: str, history: List[ChatMessage]) -> Generator[List[ChatMessage], None, None]:
        """主要的聊天函数，返回ChatMessage列表"""
        
        # 检查帮助请求
        if message.lower().strip() in ['help', '帮助', 'h', '?']:
            current_history = history + [
                ChatMessage(role="assistant", content=self.get_help_message())
            ]
            yield current_history
            return
        
        # 执行命令
        command = message.strip()
        self.terminal_context["last_command"] = command
        self.terminal_context["command_history"].append(command)
        
        # 使用现有的历史记录（Gradio会自动添加用户消息）
        current_history = history.copy()
        
        # 收集输出
        stdout_content = []
        
        try:
            for output_type, content_line, metadata in self.api_client.execute_command(command):
                if output_type == "status":
                    # 初始状态消息
                    status_msg = ChatMessage(
                        role="assistant", 
                        content=content_line,
                        metadata=metadata
                    )
                    current_history.append(status_msg)
                    yield current_history
                    
                elif output_type == "stdout":
                    # 标准输出 - 累积显示
                    stdout_content.append(content_line)
                    
                    # 更新最后一条消息为累积的输出
                    stdout_text = "\n".join(stdout_content)
                    if len(current_history) > 1 and current_history[-1].role == "assistant":
                        current_history[-1] = ChatMessage(
                            role="assistant",
                            content=f"```\n{stdout_text}\n```"
                        )
                    else:
                        current_history.append(ChatMessage(
                            role="assistant",
                            content=f"```\n{stdout_text}\n```"
                        ))
                    yield current_history
                    
                elif output_type == "stderr":
                    # 错误输出
                    stderr_msg = ChatMessage(
                        role="assistant",
                        content=content_line,
                        metadata=metadata
                    )
                    current_history.append(stderr_msg)
                    yield current_history
                    
                elif output_type == "summary":
                    # 执行摘要 - 带title的metadata，显示为可折叠
                    summary_text = self.format_summary(content_line)
                    
                    summary_msg = ChatMessage(
                        role="assistant",
                        content=summary_text,
                        metadata=metadata
                    )
                    current_history.append(summary_msg)
                    yield current_history
                    
                elif output_type == "error":
                    # 错误消息 - 带title的metadata
                    error_msg = ChatMessage(
                        role="assistant",
                        content=content_line,
                        metadata=metadata
                    )
                    current_history.append(error_msg)
                    yield current_history
                
                time.sleep(0.01)  # 控制流式输出速度
                
        except Exception as e:
            error_msg = ChatMessage(
                role="assistant",
                content=f"命令执行失败: {str(e)}",
                metadata={"title": "❌ 执行异常"}
            )
            current_history.append(error_msg)
            yield current_history

def create_terminal_chat_interface():
    """创建Terminal聊天界面"""
    
    # 创建聊天机器人实例
    bot = TerminalChatBot()
    
    # 自定义CSS样式
    custom_css = """
    .gradio-container {
        max-width: 1200px !important;
    }
    .chat-message {
        font-family: 'Monaco', 'Menlo', 'Ubuntu Mono', monospace;
    }
    """
    
    # 创建ChatInterface
    demo = gr.ChatInterface(
        fn=bot.chat_function,
        type="messages",
        title="🖥️ Terminal API Chat",
        description="通过聊天界面跟Q CLI进行交互，支持实时流式输出和智能消息分类",
        examples=[
            "help",
            "q --help",
            "帮我写一个Python脚本来计算斐波那契数列",
            "列出当前目录的所有文件",
            "q doctor"
        ],
        cache_examples=False,
        css=custom_css,
        theme=gr.themes.Soft(
            primary_hue="blue",
            secondary_hue="gray",
            neutral_hue="slate"
        ),
        chatbot=gr.Chatbot(
            height=600,
            placeholder="🤖 Terminal API助手已就绪！\n\n输入 'help' 查看使用说明，或直接与Q CLI交互",
            show_copy_button=True,
            type="messages"
        ),
        textbox=gr.Textbox(
            placeholder="输入Q CLI命令或问题... (例如: 帮我写一个Python脚本)",
            container=False,
            scale=7
        )
    )
    
    return demo

def main():
    """主函数"""
    print("🚀 启动Terminal API Gradio Chat界面...")
    
    # 创建界面
    demo = create_terminal_chat_interface()
    
    # 启动应用
    demo.launch(
        server_name="0.0.0.0",
        server_port=7860,  # 使用标准端口
        share=False,
        debug=True,
        show_error=True,
        quiet=False
    )

if __name__ == "__main__":
    main()