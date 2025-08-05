# Terminal API Demo

基于 TTYD 的 Web 终端 API 演示项目

## 🎯 项目概述

这是一个基于 TTYD 实现的 Web 终端 API 演示项目，支持通过 Web 界面访问 Linux 终端，并可以运行各种交互式命令行程序如: Bash、Q CLI、Python 等。

### 📈 项目状态
- ✅ **核心功能完成**: TTYD服务集成、WebSocket通信、流式输出处理
- ✅ **现代化UI**: 基于Gradio 5的ChatInterface界面，支持Markdown格式输出
- ✅ **安全防护**: 危险命令检测和拦截机制
- ✅ **完整测试**: 集成测试套件，确保稳定性
- ✅ **简洁架构**: 避免过度工程化，专注核心功能
- 🚀 **生产就绪**: 可直接部署使用

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
├── qcli_interactive_demo.py # Q CLI 交互演示应用
├── run_tests.py            # 测试运行器
├── tests/                  # 测试套件
├── logs/                   # 日志目录
├── start-webui.sh          # Gradio WebUI 启动脚本
└── README.md
```

## 🏗️ 架构设计

采用**模块化分层架构**，职责明确，易于维护：

```
               ┌──────────────────────────────────────┐
               │            Gradio WebUI              │  ← User Interface Layer
               │         (gradio_chat.py)             │
               └──────────────────┬───────────────────┘
                                    │
               ┌──────────────────▼───────────────────┐
               │       TerminalAPIClient              │  ← **Main API Interface**
               │    (terminal_api_client.py)          │
               │   - Component coordination           │
               │   - Unified external interface       │
               └─────┬──────────────────────────▲─────┘
      Request Flow   │                          │   Response Flow
                     │                          │
   execute_command() │                          │ Process results
               ┌─────▼─────────┐      ┌─────────└─────┐
               │  Command      │      │  Output       │  ← **Component Layer**
               │  Executor     │      │ Processor     │
               │               │      │               │
               │ Cmd lifecycle │      │ Data cleaning │
               └─────┬─────────┘      └─────────▲─────┘
   send_command()    │                          │ raw_output
               ┌─────▼──────────────────────────└─────┐
               │               Connection             │
               │                 Manager              │  ← **Connection Layer**
               │         Connection lifecycle         │
               └─────┬──────────────────────────▲─────┘
   WebSocket comm    │                          │ Message receive
               ┌─────▼──────────────────────────└─────┐
               │                WebSocket             │  ← **Communication Layer**
               │                  Client              │
               └─────┬──────────────────────────▲─────┘
                     │                          │
               ┌─────▼──────────────────────────└─────┐
               │                 ttyd                 │  ← **Terminal Server**
               │      (WebSocket Terminal Server)     │
               └──────────────────────────────────────┘
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

### 数据流

```
原始数据 → CommandExecutor (完成检测) → OutputProcessor (清理) → 用户
```

**设计原则：**
- ✅ **单一职责**：每个组件只负责一个明确的功能
- ✅ **清晰边界**：组件间接口简单明确
- ✅ **单向数据流**：避免循环依赖和重复处理

## 🚀 快速开始

### 1. 启动 TTYD 服务

```bash
# 启动默认服务 (bash:7681)
./ttyd/ttyd-service.sh start

# 启动不同类型的终端
./ttyd/ttyd-service.sh start python 7682    # Python REPL
./ttyd/ttyd-service.sh start qcli 8081      # Q CLI (如果已安装)
```

### 2. 访问 Web 终端

**方式一：Gradio ChatInterface WebUI（推荐）**
```bash
# 启动Gradio聊天界面
./start-webui.sh
```
访问地址: http://localhost:7860

特性：
- 🤖 智能聊天界面，支持自然语言命令执行
- 📝 Markdown格式输出，清晰易读
- 🔄 实时流式输出处理
- 💬 命令历史和上下文维护
- 🎨 现代化UI设计

**方式二：Q CLI 交互演示**
```bash
# 启动 Q CLI 交互演示（快速启动）
uv run python qcli_interactive_demo.py
```

特性：
- 🚀 **快速启动**: 通过 tmux 会话共享，5秒连接 vs 30+秒重新初始化
- 💬 **交互式对话**: 直接与 Q CLI 对话
- 📊 **会话信息**: 查看连接状态和会话信息

**方式三：原生TTYD Web终端**
打开浏览器访问: http://localhost:7681

默认认证信息:
- 用户名: demo
- 密码: password123

### 3. API 使用示例

```python
import asyncio
from api import TerminalAPIClient

async def example():
    # 使用异步上下文管理器
    async with TerminalAPIClient(
        host="localhost", 
        port=7681, 
        username="demo", 
        password="password123"
    ) as client:
        
        # 执行命令
        result = await client.execute_command('ls -la')
        
        print(f"成功: {result.success}")
        print(f"退出码: {result.exit_code}")
        print(f"执行时间: {result.execution_time:.2f}秒")
        print("清理后输出:")
        print(result.formatted_output)

# 运行示例
asyncio.run(example())
```

## 🔧 服务管理

### TTYD 服务脚本

`ttyd/ttyd-service.sh` 提供完整的服务生命周期管理：

```bash
# 基本命令
./ttyd/ttyd-service.sh start [type] [port]  # 启动服务
./ttyd/ttyd-service.sh stop [type] [port]   # 停止服务
./ttyd/ttyd-service.sh restart [type] [port] # 重启服务
./ttyd/ttyd-service.sh status [type] [port] # 查看状态
./ttyd/ttyd-service.sh stop-all             # 停止所有服务
./ttyd/ttyd-service.sh help                 # 显示帮助

# 示例
./ttyd/ttyd-service.sh start               # 启动默认服务 (bash:7681)
./ttyd/ttyd-service.sh start python 7682   # 启动Python服务 (端口7682)
./ttyd/ttyd-service.sh status              # 查看默认服务状态
```

### 支持的终端类型

- `bash` - Bash Shell (默认)
- `python` - Python REPL
- `qcli` - Q CLI (需要先安装 Q CLI)

### 配置文件

`ttyd/conf.ini` 支持完整的配置管理。

## 🎨 格式化输出特性

项目的一大特色是智能的输出格式化，将原始终端输出转换为友好的Markdown格式：

### 输出清理

- **ANSI序列清理**: 移除颜色和格式控制字符
- **OSC序列清理**: 移除现代shell的集成信息
- **提示符清理**: 移除命令提示符残留
- **空白处理**: 智能处理多余的空白和换行

### Markdown格式化

```markdown
## ✅ 命令执行 - 成功
**命令:** `ls -la`
**执行时间:** 0.01秒
**输出:**
```bash
total 392
drwxrwxr-x 15 ubuntu ubuntu  6144 Aug  1 09:49 .
drwxrwxr-x 12 ubuntu ubuntu  6144 Jul 30 11:35 ..
-rw-rw-r--  1 ubuntu ubuntu  8624 Aug  1 09:43 README.md
```
---
```

## 🧪 测试

### 运行测试

```bash
# 集成测试（需要TTYD服务运行）
uv run python tests/test_terminal_api_integration.py

# 服务脚本测试
uv run python tests/test_ttyd_service.py

# 格式化输出测试
uv run python tests/test_formatted_output.py

# 使用pytest运行所有测试
uv run python -m pytest tests/ -v
```

### 测试覆盖

- ✅ WebSocket连接和认证
- ✅ 命令执行和输出处理
- ✅ 格式化和清理功能
- ✅ 服务管理脚本
- ✅ 错误处理和恢复

## 🔒 安全考虑

### 当前安全措施

- **HTTP基本认证**: 用户名密码验证
- **连接数限制**: 防止资源耗尽
- **命令权限**: 基于启动用户的权限
- **输入验证**: 防止恶意输入

### 生产环境建议

1. **使用HTTPS/WSS**
   ```bash
   # 在conf.ini中配置SSL
   ssl=true
   ssl_cert="/path/to/cert.pem"
   ssl_key="/path/to/key.pem"
   ```

2. **强化认证**
   - 使用强密码
   - 定期更换凭据
   - 考虑集成外部认证系统

3. **网络安全**
   - 使用防火墙限制访问
   - 配置反向代理
   - 启用访问日志

## 🐛 故障排除

### 常见问题

1. **连接失败**
   ```bash
   # 检查服务状态
   ./ttyd/ttyd-service.sh status
   
   # 查看日志
   tail -f logs/ttyd-bash-7681.log
   ```

2. **认证问题**
   - 确认conf.ini中的credential配置
   - 检查用户名密码格式

3. **输出格式问题**
   - 检查format_output参数是否启用
   - 查看utils.py中的清理规则

### 调试技巧

```bash
# 启用详细日志
# 在conf.ini中设置: debug_level=7

# 手动测试连接
curl -u demo:password123 http://localhost:7681/ -I

# 检查WebSocket连接
# 使用浏览器开发者工具查看WebSocket流量
```

## 🚀 扩展和定制

### 添加新的终端类型

1. 在`conf.ini`中添加命令配置:
   ```ini
   nodejs_command="node"
   ```

2. 在`ttyd-service.sh`的`get_terminal_command`函数中添加处理:
   ```bash
   "nodejs")
       echo "$(get_config nodejs_command)"
       ;;
   ```

### 自定义格式化规则

修改`api/utils.py`中的`TerminalOutputFormatter`类:

```python
def _looks_like_code_output(self, text: str) -> bool:
    # 添加自定义的代码输出检测规则
    custom_indicators = ['your_pattern']
    return any(indicator in text for indicator in custom_indicators)
```

## 📚 开发文档

- [项目架构文档](docs/) - 详细的技术文档
- [TTYD协议开发指南](docs/ttyd-protocol-dev-guide.md) - 通用的ttyd开发经验和技巧

## 🤝 贡献

欢迎提交Issue和Pull Request！

### 开发环境设置

```bash
# 安装依赖
uv sync

# 运行测试
uv run python -m pytest

# 启动开发服务
./ttyd/ttyd-service.sh start
```

## 📝 许可证

MIT License

---

**注意**: 本项目专注于演示TTYD的Web终端API功能，适合学习和原型开发。生产环境使用请注意安全配置。
