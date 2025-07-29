#!/bin/bash

# Terminal API MVP - Gotty 服务管理脚本
# 使用方法: ./gotty-service.sh {start|stop|restart|status} [terminal_type] [port]

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
GOTTY_BIN=$(which gotty 2>/dev/null || echo "gotty")
Q_CLI_BIN=$(which q 2>/dev/null || echo "q")
PID_DIR="$PROJECT_ROOT/pids"
LOG_DIR="$PROJECT_ROOT/logs"

# 创建必要目录
mkdir -p "$PID_DIR" "$LOG_DIR"

# 默认配置
DEFAULT_TERMINAL="qcli"
DEFAULT_PORT="8080"
DEFAULT_USER="demo"
DEFAULT_PASS="password123"

# 颜色输出
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

log() {
    echo -e "${BLUE}[$(date '+%Y-%m-%d %H:%M:%S')]${NC} $1"
}

success() {
    echo -e "${GREEN}✅ $1${NC}"
}

warning() {
    echo -e "${YELLOW}⚠️  $1${NC}"
}

error() {
    echo -e "${RED}❌ $1${NC}"
}

# 获取PID文件路径
get_pid_file() {
    local terminal_type=${1:-$DEFAULT_TERMINAL}
    local port=${2:-$DEFAULT_PORT}
    echo "$PID_DIR/gotty-${terminal_type}-${port}.pid"
}

# 获取日志文件路径
get_log_file() {
    local terminal_type=${1:-$DEFAULT_TERMINAL}
    local port=${2:-$DEFAULT_PORT}
    echo "$LOG_DIR/gotty-${terminal_type}-${port}.log"
}

# 检查服务是否运行
is_running() {
    local pid_file=$(get_pid_file "$1" "$2")
    if [ -f "$pid_file" ]; then
        local pid=$(cat "$pid_file")
        if kill -0 "$pid" 2>/dev/null; then
            return 0
        else
            rm -f "$pid_file"
            return 1
        fi
    fi
    return 1
}

# 健康检查函数
health_check() {
    local terminal_type=${1:-$DEFAULT_TERMINAL}
    local port=${2:-$DEFAULT_PORT}
    local max_attempts=3
    local attempt=0
    
    log "执行健康检查 (${terminal_type}:${port})..."
    
    while [ $attempt -lt $max_attempts ]; do
        if curl -u "$DEFAULT_USER:$DEFAULT_PASS" "http://localhost:$port" -I -s > /dev/null 2>&1; then
            success "健康检查通过 (尝试 $((attempt + 1))/$max_attempts)"
            return 0
        fi
        
        attempt=$((attempt + 1))
        if [ $attempt -lt $max_attempts ]; then
            log "健康检查失败，等待重试... ($attempt/$max_attempts)"
            sleep 2
        fi
    done
    
    warning "健康检查失败，服务可能未正常启动"
    return 1
}

# 启动服务
start_service() {
    local terminal_type=${1:-$DEFAULT_TERMINAL}
    local port=${2:-$DEFAULT_PORT}
    local pid_file=$(get_pid_file "$terminal_type" "$port")
    local log_file=$(get_log_file "$terminal_type" "$port")
    
    if is_running "$terminal_type" "$port"; then
        warning "服务已在运行 (${terminal_type}:${port})"
        return 1
    fi
    
    log "启动 $terminal_type 终端服务 (端口: $port)..."
    
    # 检查gotty二进制文件
    if ! command -v "$GOTTY_BIN" &> /dev/null; then
        error "未找到gotty二进制文件: $GOTTY_BIN"
        error "请安装gotty: https://github.com/yudai/gotty"
        return 1
    fi
    
    # 检查端口是否被占用
    if ss -tlnp | grep ":$port " > /dev/null 2>&1; then
        error "端口 $port 已被占用"
        return 1
    fi
    
    # 根据终端类型设置命令
    local command
    case $terminal_type in
        "bash")
            command="bash"
            ;;
        "qcli")
            # 检查Q CLI是否可用
            if ! command -v "$Q_CLI_BIN" &> /dev/null; then
                error "未找到Q CLI二进制文件: $Q_CLI_BIN"
                error "请确保Q CLI已正确安装并在PATH中"
                return 1
            fi
            
            # 测试Q CLI是否正常工作
            if ! "$Q_CLI_BIN" --version &> /dev/null; then
                warning "Q CLI版本检查失败，但继续尝试启动..."
            fi
            
            command="$Q_CLI_BIN chat"
            ;;
        "python"|"python3")
            command="python3"
            ;;
        "mysql")
            if ! command -v mysql &> /dev/null; then
                warning "MySQL客户端未安装，正在安装..."
                sudo apt-get update && sudo apt-get install -y mysql-client
            fi
            command="mysql --help"
            ;;
        "redis")
            if ! command -v redis-cli &> /dev/null; then
                warning "Redis客户端未安装，正在安装..."
                sudo apt-get update && sudo apt-get install -y redis-tools
            fi
            command="redis-cli"
            ;;
        *)
            command="$terminal_type"
            ;;
    esac
    
    # 启动gotty服务
    nohup "$GOTTY_BIN" \
        --permit-write \
        --credential "$DEFAULT_USER:$DEFAULT_PASS" \
        --port "$port" \
        --title-format "Terminal API MVP - $terminal_type" \
        --max-connection 10 \
        --timeout 300 \
        --reconnect \
        $command > "$log_file" 2>&1 &
    
    local pid=$!
    echo $pid > "$pid_file"
    
    # 等待服务启动
    sleep 3
    
    if is_running "$terminal_type" "$port"; then
        success "服务启动成功 (PID: $pid)"
        log "访问地址: http://localhost:$port"
        log "用户名: $DEFAULT_USER"
        log "密码: $DEFAULT_PASS"
        log "日志文件: $log_file"
        
        # 执行健康检查
        if health_check "$terminal_type" "$port"; then
            success "服务健康检查通过"
        else
            warning "服务健康检查失败，但服务已启动"
        fi
        
        return 0
    else
        error "服务启动失败"
        log "查看日志: cat $log_file"
        return 1
    fi
}

# 停止服务
stop_service() {
    local terminal_type=${1:-$DEFAULT_TERMINAL}
    local port=${2:-$DEFAULT_PORT}
    local pid_file=$(get_pid_file "$terminal_type" "$port")
    
    if ! is_running "$terminal_type" "$port"; then
        warning "服务未运行 (${terminal_type}:${port})"
        return 1
    fi
    
    local pid=$(cat "$pid_file")
    log "停止服务 (PID: $pid)..."
    
    # 优雅停止
    kill "$pid" 2>/dev/null
    
    # 等待进程结束
    local count=0
    while kill -0 "$pid" 2>/dev/null && [ $count -lt 10 ]; do
        sleep 1
        count=$((count + 1))
    done
    
    # 强制停止
    if kill -0 "$pid" 2>/dev/null; then
        warning "强制停止服务..."
        kill -9 "$pid" 2>/dev/null
    fi
    
    rm -f "$pid_file"
    success "服务已停止"
    return 0
}

# 重启服务
restart_service() {
    local terminal_type=${1:-$DEFAULT_TERMINAL}
    local port=${2:-$DEFAULT_PORT}
    
    log "重启服务 (${terminal_type}:${port})..."
    stop_service "$terminal_type" "$port"
    sleep 2
    start_service "$terminal_type" "$port"
}

# 显示服务状态
show_status() {
    local terminal_type=${1:-$DEFAULT_TERMINAL}
    local port=${2:-$DEFAULT_PORT}
    
    echo "=== Terminal API MVP 服务状态 ==="
    
    if [ -n "$terminal_type" ] && [ "$terminal_type" != "all" ]; then
        # 显示特定服务状态
        local pid_file=$(get_pid_file "$terminal_type" "$port")
        local log_file=$(get_log_file "$terminal_type" "$port")
        
        echo "服务: $terminal_type"
        echo "端口: $port"
        echo "PID文件: $pid_file"
        echo "日志文件: $log_file"
        
        if is_running "$terminal_type" "$port"; then
            local pid=$(cat "$pid_file")
            success "运行中 (PID: $pid)"
            
            # 显示连接测试
            if curl -u "$DEFAULT_USER:$DEFAULT_PASS" "http://localhost:$port" -I -s > /dev/null 2>&1; then
                success "连接正常"
            else
                warning "连接异常"
            fi
        else
            error "未运行"
        fi
    else
        # 显示所有服务状态
        echo "扫描所有运行的gotty服务..."
        
        local found=false
        for pid_file in "$PID_DIR"/gotty-*.pid; do
            if [ -f "$pid_file" ]; then
                local basename=$(basename "$pid_file" .pid)
                local service_info=${basename#gotty-}
                local terminal_type=${service_info%-*}
                local port=${service_info##*-}
                
                echo
                echo "服务: $terminal_type (端口: $port)"
                
                if is_running "$terminal_type" "$port"; then
                    local pid=$(cat "$pid_file")
                    success "运行中 (PID: $pid)"
                else
                    error "未运行"
                fi
                found=true
            fi
        done
        
        if [ "$found" = false ]; then
            warning "未找到运行的服务"
        fi
    fi
    
    echo
    echo "=== 系统进程 ==="
    ps aux | grep gotty | grep -v grep || echo "无gotty进程"
}

# 停止所有服务
stop_all() {
    log "停止所有gotty服务..."
    
    # 停止PID文件记录的服务
    for pid_file in "$PID_DIR"/gotty-*.pid; do
        if [ -f "$pid_file" ]; then
            local basename=$(basename "$pid_file" .pid)
            local service_info=${basename#gotty-}
            local terminal_type=${service_info%-*}
            local port=${service_info##*-}
            stop_service "$terminal_type" "$port"
        fi
    done
    
    # 清理遗留进程
    pkill -f gotty 2>/dev/null || true
    
    success "所有服务已停止"
}

# 显示帮助信息
show_help() {
    echo "Terminal API MVP - Gotty 服务管理脚本"
    echo
    echo "使用方法:"
    echo "  $0 {start|stop|restart|status} [terminal_type] [port]"
    echo "  $0 stop-all"
    echo
    echo "命令:"
    echo "  start     启动服务"
    echo "  stop      停止服务"
    echo "  restart   重启服务"
    echo "  status    显示服务状态"
    echo "  stop-all  停止所有服务"
    echo
    echo "参数:"
    echo "  terminal_type  终端类型 (默认: qcli)"
    echo "                 支持: qcli, bash, python, mysql, redis, htop"
    echo "  port          端口号 (默认: 8080)"
    echo
    echo "示例:"
    echo "  $0 start                    # 启动默认Q CLI终端 (端口8080)"
    echo "  $0 start qcli 8081          # 启动Q CLI (端口8081)"
    echo "  $0 start python 8082        # 启动Python REPL (端口8082)"
    echo "  $0 stop qcli 8080           # 停止Q CLI终端"
    echo "  $0 restart qcli 8081        # 重启Q CLI"
    echo "  $0 status                   # 显示所有服务状态"
    echo "  $0 status qcli 8080         # 显示特定服务状态"
    echo "  $0 stop-all                 # 停止所有服务"
    echo
    echo "默认认证信息:"
    echo "  用户名: $DEFAULT_USER"
    echo "  密码: $DEFAULT_PASS"
}

# 主函数
main() {
    local action=${1:-start}  # 默认动作改为start
    local terminal_type=$2
    local port=$3
    
    # 如果没有提供任何参数，显示快速启动信息
    if [ $# -eq 0 ]; then
        echo "🎯 Terminal API MVP - 快速启动"
        echo "=============================="
        echo
        start_service "$DEFAULT_TERMINAL" "$DEFAULT_PORT"
        if [ $? -eq 0 ]; then
            echo
            echo "💡 更多命令:"
            echo "./gotty-service.sh status          # 查看服务状态"
            echo "./gotty-service.sh start python 8081  # 启动Python REPL"
            echo "./gotty-service.sh stop-all        # 停止所有服务"
            echo "./gotty-service.sh help            # 查看完整帮助"
        fi
        return
    fi
    
    case $action in
        "start")
            start_service "$terminal_type" "$port"
            ;;
        "stop")
            stop_service "$terminal_type" "$port"
            ;;
        "restart")
            restart_service "$terminal_type" "$port"
            ;;
        "status")
            show_status "$terminal_type" "$port"
            ;;
        "stop-all")
            stop_all
            ;;
        "help"|"-h"|"--help")
            show_help
            ;;
        *)
            error "未知命令: $action"
            echo
            show_help
            exit 1
            ;;
    esac
}

# 执行主函数
main "$@"
