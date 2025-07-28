# Terminal API Demo

基于 Gotty 的 Web 终端 API 演示（Demo）

## 🎯 项目概述

这是一个使用 Gotty 实现的 Web 终端 API 演示项目，支持通过 Web 界面访问 Linux 终端，并可以运行各种交互式命令行程序如: Q Cli、MySQL、Python 等。

## 📁 项目结构

```
terminal-api-mvp/
├── config/
│   └── gotty.conf          # Gotty 配置文件
├── scripts/
│   ├── start-gotty.sh      # 传统启动脚本 (前台运行)
│   ├── test-api.py         # API 测试脚本
│   └── demo.sh             # 演示脚本
├── web/
│   ├── client.html         # Web 客户端界面
│   ├── gradio_chat.py  # Gradio ChatInterface WebUI
│   └── simple_test.py      # 简化测试版本
├── logs/                   # 日志目录
├── pids/                   # PID 文件目录
├── gotty-service.sh        # 服务管理脚本 (推荐使用)
├── start-webui.sh          # Gradio WebUI 启动脚本
├── pyproject.toml          # uv 项目配置
└── README.md              # 项目说明
```

## 🚀 快速开始

### 一键启动（最简单）

```bash
# 直接运行，自动启动默认bash终端
./gotty-service.sh
```

### 完整服务管理

```bash
# 启动不同类型的终端
./gotty-service.sh start qcli 8081     # Q CLI
./gotty-service.sh start python 8082    # Python REPL
./gotty-service.sh start mysql 8083     # MySQL 客户端

# 服务管理
./gotty-service.sh status               # 查看所有服务状态
./gotty-service.sh stop bash 8080       # 停止特定服务
./gotty-service.sh restart python 8081  # 重启服务
./gotty-service.sh stop-all             # 停止所有服务
./gotty-service.sh help                 # 查看完整帮助
```

### 传统方式（前台运行）

```bash
# 如果需要前台运行和实时日志查看
./scripts/start-gotty.sh               # Bash终端
./scripts/start-gotty.sh python        # Python REPL
./scripts/start-gotty.sh mysql         # MySQL客户端
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

### 3. 使用 Web 客户端

打开 `web/client.html` 文件，或者启动一个简单的 HTTP 服务器:

```bash
cd web
python3 -m http.server 3000
```

然后访问: http://localhost:3000/client.html

### 4. 测试 API 连接

```bash
# 运行测试脚本
python3 scripts/test-api.py

# 自定义测试参数
python3 scripts/test-api.py --url http://localhost:8080 --username demo --password password123
```

## 🔧 服务管理

### 服务管理脚本功能

`gotty-service.sh` 提供完整的服务生命周期管理：

```bash
# 查看帮助
./gotty-service.sh help

# 启动服务
./gotty-service.sh start [terminal_type] [port]

# 停止服务
./gotty-service.sh stop [terminal_type] [port]

# 重启服务
./gotty-service.sh restart [terminal_type] [port]

# 查看状态
./gotty-service.sh status [terminal_type] [port]

# 停止所有服务
./gotty-service.sh stop-all
```

### 支持的终端类型

- `bash` - Bash Shell (默认)
- `python` - Python REPL
- `mysql` - MySQL 客户端
- `redis` - Redis CLI
- `htop` - 系统监控

### 服务特性

- **后台运行**: 服务在后台运行，不占用终端
- **PID管理**: 自动管理进程ID文件
- **日志记录**: 每个服务独立的日志文件
- **健康检查**: 自动检测服务状态和连接
- **优雅停止**: 支持优雅停止和强制停止
## 🎨 Gradio ChatInterface WebUI

### 功能特性

- **智能命令解析**: 支持自然语言命令执行
  - `执行: ls -la` 或 `执行：pwd`
  - `运行: ps aux` 或 `运行：df -h`
  - `$ ls -la` 或 `> pwd`
  - 直接输入常见命令如：`ls`, `pwd`, `whoami`

- **实时流式输出**: 命令执行过程实时显示
- **安全防护**: 自动拦截危险命令
- **上下文感知**: 维护命令历史和工作目录状态
- **现代化UI**: 基于Gradio 5的现代聊天界面

### 使用示例

```bash
# 启动WebUI
./start-webui.sh

# 在聊天界面中输入：
help                    # 查看帮助
执行: ls -la           # 列出文件详情
运行: python3 --version # 查看Python版本
$ curl -I http://localhost:8080  # 测试API连接
检查API状态            # 查看系统状态
```

### 技术栈

- **前端**: Gradio 5 ChatInterface
- **后端**: Python + subprocess
- **依赖管理**: uv
- **流式输出**: Python Generator
- **安全**: 命令白名单过滤

## 🔧 配置说明

### Gotty 配置 (config/gotty.conf)

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

## 🧪 测试功能

### 支持的终端类型

1. **Bash Shell** - 标准 Linux 终端
2. **Python REPL** - Python 交互式解释器
3. **MySQL Client** - MySQL 数据库客户端
4. **Redis CLI** - Redis 命令行客户端

### 测试场景

1. **基本连接测试**
   ```bash
   curl -u demo:password123 http://localhost:8080
   ```

2. **MySQL 交互测试**
   - 启动 MySQL 客户端
   - 连接数据库
   - 执行 SQL 查询
   - 查看结果

3. **Python 脚本执行**
   - 启动 Python REPL
   - 执行 Python 代码
   - 导入模块
   - 运行复杂脚本

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
  "data": "command output"
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

## 🤝 贡献

欢迎提交 Issue 和 Pull Request！

## 📞 联系方式

如有问题，请创建 GitHub Issue。
