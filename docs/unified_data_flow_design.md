# 统一数据流架构设计文档

## 设计目标

规范化收发消息流程，减少不必要的数据转换开销，统一数据格式，无论是 Q CLI 还是通用终端应用，经过不同的 formatter 处理后最终应该以相同的格式流式输出。

## 架构概览

### 核心设计原则

1. **分层清晰** - 协议层、连接层、业务层职责明确
2. **单一职责** - 每层专注核心功能，组件间通过事件和回调通信
3. **统一格式** - 中间使用统一的 StreamChunk 数据结构
4. **延迟转换** - 只在最后一步转换为API格式
5. **集中处理** - 错误处理和格式化集中在 MessageProcessor

### 架构层次

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
               │   - Business state management        │
               │   - Unified external interface       │
               └─────┬──────────────────────────▲─────┘
      Request Flow   │                          │   Response Flow
                     │                          │
   execute_command() │                          │ StreamChunk
               ┌─────▼─────────┐      ┌─────────└─────┐
               │  Command      │◄────►│  Message      │  ← **Processing Layer**
               │  Executor     │      │ Processor     │
               │               │      │               │
               │ Cmd lifecycle │      │ Data cleaning │
               │ Activity mgmt │      │ Type detection│
               └─────┬─────────┘      └─────────▲─────┘
   send_command()    │                          |
               ┌─────▼──────────────────────────└─────┐
               │               Connection             │
               │                 Manager              │  ← **Connection Layer**
               │         - Connection lifecycle       │
               │         - Event-driven dispatch      │
               │         - State mapping              │
               └─────┬──────────────────────────▲─────┘
   WebSocket ops     │                          │ raw_message
               ┌─────▼──────────────────────────└─────┐
               │            TtydWebSocketClient       │  ← **Protocol Layer**
               │        (websockets 15.x API)         │
               │         - ClientConnection           │
               │         - ttyd protocol parsing      │
               │         - Authentication             │
               └─────┬──────────────────────────▲─────┘
                     │                          │
               ┌─────▼──────────────────────────└─────┐
               │                 ttyd                 │  ← **Terminal Server**
               │      (WebSocket Terminal Server)     │
               └──────────────────────────────────────┘
```

#### **层次说明**：

**🎨 User Interface Layer**
- **Gradio WebUI**: 现代化聊天界面，支持Markdown渲染和流式显示

**🚀 Main API Interface**  
- **TerminalAPIClient**: 统一的外部接口，负责组件协调和业务状态管理
- 提供`execute_command_stream()`等高级API
- 管理组件生命周期和状态映射（INITIALIZING → IDLE → BUSY → IDLE）

**⚙️ Processing Layer**
- **CommandExecutor**: 命令生命周期管理，活跃性检测，execution_time注入
- **MessageProcessor**: 统一数据处理，ANSI清理，类型识别，StreamChunk构建
- 两者通过依赖注入紧密协作

**🔗 Connection Layer**
- **ConnectionManager**: 连接生命周期管理，事件驱动消息分发
- 连接状态到业务状态的映射
- 管理WebSocket客户端实例

**📡 Protocol Layer**  
- **TtydWebSocketClient**: WebSocket协议实现，使用现代websockets 15.x ClientConnection API
- ttyd协议解析，认证处理，连接状态管理（使用State枚举）

**🖥️ Terminal Server**
- **ttyd**: WebSocket终端服务器，提供终端访问能力

## 数据流程

### 发送消息流程（Request Flow）
```
Gradio WebUI
    ↓ user_input
TerminalAPIClient.execute_command_stream(command)
    ↓ execute_command()
CommandExecutor.execute_command()
    ↓ send_command()
ConnectionManager.send_command()
    ↓ WebSocket comm
TtydWebSocketClient.send_command()
    ↓ ttyd protocol
ttyd Terminal Server
```

### 接收消息流程（Response Flow）

统一数据处理流程，确保原始数据完整性的同时实现统一格式输出：

```
ttyd Terminal Server
    ↓ WebSocket message
TtydWebSocketClient._handle_message()
    ↓ 解析 ttyd 协议
    ├─ command = raw_data[0]
    └─ raw_message = raw_data[1:]
    ↓ Message receive
ConnectionManager._dispatch_message(raw_message)
    ↓ 事件分发（raw_message）
CommandExecutor._handle_raw_message(raw_message)
    ├─ 活跃性检测（基于raw_message）
    ├─ 完成检测（基于raw_message）
    └─ execution_time 注入（COMPLETE类型时）
    ↓ raw_message
MessageProcessor.process_raw_message(raw_message)
    ├─ QCLI 分支:
    │   ├─ ansi_formatter.parse_terminal_output() → (clean_content, ChunkType)
    │   └─ _build_qcli_metadata() → metadata
    ├─ Generic 分支:
    │   ├─ ansi_formatter.parse_terminal_output() → (clean_content, ChunkType)
    │   ├─ _remove_command_echo() → clean_content
    │   └─ _build_generic_metadata() → metadata
    └─ 构建 StreamChunk:
        ├─ clean_content (处理后的内容)
        ├─ ChunkType (消息类型)
        ├─ metadata (元数据，包含execution_time)
        └─ timestamp
    ↓ Process results
TerminalAPIClient.stream_handler(StreamChunk)
    ↓ StreamChunk.to_api_format() - 延迟转换
Gradio WebUI 显示结果
```

## 核心数据结构

### 1. 统一数据结构定义

```python
@dataclass
class StreamChunk:
    """统一的流式数据块"""
    content: str                    # 处理后的内容
    type: ChunkType                # 数据块类型
    metadata: Dict[str, Any]       # 元数据
    timestamp: float               # 时间戳
    
    def to_api_format(self) -> Dict[str, Any]:
        """转换为API输出格式"""
        return {
            "content": self.content,
            "type": self.type.value,
            "metadata": self.metadata,
            "timestamp": self.timestamp
        }

class ChunkType(Enum):
    """统一的数据块类型 - 语义明确，调用方可根据类型决定展示策略"""
    THINKING = "thinking"      # AI思考中 - 通常显示思考指示器
    TOOL_USE = "tool_use"      # 工具使用 - 可显示工具信息
    CONTENT = "content"        # 文本内容输出 - 应该显示给用户
    PENDING = "pending"        # 等待输入 - 可显示等待提示
    COMPLETE = "complete"      # 完成 - 可显示完成信息
    ERROR = "error"           # 错误 - 应该显示错误信息

class TerminalType(Enum):
    """终端类型 - 统一定义"""
    GENERIC = "generic"
    QCLI = "qcli"

class MetadataBuilder:
    """元数据构建器 - 为不同类型的消息构建相应的元数据"""
    
    @staticmethod
    def for_thinking(raw_length: int, terminal_type: str) -> Dict[str, Any]:
        """思考状态的元数据"""
        return {
            "raw_length": raw_length,
            "terminal_type": terminal_type
        }
    
    @staticmethod
    def for_tool_use(tool_name: str, raw_length: int, terminal_type: str) -> Dict[str, Any]:
        """工具使用的元数据"""
        return {
            "tool_name": tool_name,
            "raw_length": raw_length,
            "terminal_type": terminal_type
        }
    
    @staticmethod
    def for_content(raw_length: int, content_length: int, terminal_type: str) -> Dict[str, Any]:
        """内容输出的元数据"""
        return {
            "raw_length": raw_length,
            "content_length": content_length,
            "terminal_type": terminal_type
        }
    
    @staticmethod
    def for_error(error_message: str, terminal_type: str, error_type: str = "execution_error") -> Dict[str, Any]:
        """错误状态的元数据"""
        return {
            "error_message": error_message,
            "error_type": error_type,
            "terminal_type": terminal_type
        }
    
    @staticmethod
    def for_pending(terminal_type: str, prompt_text: str = "") -> Dict[str, Any]:
        """等待状态的元数据"""
        return {
            "terminal_type": terminal_type,
            "prompt_text": prompt_text
        }
```

## 分层职责详细设计

### 第1层：TtydWebSocketClient - 协议实现层

**核心职责**：
- WebSocket连接生命周期管理
- ttyd协议消息解析和封装
- HTTP基本认证处理
- 连接状态管理（使用State枚举）
- 连接状态监控和异常处理

**实现逻辑**：
```
连接建立流程:
  建立WebSocket连接 → HTTP认证 → ttyd协议握手 → 连接就绪

消息处理流程:
  接收原始数据 → 解析ttyd协议 → 提取消息内容 → 分发给上层

状态检查机制:
  使用现代WebSocket API检查连接状态
  支持连接断开检测和自动重连
```

**关键特性**：
- 使用websockets 15.x现代API (ClientConnection + State枚举)
- 支持异步消息监听和事件驱动处理
- 提供连接状态变化回调机制

### 第2层：ConnectionManager - 连接管理层

**核心职责**：
- 管理WebSocket客户端实例
- 事件驱动的消息分发
- 连接状态到业务状态的映射
- 连接异常处理和恢复

**实现逻辑**：
```
消息分发机制:
  接收原始消息 → 分发给主处理器 → 同时通知临时监听器

状态映射逻辑:
  WebSocket状态变化 → 触发业务状态更新 → 通知上层组件

连接管理流程:
  初始化连接 → 监控连接状态 → 处理异常 → 必要时重连
```

**设计原则**：
- 纯粹的消息路由，不做数据转换
- 事件驱动架构，松耦合设计
- 统一的错误处理和状态管理

### 第3层：Processing Layer - 数据处理层

#### CommandExecutor - 命令执行管理

**核心职责**：
- 命令生命周期管理
- 活跃性检测和超时控制
- 命令完成检测
- 执行时间统计和注入

**实现逻辑**：
```
命令执行流程:
  接收命令 → 创建执行上下文 → 发送到终端 → 监控执行状态

活跃性检测:
  每收到消息 → 更新活跃时间戳 → 检查是否超时

完成检测:
  接收消息 → 委托MessageProcessor处理 → 检查返回类型 → 
  如果是COMPLETE类型 → 注入执行时间 → 设置完成事件

执行时间注入:
  检测到完成信号 → 计算执行时间 → 注入到metadata → 标记成功状态
```

**设计特点**：
- 无状态设计，每次执行创建新的执行上下文
- 优雅的后处理机制，不修改MessageProcessor接口
- 统一的StreamChunk回调接口

#### MessageProcessor - 统一数据处理

**核心职责**：
- 原始消息清理和格式化
- 消息类型识别和分类
- 统一数据结构构建
- 终端类型特定处理

**实现逻辑**：
```
统一处理入口:
  接收原始消息 → 根据终端类型选择处理分支 → 返回StreamChunk

QCLI处理分支:
  ANSI序列解析 → 消息类型检测 → 内容清理 → 构建metadata

Generic处理分支:
  ANSI序列解析 → 完成信号检测 → 命令回显移除 → 构建metadata

错误处理机制:
  捕获处理异常 → 创建错误StreamChunk → 记录日志 → 返回错误信息
```

**核心算法**：
- 使用统一的ANSI解析器处理所有终端类型
- 基于真实ttyd数据的OSC 697序列完成检测
- 延迟转换原则，只在最后构建StreamChunk
        
        # 4. 返回统一格式
        return StreamChunk(
            content=clean_content,
            type=chunk_type,
            metadata=metadata,
            timestamp=time.time()
        )
```

### 第4层：TerminalAPIClient - 业务协调层

**核心职责**：
- 组件生命周期协调
- 业务状态管理
- 用户接口提供
- API格式转换

**实现逻辑**：
```
组件协调:
  初始化各组件 → 建立依赖关系 → 设置回调链 → 启动服务

状态管理:
  INITIALIZING → IDLE → BUSY → IDLE (循环)
  连接状态变化 → 自动映射业务状态 → 通知用户

流式执行:
  设置StreamChunk回调 → 启动命令执行 → 收集输出块 → 
  转换API格式 → 流式返回给用户

错误处理:
  捕获各层异常 → 统一错误格式 → 状态恢复 → 用户通知
```

**设计优势**：
- 延迟转换：只在最后一步转换为API格式
- 统一接口：对外提供一致的API体验
- 状态感知：完整的业务状态管理和映射

## 层间交互模式

### 数据流向
```
用户请求 → TerminalAPIClient → CommandExecutor → ConnectionManager → TtydWebSocketClient
                    ↓                    ↓              ↓               ↓
                StreamChunk ← MessageProcessor ← 原始消息分发 ← ttyd协议解析
```

### 回调链设计
```
TtydWebSocketClient.message_handler → ConnectionManager.dispatch_message →
CommandExecutor.handle_raw_message → MessageProcessor.process_raw_message →
CommandExecutor.stream_callback → TerminalAPIClient.stream_handler
```

### 状态传播
```
WebSocket状态 → 连接状态 → 业务状态 → 用户可见状态
```

## 流式输出格式

### 统一的API输出格式

```json
{
  "content": "Hello! I'm Amazon Q...",
  "type": "content",
  "metadata": {
    "terminal_type": "qcli",
    "raw_length": 156,
    "content_length": 23,
    "execution_time": 4.09,
    "command_success": true
  },
  "timestamp": 1704067200.123
}
```

### 消息类型说明

| 类型 | 描述 | 元数据字段 | 用途 |
|------|------|------------|------|
| `thinking` | AI 思考中 | `raw_length`, `terminal_type` | 显示思考指示器 |
| `tool_use` | 使用工具中 | `tool_name`, `raw_length`, `terminal_type` | 显示工具信息 |
| `content` | 文本内容输出 | `raw_length`, `content_length`, `terminal_type` | 显示给用户的内容 |
| `pending` | 等待用户输入 | `terminal_type`, `prompt_text` | 显示等待提示 |
| `complete` | 回复完成 | `execution_time`, `command_success`, `terminal_type` | 显示完成信息 |
| `error` | 执行错误 | `error_message`, `error_type`, `terminal_type` | 显示错误信息 |
