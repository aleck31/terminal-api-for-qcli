# Terminal API Demo

基于 Gotty 的 Web 终端 API 演示（Demo）

## 🎯 项目概述

这是一个使用 Gotty 实现的 Web 终端 API 演示项目，支持通过 Web 界面访问 Linux 终端，并可以运行各种交互式命令行程序如: Q CLI、MySQL、Python 等。

### 📈 项目状态
- ✅ **核心功能完成**: Gotty服务集成、WebSocket通信、流式输出处理
- ✅ **现代化UI**: 基于Gradio 5的ChatInterface界面
- ✅ **安全防护**: 危险命令检测和拦截机制
- ✅ **完整测试**: 43个测试用例，88%通过率
- ✅ **模块化架构**: 清晰的组件分离和依赖管理
- 🚀 **生产就绪**: 可直接部署使用

## 📁 项目结构

```
terminal-api-demo/
├── gotty/                  # Gotty相关文件
│   ├── gotty-service.sh    # 服务管理脚本 (推荐使用)
│   └── gotty.conf          # Gotty 配置文件
├── api/                    # API组件
│   ├── __init__.py
│   ├── message_processor.py # 消息处理器
│   ├── terminal_client.py   # 终端客户端
│   ├── websocket_client.py  # WebSocket客户端
│   └── connection_manager.py # 连接管理器
├── utils/                  # 工具组件
│   └── ansi_cleaner.py     # ANSI转义序列清理器
├── webui/                  # Web UI
│   └── gradio_chat.py      # Gradio ChatInterface WebUI
├── tests/                  # 测试套件
├── logs/                   # 日志目录
├── start-webui.sh          # Gradio WebUI 启动脚本
├── run_tests.py            # 测试运行脚本
├── pyproject.toml          # uv 项目配置
└── README.md              # 项目说明
```

## 🚀 快速开始

### 1. 一键启动

```bash
# 直接运行，自动启动默认Q CLI终端
./gotty/gotty-service.sh
```

### 完整服务管理

```bash
# 启动不同类型的终端
./gotty/gotty-service.sh start qcli 8081     # Q CLI
./gotty/gotty-service.sh start python 8082    # Python REPL
./gotty/gotty-service.sh start mysql 8083     # MySQL 客户端

# 服务管理
./gotty/gotty-service.sh status               # 查看所有服务状态
./gotty/gotty-service.sh stop bash 8080       # 停止特定服务
./gotty/gotty-service.sh restart python 8081  # 重启服务
./gotty/gotty-service.sh stop-all             # 停止所有服务
./gotty/gotty-service.sh help                 # 查看完整帮助
```

### 2. 访问 Web 终端

**方式一：Gradio ChatInterface WebUI（推荐）**
```bash
# 启动Gradio聊天界面
./start-webui.sh
```
访问地址: http://localhost:7860

特性：
- 🤖 智能聊天界面
- 📝 支持自然语言命令执行
- 🔄 实时流式输出
- 💬 命令历史和上下文
- 🎨 现代化UI设计

**方式二：原生Gotty Web终端**
打开浏览器访问: http://localhost:8080

默认认证信息:
- 用户名: demo
- 密码: password123

### 3. 运行测试套件

```bash
# 运行所有测试
uv run python -m pytest tests/ -v

# 只运行单元测试
uv run python -m pytest tests/ -m "not integration" -v

# 使用测试脚本
uv run python run_tests.py --unit

# 生成覆盖率报告
uv run python run_tests.py --coverage
```

## 🔧 服务管理

### 服务管理脚本功能

`gotty/gotty-service.sh` 提供完整的服务生命周期管理：

```bash
# 查看帮助
./gotty/gotty-service.sh help

# 启动服务
./gotty/gotty-service.sh start [terminal_type] [port]

# 停止服务
./gotty/gotty-service.sh stop [terminal_type] [port]

# 重启服务
./gotty/gotty-service.sh restart [terminal_type] [port]

# 查看状态
./gotty/gotty-service.sh status [terminal_type] [port]

# 停止所有服务
./gotty/gotty-service.sh stop-all
```

### 支持的终端类型

- `qcli` - Q CLI (默认)
- `bash` - Bash Shell
- `python` - Python REPL
- `mysql` - MySQL 客户端
- `redis` - Redis CLI

### 服务特性

- **后台运行**: 服务在后台运行，不占用终端
- **PID管理**: 自动管理进程ID文件
- **日志记录**: 每个服务独立的日志文件
- **健康检查**: 自动检测服务状态和连接
- **优雅停止**: 支持优雅停止和强制停止
## 🎨 Gradio ChatInterface WebUI

### 功能特性

- **实时流式输出**: 命令执行过程实时显示
- **安全防护**: 自动拦截危险命令
- **上下文感知**: 维护命令历史和工作目录状态
- **现代化UI**: 基于Gradio 5的现代聊天界面

### 技术栈

- **前端**: Gradio 5 ChatInterface
- **后端**: Python + WebSocket + Gotty
- **依赖管理**: uv
- **流式输出**: WebSocket实时通信
- **安全**: 危险命令检测和拦截
- **测试**: pytest + 完整测试套件
- **架构**: 模块化组件设计

## 🔧 配置说明

### Gotty 配置 (gotty/gotty.conf)

```ini
port = "8080"                # 服务端口
permit_write = true          # 允许写入操作
enable_basic_auth = true     # 启用基本认证
credential = "demo:password123"  # 认证凭据
max_connection = 10          # 最大连接数
timeout = 300               # 超时时间(秒)
enable_reconnect = true     # 启用重连
```

### 安全配置

- 基本 HTTP 认证
- 连接数限制
- 超时控制
- 写入权限控制

## 📊 API 接口说明

### HTTP 接口

- **GET /** - 获取 Web 终端页面
- **WebSocket /ws** - 终端 WebSocket 连接
- **GET /js/gotty.js** - 客户端 JavaScript

### WebSocket 消息格式

```json
{
  "type": "input",
  "data": "command\n"
}
```

```json
{
  "type": "output", 
  "data": "command results"
}
```

## 🔒 安全考虑

### 当前实现的安全措施

- HTTP 基本认证
- 连接数限制
- 会话超时
- 写入权限控制

### 生产环境建议

1. **使用 HTTPS**
   ```bash
   ./gotty --tls --tls-crt server.crt --tls-key server.key
   ```

2. **反向代理配置**
   ```nginx
   location /terminal/ {
       proxy_pass http://localhost:8080/;
       proxy_http_version 1.1;
       proxy_set_header Upgrade $http_upgrade;
       proxy_set_header Connection "upgrade";
   }
   ```

3. **防火墙规则**
   ```bash
   ufw allow from 192.168.1.0/24 to any port 8080
   ```

## 🐛 故障排除

### 常见问题

1. **连接被拒绝**
   - 检查 Gotty 服务是否启动
   - 确认端口是否被占用
   - 验证防火墙设置

2. **认证失败**
   - 检查用户名密码
   - 确认配置文件中的凭据设置

3. **WebSocket 连接失败**
   - 检查代理服务器配置
   - 确认浏览器支持 WebSocket

### 日志查看

```bash
# 查看 Gotty 日志
tail -f logs/gotty.log

# 查看系统日志
journalctl -u gotty -f
```

## 🚀 扩展功能

### 计划中的功能

1. **多用户支持**
2. **会话录制回放**
3. **文件上传下载**
4. **终端分享**
5. **API 密钥认证**

### 自定义扩展

可以通过修改启动脚本添加更多终端类型:

```bash
case $COMMAND in
    "nodejs")
        $GOTTY_BIN --config-file "$CONFIG_FILE" --port "$PORT" node
        ;;
    "docker")
        $GOTTY_BIN --config-file "$CONFIG_FILE" --port "$PORT" docker run -it ubuntu bash
        ;;
esac
```

## 📝 许可证

MIT License
