# Terminal API for Q CLI

基于 TTYD 的 Web 终端 API，支持与 Amazon Q CLI 进行流式交互。

## 🎯 项目概述

这是一个基于 TTYD 实现的 Web 终端 API 演示项目，支持通过 Web 界面访问 Linux 终端，并可以运行各种交互式命令行程序如: Bash、Q CLI、Python 等。

## 📋 主要特性

- ✅ **事件驱动架构**: 组件间通过事件通信，松耦合设计
- ✅ **分层状态管理**: 协议、连接、业务三层状态管理，职责清晰
- ✅ **自动状态映射**: 连接状态变化自动映射为业务状态
- ✅ **流式输出**: 实时显示 Q CLI 思考和回复过程
- ✅ **Web 界面**: 现代化聊天界面，支持 Markdown 输出
- ✅ **API 接口**: 支持编程方式集成

## 📁 项目结构

```
terminal-api-for-qcli/
├── api/                    # API组件
│   ├── terminal_api_client.py   # 主要API接口
│   ├── websocket_client.py      # WebSocket客户端
│   ├── command_executor.py      # 命令执行器
│   ├── connection_manager.py    # 连接管理器
│   ├── output_processor.py      # 消息处理器
│   └── utils/                   # 工具组件
│       ├── qcli_formatter.py    # Q CLI 格式化工具
│       └── formatter.py         # 通用格式化工具
├── ttyd/                   # TTYD服务管理
│   ├── ttyd-service.sh     # 服务管理脚本
│   └── conf.ini           # 配置文件
├── tests/                  # 测试套件
├── webui/                  # Web UI
│   └── gradio_chat.py      # Gradio ChatInterface WebUI
├── start-webui.sh          # Gradio WebUI 启动脚本
├── interactive_demo.py     # 命令行演示
├── docs/                   # 文档目录
│   ├── connection_state_design.md      # 连接状态管理设计
│   └── terminal_api_client_redesign.md # 业务层重构设计
└── README.md
```

### 核心组件架构

#### 设计原则
- **分层清晰**: 协议层、连接层、业务层职责明确
- **松耦合**: 组件间通过事件和回调通信
- **状态一致**: 多层状态通过映射机制保持一致
- **无状态工具**: CommandExecutor 设计为无状态工具
- **事件驱动**: 消息处理采用监听器模式

#### **🏗️ 分层架构**
```
┌──────────────────────────────────────────────────────────────┐
│                TerminalAPIClient                             │
│                (Business Layer)                              │
│  Responsibilities:                                           │
│  • Business process coordination                             │
│  • User interface provision                                  │
│  • Component lifecycle management                            │
│  • Business state management (IDLE, BUSY, ERROR, etc.)       │
│  • Connection state mapping                                  │
├──────────────────────────────────────────────────────────────┤
│  ConnectionManager │  CommandExecutor   │  OutputProcessor   │
│  (Connection Mgmt) │  (Command Exec)    │  (Output Process)  │
│  Responsibilities: │  Responsibilities: │  Responsibilities: │
│  • Connection      │  • Stateless cmd   │  • Data cleaning   │
│    lifecycle       │    execution       │    & conversion    │
│  • Reconnection    │  • Completion      │  • Message type    │
│    strategy        │    detection       │    identification  │
│  • Connection      │  • Stream output   │  • Format output   │
│    state mgmt      │    processing      │                    │
│  • Event-driven    │                    │                    │
│    msg dispatch    │                    │                    │
├──────────────────────────────────────────────────────────────┤
│                 TtydWebSocketClient                          │
│                (Protocol Layer)                              │
│  Responsibilities:                                           │
│  • WebSocket connection establish/disconnect                 │
│  • ttyd message format processing                            │
│  • Authentication handling                                   │
│  • Protocol state management (CONNECTING, AUTH, READY)       │
└──────────────────────────────────────────────────────────────┘
```

#### **🔧 组件职责**
- **`TerminalAPIClient`** - 业务协调层，负责组件协调、业务状态管理和连接状态映射
- **`CommandExecutor`** - 无状态命令执行工具，专注命令执行逻辑，不维护状态
- **`OutputProcessor`** - 输出处理器，专注数据转换和消息类型识别
- **`ConnectionManager`** - 连接管理器，管理连接生命周期和事件驱动消息分发
- **`TtydWebSocketClient`** - 协议实现层，处理 ttyd 协议和协议状态管理

#### **🔄 状态管理设计**
- **协议状态** (TtydWebSocketClient): `DISCONNECTED` → `CONNECTING` → `AUTHENTICATING` → `PROTOCOL_READY`
- **连接状态** (ConnectionManager): `IDLE` → `CONNECTING` → `CONNECTED` → `DISCONNECTED`
- **业务状态** (TerminalAPIClient): `INITIALIZING` → `IDLE` → `BUSY` → `IDLE` (循环)
- **状态映射**: 连接状态变化自动映射为业务状态，确保状态一致性

## 🚀 快速开始

### 1. 启动服务

```bash
# 启动通用终端服务 (端口 7681)
./ttyd/ttyd-service.sh start

# 启动 Q CLI 服务 (端口 7682)
./ttyd/ttyd-service.sh start qcli 7682

# 启动 Web UI
./start-webui.sh
```

### 2. 访问界面

- **Web UI**: http://localhost:7860 (Chatbot)
- **通用终端**: http://localhost:7681
- **Q CLI 终端**: http://localhost:7682
- **交互演示**: `uv run python interactive_demo.py`

默认认证: `demo` / `password123`

## 🔧 API 使用

### 基础用法

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

### 高级用法 - 状态感知

```python
async def advanced_qcli_chat():
    async with TerminalAPIClient(
        host="localhost", 
        port=7682,
        terminal_type=TerminalType.QCLI
    ) as client:
        
        # 检查终端状态
        print(f"终端状态: {client.terminal_state.value}")
        print(f"可执行命令: {client.can_execute_command}")
        
        async for chunk in client.execute_command_stream("Create a Lambda function"):
            state = chunk.get("state")
            content = chunk.get("content")
            metadata = chunk.get("metadata", {})
            
            if state == "thinking":
                print("🤔 AI is thinking...")
            elif state == "tool_use":
                print(f"🔧 Using tool: {metadata.get('tool_name', 'unknown')}")
            elif state == "streaming" and chunk.get("is_content"):
                print(content, end="")
            elif state == "complete":
                print("\n✅ Response complete")
                break

asyncio.run(advanced_qcli_chat())
```

### 通用终端使用

```python
async def use_generic_terminal():
    async with TerminalAPIClient(
        host="localhost", 
        port=7681,
        terminal_type=TerminalType.GENERIC
    ) as client:
        
        commands = ["pwd", "ls -la", "echo 'Hello World'"]
        
        for cmd in commands:
            print(f"\n执行命令: {cmd}")
            async for chunk in client.execute_command_stream(cmd):
                if chunk.get("content"):
                    print(chunk["content"], end="")
                elif chunk.get("state") == "complete":
                    success = chunk.get("command_success", False)
                    print(f"\n命令完成，成功: {success}")
                    break

asyncio.run(use_generic_terminal())
```

## 🛠️ 服务管理

```bash
# 服务控制
./ttyd/ttyd-service.sh start bash 7681     # 启动通用终端
./ttyd/ttyd-service.sh start qcli 7682     # 启动 Q CLI
./ttyd/ttyd-service.sh status bash 7681    # 查看状态
./ttyd/ttyd-service.sh stop-all            # 停止所有服务

# 测试
uv run python test_simple_terminal.py      # 简单终端测试
uv run python test_state_mapping.py        # 状态映射测试
uv run python test_event_driven.py         # 事件驱动测试
```

## 📊 流式输出格式

### 统一的流式块格式

```json
{
  "type": "streaming",
  "content": "Hello! I'm Amazon Q...",
  "is_content": true,
  "metadata": {
    "terminal_type": "qcli",
    "status_indicator": "💬",
    "raw_length": 156,
    "content_length": 23,
    "timestamp": 1704067200.123
  }
}
```

### 消息类型说明

| 类型 | 描述 | 指示符 | is_content |
|------|------|--------|------------|
| `thinking` | AI 思考中 | 🤔 | false |
| `tool_use` | 使用工具中 | 🔧 | false |
| `streaming` | 流式输出内容 | 💬 | true |
| `pending` | 等待用户输入 | ⏳ | false |
| `complete` | 回复完成 | ✅ | false |
| `error` | 执行错误 | ❌ | false |

## 🧪 测试

### 运行测试套件

```bash
# 基础功能测试
uv run ./tests/test_simple_terminal.py      # 简单终端功能测试

# 状态管理测试
uv run tests/test_conn_state_management.py   # 网络状态管理
uv run tests/test_state_mapping.py         # 状态映射机制测试
uv run tests/test_state_transitations.py   # 状态转换测试

# Web UI 测试
uv run tests/test_gradio_webui.py   # Gradio WebUI 测试
```

## 📝 许可证

MIT License

---

**注意**: 本项目专注于演示TTYD的Web终端API功能，适合学习和原型开发。生产环境使用请注意安全配置。
