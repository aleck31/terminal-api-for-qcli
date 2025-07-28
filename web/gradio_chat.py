#!/usr/bin/env python3
"""
Terminal API Demo - Gradio ChatInterface WebUI
"""

import gradio as gr
from gradio import ChatMessage
import requests
import json
import time
import re
import subprocess
import threading
import queue
from typing import Generator, List, Dict, Any
from urllib.parse import urljoin
import base64

class TerminalAPIClient:
    """Terminal API客户端"""
    
    def __init__(self, base_url: str = "http://localhost:8080", username: str = "demo", password: str = "password123"):
        self.base_url = base_url
        self.username = username
        self.password = password
        self.session = requests.Session()
        
        # 设置基本认证
        credentials = base64.b64encode(f"{username}:{password}".encode()).decode()
        self.session.headers.update({
            'Authorization': f'Basic {credentials}',
            'User-Agent': 'Terminal-API-Gradio-Client/1.0'
        })
    
    def test_connection(self) -> bool:
        """测试API连接"""
        try:
            response = self.session.get(self.base_url, timeout=5)
            return response.status_code == 200
        except:
            return False
    
    def execute_command_local(self, command: str) -> Generator[tuple[str, str, dict], None, None]:
        """本地执行命令并流式返回结果，返回(output_type, content, metadata)元组"""
        try:
            # 安全检查 - 基本的命令过滤
            dangerous_commands = ['rm -rf', 'sudo rm', 'mkfs', 'dd if=', 'format', ':(){ :|:& };:']
            if any(dangerous in command.lower() for dangerous in dangerous_commands):
                yield ("error", "⚠️ 危险命令已被阻止执行", {"title": "🚫 安全拦截"})
                return
            
            start_time = time.time()
            
            # 执行命令，分别捕获stdout和stderr
            process = subprocess.Popen(
                command,
                shell=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                universal_newlines=True,
                bufsize=1
            )
            
            # 创建队列来收集输出
            output_queue = queue.Queue()
            
            def read_stdout():
                """读取标准输出"""
                try:
                    for line in iter(process.stdout.readline, ''):
                        if line:
                            output_queue.put(('stdout', line))
                    process.stdout.close()
                except:
                    pass
            
            def read_stderr():
                """读取错误输出"""
                try:
                    for line in iter(process.stderr.readline, ''):
                        if line:
                            output_queue.put(('stderr', line))
                    process.stderr.close()
                except:
                    pass
            
            # 启动读取线程
            stdout_thread = threading.Thread(target=read_stdout)
            stderr_thread = threading.Thread(target=read_stderr)
            
            stdout_thread.daemon = True
            stderr_thread.daemon = True
            
            stdout_thread.start()
            stderr_thread.start()
            
            # 收集输出
            stdout_data = ""
            stderr_data = ""
            
            while process.poll() is None or not output_queue.empty():
                try:
                    # 非阻塞获取输出
                    output_type, line = output_queue.get(timeout=0.1)
                    
                    if output_type == 'stdout':
                        stdout_data += line
                        yield ("stdout", line.rstrip(), {})
                    elif output_type == 'stderr':
                        stderr_data += line
                        yield ("stderr", line.rstrip(), {"title": "⚠️ 错误输出"})
                        
                except queue.Empty:
                    continue
                except:
                    break
            
            # 等待线程结束
            stdout_thread.join(timeout=1)
            stderr_thread.join(timeout=1)
            
            # 获取返回码并生成最终报告
            return_code = process.poll()
            end_time = time.time()
            duration = end_time - start_time
            
            # 生成执行摘要
            summary_data = {
                "command": command,
                "return_code": return_code,
                "status": "success" if return_code == 0 else "failed",
                "stdout_lines": len(stdout_data.strip().splitlines()) if stdout_data.strip() else 0,
                "stderr_lines": len(stderr_data.strip().splitlines()) if stderr_data.strip() else 0,
                "duration": duration
            }
            
            status_icon = "✅" if return_code == 0 else "❌"
            summary_title = f"{status_icon} 执行完成"
            
            yield ("summary", summary_data, {
                "title": summary_title,
                "duration": duration,
                "status": "done"
            })
                
        except Exception as e:
            yield ("error", f"执行错误: {str(e)}", {"title": "❌ 执行异常"})

class TerminalChatBot:
    """终端聊天机器人"""
    
    def __init__(self):
        self.api_client = TerminalAPIClient()
        self.current_directory = "/home/ubuntu/labzone/idears"
        self.terminal_context = {
            "working_directory": self.current_directory,
            "last_command": None,
            "command_history": []
        }
    
    def get_help_message(self) -> str:
        """获取帮助信息"""
        return """🖥️ **Terminal API Chat 使用指南**

**执行命令的方式：**
- 直接输入自然语言需求或常见命令

**输出显示说明：**
- 📤 **标准输出**: 命令的正常输出结果（普通消息）
- ⚠️ **错误输出**: 命令的错误信息（可折叠显示）
- ✅/❌ **执行完成**: 命令执行统计信息（可折叠显示）

**支持的命令类型：**
- 文件操作：`ls`, `cat`, `find`, `grep`
- 系统信息：`ps`, `top`, `df`, `free`, `uname`
- 网络工具：`ping`, `curl`, `wget`
- 开发工具：`git`, `python`, `node`

**安全特性：**
- 危险命令自动拦截
- 实时流式输出
- 命令历史记录

输入 `help` 或 `帮助` 查看此信息。
"""
    
    def format_summary(self, summary: dict) -> str:
        """格式化执行摘要"""
        status_icon = "✅" if summary["status"] == "success" else "❌"
        status_text = "成功" if summary["status"] == "success" else "失败"
        
        result = f"**命令执行摘要**\n\n"
        result += f"- 命令: `{summary['command']}`\n"
        result += f"- 返回码: {summary['return_code']}\n"
        result += f"- 状态: {status_icon} {status_text}\n"
        result += f"- 执行时间: {summary['duration']:.2f}秒\n"
        
        if summary["stdout_lines"] > 0:
            result += f"- 标准输出: {summary['stdout_lines']} 行\n"
        if summary["stderr_lines"] > 0:
            result += f"- 错误输出: {summary['stderr_lines']} 行\n"
        
        return result
    
    def chat_function(self, message: str, history: List[ChatMessage]) -> Generator[List[ChatMessage], None, None]:
        """主要的聊天函数，返回ChatMessage列表"""
        
        # 检查帮助请求
        if message.lower().strip() in ['help', '帮助', 'h', '?']:
            help_messages = [
                ChatMessage(role="user", content=message),
                ChatMessage(role="assistant", content=self.get_help_message())
            ]
            yield help_messages
            return
        
        # 执行命令
        command = content.strip()
        self.terminal_context["last_command"] = command
        self.terminal_context["command_history"].append(command)
        
        # 初始状态消息 - 使用pending状态显示加载动画
        status_msg = ChatMessage(
            role="assistant", 
            content=f"正在执行命令: `{command}`",
            metadata={
                "title": "🔄 执行中...", 
                "status": "pending"
            }
        )
        result_messages.append(status_msg)
        yield result_messages
        
        # 收集输出
        stdout_content = []
        stderr_messages = []
        
        try:
            for output_type, content_line, metadata in self.api_client.execute_command_local(command):
                if output_type == "stdout":
                    # 标准输出 - 普通ChatMessage（无metadata）
                    stdout_content.append(content_line)
                    
                    # 更新为普通输出消息
                    stdout_text = "\n".join(stdout_content)
                    current_history[-1] = ChatMessage(
                        role="assistant",
                        content=f"```bash\n$ {command}\n{stdout_text}\n```"
                    )
                    yield current_history
                    
                elif output_type == "stderr":
                    # 错误输出
                    stderr_msg = ChatMessage(
                        role="assistant",
                        content=content_line,
                        metadata=metadata
                    )
                    stderr_messages.append(stderr_msg)
                    
                    # 添加stderr消息到历史
                    if len(stderr_messages) == 1:
                        current_history.append(stderr_msg)
                    else:
                        current_history[-1] = stderr_msg
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
                    current_history[-1] = error_msg
                    yield current_history
                
                time.sleep(0.01)  # 控制流式输出速度
                
        except Exception as e:
            current_history[-1] = ChatMessage(
                role="assistant",
                content=f"命令执行失败: {str(e)}",
                metadata={"title": "❌ 执行异常"}
            )
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
        description="通过聊天界面跟Q Cli进行交互，支持实时流式输出和智能消息分类",
        examples=[
            "help",
            "查询当前磁盘使用率",
            "分析最近1小时的系统日志", 
            "检查API连接",
            "查询最新的AWS Region列表"
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
            placeholder="🤖 Terminal API助手已就绪！\n\n输入 'help' 查看使用说明，或直接执行命令如 '执行: ls -la'",
            show_copy_button=True,
            type="messages"
        ),
        textbox=gr.Textbox(
            placeholder="输入命令或消息... (例如: 查询系统日志)",
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
