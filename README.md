# Terminal API for Q CLI

基于 TTYD 的 Web 终端 API，支持与 Amazon Q CLI 进行流式交互。采用**统一数据流架构**，提供高性能、可维护的终端交互体验。

## 🎯 项目概述

这是一个基于 TTYD 实现的 Web 终端 API 项目，支持通过 Web 界面访问 Linux 终端，并可以运行各种交互式命令行程序如: Bash、Q CLI、Python 等。

## 📋 主要特性

- ✅ **事件驱动架构**: 组件间通过事件通信，松耦合设计
- ✅ **分层状态管理**: 协议、连接、业务三层状态管理，职责清晰
- ✅ **自动状态映射**: 连接状态变化自动映射为业务状态
- ✅ **智能消息识别**: 自动识别 Q CLI 思考、工具使用、内容输出等状态
- ✅ **统一数据格式**: 所有终端类型使用相同的 StreamChunk 格式
- ✅ **流式输出**: 实时显示 Q CLI 思考和回复过程
- ✅ **Web 界面**: 现代化聊天界面，支持 Markdown 输出
- ✅ **API 接口**: 支持编程方式集成

## 📁 项目结构

```
terminal-api-for-qcli/
├── api/                         # 核心API组件
│   ├── data_structures.py       # 统一数据结构定义
│   ├── terminal_api_client.py   # 主要API接口
│   ├── message_processor.py      # 统一消息处理器
│   ├── command_executor.py      # 命令执行器
│   ├── connection_manager.py    # 连接管理器
│   ├── websocket_client.py      # WebSocket客户端
│   └── utils/                   # 工具组件
│       └── ansi_formatter.py    # 统一ANSI处理工具
├── tests/                       # 测试套件
│   └── run_tests.py             # 统一测试运行器
├── ttyd/                        # TTYD服务管理
│   ├── ttyd-service.sh          # 服务管理脚本
│   └── conf.ini                 # 配置文件
├── webui/                       # Web UI
│   └── gradio_chat.py           # Gradio ChatInterface WebUI
├── docs/                        # 文档目录
│   ├── unified_data_flow_design.md # 统一数据流设计文档
│   └── ttyd-protocol-dev-guide.md  # TTYD WebSocket 协议开发指南
├── start-webui.sh               # Gradio WebUI 启动脚本
├── demo_qterm_interactive.py          # 命令行演示
└── README.md
```

## 🏗️ 核心组件架构

### 设计原则
- **分层清晰**: 协议层、连接层、业务层职责明确
- **单一职责**: 每层专注核心功能，组件间通过事件和回调通信
- **统一格式**: 中间使用统一的 StreamChunk 数据结构
- **延迟转换**: 只在最后一步转换为API格式
- **集中处理**: 错误处理和格式化集中在 MessageProcessor

### 架构层次
```
┌──────────────────────────────────────────────────────────────┐
│                TerminalAPIClient                             │
│                (Business Layer)                              │
│  • Business process coordination                             │
│  • User interface provision                                  │
│  • Component lifecycle management                            │
│  • Business state management (IDLE, BUSY, ERROR, etc.)       │
├──────────────────────────────────────────────────────────────┤
│  ConnectionManager │  CommandExecutor   │  MessageProcessor  │
│  (Connection Mgmt) │  (Command Exec)    │  (Output Process)  │
│  • Connection      │  • Stateless cmd   │  • Data cleaning   │
│    lifecycle       │    execution       │    & conversion    │
│  • Event-driven    │  • Completion      │  • Message type    │
│    msg dispatch    │    detection       │    identification  │
├──────────────────────────────────────────────────────────────┤
│                 TtydWebSocketClient                          │
│                (Protocol Layer)                              │
│  • WebSocket connection establish/disconnect                 │
│  • ttyd message format processing                            │
│  • Authentication handling                                   │
│  • websockets 15.x ClientConnection API                      │
└──────────────────────────────────────────────────────────────┘
```

#### **🔧 组件职责**
- **`TerminalAPIClient`** - 业务协调层，负责组件协调、业务状态管理和连接状态映射
- **`CommandExecutor`** - 无状态命令执行工具，专注命令执行逻辑和活跃性/完成检测
- **`MessageProcessor`** - 统一数据处理器，专注数据转换和消息类型识别
- **`ConnectionManager`** - 连接管理器，管理连接生命周期和事件驱动消息分发
- **`TtydWebSocketClient`** - 协议实现层，处理 ttyd 协议和 WebSocket 通信

#### **🔄 状态管理**
- **协议状态** (TtydWebSocketClient): `DISCONNECTED` → `CONNECTING` → `AUTHENTICATING` → `PROTOCOL_READY`
- **连接状态** (ConnectionManager): `IDLE` → `CONNECTING` → `CONNECTED` / `FAILED` → `DISCONNECTED`
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
- **交互演示**: `uv run python demo_qterm_interactive.py`

默认认证: `demo` / `password123`

## 🔧 API 使用

### 基础用法

```python
import asyncio
from api import TerminalAPIClient
from api.data_structures import TerminalType

async def chat_with_qcli():
    async with TerminalAPIClient(
        host="localhost", 
        port=7682,
        terminal_type=TerminalType.QCLI
    ) as client:
        
        # 流式接口
        async for chunk in client.execute_command_stream("What is Lambda?"):
            if chunk.get("type") == "content":
                print(chunk["content"], end="")
            elif chunk.get("type") == "complete":
                break

asyncio.run(chat_with_qcli())
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
                if chunk.get("type") == "content":
                    print(chunk["content"], end="")
                elif chunk.get("type") == "complete":
                    success = chunk.get("metadata", {}).get("command_success", False)
                    print(f"\n命令完成，成功: {success}")
                    break

asyncio.run(use_generic_terminal())
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
            chunk_type = chunk.get("type")
            content = chunk.get("content")
            metadata = chunk.get("metadata", {})
            
            if chunk_type == "thinking":
                print("🤔 AI is thinking...")
            elif chunk_type == "tool_use":
                print(f"🔧 Using tool: {metadata.get('tool_name', 'unknown')}")
            elif chunk_type == "content":
                print(content, end="")
            elif chunk_type == "complete":
                print("\n✅ Response complete")
                break

asyncio.run(advanced_qcli_chat())
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
  "content": "Hello! I'm Amazon Q...",
  "type": "content",
  "metadata": {
    "terminal_type": "qcli",
    "raw_length": 156,
    "content_length": 23
  },
  "timestamp": 1704067200.123
}
```

### 消息类型说明

| 类型 | 描述 | 用途 |
|------|------|------|
| `thinking` | AI 思考中 | 显示思考指示器 |
| `tool_use` | 使用工具中 | 显示工具信息 |
| `content` | 文本内容输出 | 显示给用户的内容 |
| `pending` | 等待用户输入 | 显示等待提示 |
| `complete` | 回复完成 | 显示完成信息 |
| `error` | 执行错误 | 显示错误信息 |

## 🧪 测试

### 运行测试套件

```bash
# 统一数据流架构测试（默认）
uv run python tests/run_tests.py

# 或明确指定
uv run python tests/run_tests.py --unified

# 集成测试（需要ttyd服务）
uv run python tests/run_tests.py --integration

# 运行所有测试
uv run python tests/run_tests.py --all
```

## 📝 许可证

MIT License

---

**注意**: 本项目专注于演示TTYD的Web终端API功能，适合学习和原型开发。生产环境使用请注意安全配置。
