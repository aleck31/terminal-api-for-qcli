# Terminal API for Q CLI

基于 TTYD 的 Web 终端 API，支持与 Amazon Q CLI 进行流式交互。

## 🎯 项目概述

这是一个基于 TTYD 实现的 Web 终端 API 演示项目，支持通过 Web 界面访问 Linux 终端，并可以运行各种交互式命令行程序如: Bash、Q CLI、Python 等。

## 📋 主要特性

- ✅ **流式输出**: 实时显示 Q CLI 思考和回复过程
- ✅ **状态检测**: 自动识别思考、回复、完成状态
- ✅ **Web 界面**: 现代化聊天界面，支持 Markdown 输出
- ✅ **API 接口**: 支持编程方式集成

## 📁 项目结构

```
terminal-api-for-qcli/
├── api/                    # API组件
│   ├── terminal_api_client.py   # 主要API接口
│   ├── websocket_client.py      # WebSocket客户端
│   └── utils/                   # 工具组件
├── ttyd/                   # TTYD服务管理
│   ├── ttyd-service.sh     # 服务管理脚本
│   ├── conf.ini           # 配置文件
│   └── pids/               # PID文件目录
├── webui/                  # Web UI
│   └── gradio_chat.py      # Gradio ChatInterface WebUI
├── start-webui.sh          # Gradio WebUI 启动脚本
├── interactive_demo.py     # 命令行演示
├── run_tests.py            # 测试运行器
├── tests/                  # 测试套件
└── README.md
```

### 核心组件

#### **接口层**
- **`TerminalAPIClient`** - 主要API接口，负责组件协调和状态管理

#### **组件层**  
- **`CommandExecutor`** - 命令执行器，专注命令生命周期管理（发送、检测完成、收集原始结果）
- **`OutputProcessor`** - 输出处理器，专注数据转换（清理控制序列、移除回显）
- **`ConnectionManager`** - 连接管理器，管理WebSocket连接生命周期

#### **通信层**
- **`WebSocketClient`** - WebSocket通信工具，处理底层协议
- **`QCLIStateDetector`** - Q CLI状态检测器（可选）


## 🚀 快速开始

### 1. 启动服务

```bash
# 启动 Q CLI 服务
./ttyd/ttyd-service.sh start qcli 7682

# 启动 Web UI
./start-webui.sh
```

### 2. 访问界面

- **Web UI**: http://localhost:7860 (Chatbot)
- **原生终端**: http://localhost:7682
- **交互演示**: `uv run python interactive_demo.py`

默认认证: `demo` / `password123`

## 🔧 API 使用

```python
import asyncio
from api import TerminalAPIClient
from api.command_executor import TerminalType

async def chat_with_qcli():
    async with TerminalAPIClient(
        host="localhost", 
        port=7682,
        terminal_type=TerminalType.QCLI
    ) as client:
        
        # 流式接口
        async for chunk in client.execute_command_stream("What is Lambda?"):
            if chunk.get("is_content"):
                print(chunk["content"], end="")
            elif chunk.get("state") == "complete":
                break

asyncio.run(chat_with_qcli())
```

## 🛠️ 服务管理

```bash
# 服务控制
./ttyd/ttyd-service.sh start qcli 7682    # 启动 Q CLI
./ttyd/ttyd-service.sh status             # 查看状态
./ttyd/ttyd-service.sh stop-all           # 停止所有服务

# 测试
uv run python -m pytest tests/ -v
```

## 📝 许可证

MIT License

---

**注意**: 本项目专注于演示TTYD的Web终端API功能，适合学习和原型开发。生产环境使用请注意安全配置。
