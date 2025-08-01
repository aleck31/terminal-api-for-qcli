# ttyd WebSocket 协议开发指南

基于实际测试和源码分析的 ttyd WebSocket 通信协议完整指南。

## 📋 目录

- [协议概述](#协议概述)
- [连接流程](#连接流程)
- [消息格式](#消息格式)
- [认证机制](#认证机制)
- [实测发现](#实测发现)
- [常见问题](#常见问题)
- [最佳实践](#最佳实践)
- [调试工具](#调试工具)
- [服务器配置](#服务器配置)

## 协议概述

ttyd 使用二进制 WebSocket 协议进行终端通信，消息格式为：
- **第一个字节**：命令类型（ASCII 字符）
- **剩余字节**：消息数据

### 支持的命令类型

**客户端到服务器：**
- `'0'` (INPUT) - 发送输入数据到终端
- `'1'` (RESIZE_TERMINAL) - 调整终端大小
- `'2'` (PAUSE) - 暂停输出
- `'3'` (RESUME) - 恢复输出
- `'{'` (JSON_DATA) - 初始化消息（JSON格式）

**服务器到客户端：**
- `'0'` (OUTPUT) - 终端输出数据
- `'1'` (SET_WINDOW_TITLE) - 设置窗口标题
- `'2'` (SET_PREFERENCES) - 设置客户端偏好

## 连接流程

### 1. WebSocket 握手

```javascript
// 关键：必须包含 HTTP 基本认证头
const websocket = new WebSocket('ws://localhost:7681/ws', ['tty'], {
    headers: {
        'Authorization': 'Basic ' + btoa('username:password')
    }
});
```

**Python 示例：**
```python
import websockets
import base64

auth_token = base64.b64encode(f"{username}:{password}".encode()).decode()
websocket = await websockets.connect(
    url,
    subprotocols=['tty'],
    additional_headers={
        "Authorization": f"Basic {auth_token}"
    }
)
```

### 2. 初始化消息

连接成功后，立即发送初始化消息：

```json
{
    "AuthToken": "base64_encoded_username:password",
    "columns": 80,
    "rows": 24
}
```

### 3. 等待服务器初始响应

服务器会发送两个初始消息：
1. `SET_WINDOW_TITLE` (命令 '1') - 设置窗口标题
2. `SET_PREFERENCES` (命令 '2') - 客户端偏好设置

### 4. 开始终端交互

初始化完成后，可以发送命令和接收输出。

## 消息格式

### 发送命令格式

```python
# 发送命令到终端
command = "echo 'Hello World'\n"
message = b'0' + command.encode('utf-8')
await websocket.send(message)
```

### 接收输出格式

```python
# 处理服务器消息
message = await websocket.recv()
if isinstance(message, bytes) and len(message) > 0:
    command = chr(message[0])
    data = message[1:]
    
    if command == '0':  # OUTPUT
        output = data.decode('utf-8', errors='ignore')
        # 处理终端输出
```

## 认证机制

### 双重认证要求

ttyd 需要**双重认证**：

1. **HTTP 基本认证头**（WebSocket 握手时）
   ```
   Authorization: Basic base64(username:password)
   ```

2. **JSON 初始化消息中的 AuthToken**
   ```json
   {"AuthToken": "base64(username:password)", ...}
   ```

### 认证失败的表现

- WebSocket 握手失败：`did not receive a valid HTTP response`
- 连接被拒绝：日志显示 `User code denied connection`
- 连接立即关闭：状态码 1006 (Policy Violation)

## 实测发现

### ✅ 成功验证的功能

1. **WebSocket 连接** - 使用正确的认证头可以成功连接
2. **初始化流程** - 能够接收窗口标题和偏好设置
3. **数据接收** - 可以接收到终端输出数据
4. **写入模式** - 使用 `-W` 参数启用输入功能

### ⚠️ 发现的问题

1. **输出内容复杂** - 包含大量 ANSI 转义序列和 OSC 序列
2. **缓冲问题** - 某些命令的输出可能被缓冲或延迟
3. **只读模式陷阱** - 默认启动为只读模式，需要显式启用 `-W`
4. **参数格式敏感** - 长参数格式可能导致连接问题

### 📊 实测输出示例

**典型的终端输出包含：**
```
原始输出: '\x1b]697;OSCUnlock=\x07\x1b]697;Dir=/path\x07\x1b]697;Shell=bash\x07'
ANSI序列: ['\x1b[?2004h', '\x1b[01;32m', '\x1b[00m']
OSC序列: ['\x1b]697;Dir=/path\x07', '\x1b]0;title\x07']
纯文本: 'ubuntu@hostname:~/path$ '
```

## 常见问题

### 问题 1：连接失败 "did not receive a valid HTTP response"

**原因：** 缺少 HTTP 基本认证头

**解决：** 在 WebSocket 握手时添加认证头
```python
additional_headers={"Authorization": f"Basic {auth_token}"}
```

### 问题 2：连接成功但无法发送命令

**原因：** ttyd 启动时未启用写入模式

**解决：** 启动时添加 `-W` 参数
```bash
ttyd -p 7681 -c demo:password123 -W bash
```

### 问题 3：接收到数据但无法读取命令输出

**原因：** 输出包含大量 ANSI/OSC 转义序列

**解决：** 实现转义序列清理器
```python
import re

def clean_ansi(text):
    # 移除 ANSI 转义序列
    ansi_escape = re.compile(r'\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])')
    cleaned = ansi_escape.sub('', text)
    
    # 移除 OSC 序列
    osc_escape = re.compile(r'\x1B\][^\x07]*\x07')
    cleaned = osc_escape.sub('', cleaned)
    
    return cleaned.strip()
```

### 问题 4：命令执行后无响应

**原因：** 
- 命令可能需要时间执行
- 输出被缓冲
- 需要等待提示符返回

**解决：** 实现超时等待和提示符检测
```python
async def wait_for_prompt(websocket, timeout=5.0):
    start_time = time.time()
    while time.time() - start_time < timeout:
        message = await websocket.recv()
        # 检测提示符 $ 或 #
        if '$' in output or '#' in output:
            return True
    return False
```

### 问题 5：ttyd 参数格式兼容性

**重要发现：必须使用短参数格式**

```bash
# ✅ 正确格式（短参数）- 完全兼容
ttyd -p 7681 -c demo:password123 -W -m 10 -P 30 -d 7 -T xterm-256color bash

# ❌ 错误格式（长参数）- 可能导致连接问题
ttyd --port 7681 --credential demo:password123 --writable --max-clients 10
```

**问题表现：**
- 服务启动成功，HTTP 访问正常
- WebSocket 连接建立但立即关闭
- 客户端报告连接失败

## 最佳实践

### 1. 连接建立

```python
async def connect_to_ttyd(url, username, password):
    auth_token = base64.b64encode(f"{username}:{password}".encode()).decode()
    
    try:
        websocket = await websockets.connect(
            url,
            subprotocols=['tty'],
            additional_headers={
                "Authorization": f"Basic {auth_token}"
            }
        )
        
        # 发送初始化消息
        init_message = {
            "AuthToken": auth_token,
            "columns": 80,
            "rows": 24
        }
        await websocket.send(json.dumps(init_message).encode())
        
        # 等待初始响应
        await wait_for_initial_responses(websocket)
        
        return websocket
        
    except Exception as e:
        print(f"连接失败: {e}")
        return None
```

### 2. 命令执行

```python
async def execute_command(websocket, command):
    # 确保命令以换行符结尾
    if not command.endswith('\n'):
        command += '\n'
    
    # 发送命令
    message = b'0' + command.encode('utf-8')
    await websocket.send(message)
    
    # 收集输出
    output_buffer = []
    timeout = 5.0
    start_time = time.time()
    
    while time.time() - start_time < timeout:
        try:
            message = await asyncio.wait_for(websocket.recv(), timeout=1.0)
            if isinstance(message, bytes) and len(message) > 0:
                cmd = chr(message[0])
                if cmd == '0':  # OUTPUT
                    data = message[1:].decode('utf-8', errors='ignore')
                    output_buffer.append(data)
                    
                    # 检测命令完成（提示符出现）
                    if '$' in data or '#' in data:
                        break
                        
        except asyncio.TimeoutError:
            break
    
    # 清理并返回输出
    raw_output = ''.join(output_buffer)
    return clean_ansi(raw_output)
```

### 3. 输出清理

```python
def clean_terminal_output(raw_output: str) -> str:
    """完整的终端输出清理"""
    if not raw_output:
        return ""
    
    text = raw_output
    
    # 1. 移除 OSC 697 序列（shell 集成信息）
    text = re.sub(r'697;[^697\n]*(?=697|$)', '', text)
    
    # 2. 移除所有以分号开头的 shell 集成信息
    text = re.sub(r';[A-Za-z][A-Za-z0-9]*=[^\n]*', '', text)
    
    # 3. 移除 ANSI 转义序列
    ansi_escape = re.compile(r'\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])')
    text = ansi_escape.sub('', text)
    
    # 4. 移除其他 OSC 序列
    osc_pattern = re.compile(r'\x1B\][^\x07]*\x07')
    text = osc_pattern.sub('', text)
    
    # 5. 清理提示符残留
    text = re.sub(r'ubuntu@[^:]*:[^$]*\$\s*', '', text)
    text = re.sub(r'StartPrompt[^\n]*', '', text)
    text = re.sub(r'PreExec[^\n]*', '', text)
    
    # 6. 过滤空行和以分号开头的行
    lines = [line.strip() for line in text.split('\n') 
             if line.strip() and not line.strip().startswith(';')]
    
    return '\n'.join(lines)
```

### 4. 错误处理

```python
async def robust_ttyd_client(url, username, password):
    max_retries = 3
    retry_delay = 1.0
    
    for attempt in range(max_retries):
        try:
            websocket = await connect_to_ttyd(url, username, password)
            if websocket:
                return websocket
                
        except websockets.exceptions.ConnectionClosed:
            print(f"连接关闭，重试 {attempt + 1}/{max_retries}")
            await asyncio.sleep(retry_delay)
            retry_delay *= 2
            
        except Exception as e:
            print(f"连接错误: {e}")
            if attempt == max_retries - 1:
                raise
            await asyncio.sleep(retry_delay)
    
    return None
```

## 调试工具

### 1. 网络抓包

使用 Wireshark 或 tcpdump 分析 WebSocket 流量：
```bash
tcpdump -i lo -A -s 0 port 7681
```

### 2. 详细日志

启动 ttyd 时启用详细日志：
```bash
ttyd -d 7 -p 7681 -c demo:password123 -W bash
```

### 3. 连接测试

```bash
# 测试 HTTP 基本认证
curl -u demo:password123 http://localhost:7681/ -I

# 测试端口连通性
nc -zv localhost 7681
```

## 服务器配置

### 推荐的 ttyd 启动参数

```bash
# 基本配置（使用短参数格式）
ttyd -p 7681 -c username:password -W bash

# 生产环境配置
ttyd -p 7681 \
     -c username:password \
     -W \
     -m 10 \
     -T xterm-256color \
     -O \
     bash

# 调试配置
ttyd -p 7681 \
     -c username:password \
     -W \
     -d 7 \
     bash
```

### 重要参数说明

- `-p` / `--port`: 监听端口
- `-c` / `--credential`: 认证凭据 (username:password)
- `-W` / `--writable`: 启用写入模式（重要！）
- `-m` / `--max-clients`: 最大客户端连接数
- `-T` / `--terminal-type`: 终端类型
- `-O` / `--check-origin`: 检查请求来源
- `-d` / `--debug`: 调试级别 (0-7)

### 安全考虑

1. **使用强密码** - 避免使用默认或弱密码
2. **限制连接数** - 使用 `-m` 限制并发连接
3. **检查来源** - 使用 `-O` 验证请求来源
4. **使用 HTTPS** - 生产环境中启用 SSL/TLS
5. **防火墙配置** - 限制访问 IP 范围

## 版本兼容性

**测试环境：**
- ttyd: 1.7.7-40e79c7
- libwebsockets: 4.3.3
- Python websockets: 15.0.1

**已知兼容性问题：**
- websockets 库 15.x 版本 API 变更
- 不同版本的 ttyd 可能有细微差异
- 长参数格式在某些版本中可能不稳定

## 总结

ttyd WebSocket 协议的关键要点：

1. **双重认证必需** - HTTP 头 + JSON AuthToken
2. **启用写入模式** - 使用 `-W` 参数
3. **使用短参数格式** - 避免长参数格式的兼容性问题
4. **处理复杂输出** - 实现完整的 ANSI/OSC 序列清理
5. **异步处理** - 使用适当的超时和缓冲机制
6. **错误恢复** - 实现重连和错误处理逻辑

通过遵循本指南，可以成功实现与 ttyd 的稳定通信。

---

*文档版本：2.0 - 通用开发指南*
*最后更新：2025-08-01*
