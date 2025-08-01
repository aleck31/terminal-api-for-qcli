#!/bin/bash

# TTYD Service Management Script
# 支持从 conf.ini 加载配置
# 使用方法: ./ttyd-service.sh {start|stop|restart|status|help} [terminal_type] [port]

# 脚本目录和项目根目录
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
CONFIG_FILE="$SCRIPT_DIR/conf.ini"

# 颜色输出
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

# 日志函数
log() { echo -e "${BLUE}[$(date '+%H:%M:%S')]${NC} $1"; }
success() { echo -e "${GREEN}✅ $1${NC}"; }
warning() { echo -e "${YELLOW}⚠️  $1${NC}"; }
error() { echo -e "${RED}❌ $1${NC}"; }

# 默认配置（如果配置文件不存在）
declare -A CONFIG=(
    [port]=7681
    [credential]="demo:password123"
    [permit_write]=true
    [max_clients]=10
    [timeout]=300
    [terminal_type]="xterm-256color"
    [title_format]="Terminal API - {terminal}"
    [check_origin]=false
    [once]=false
    [readonly]=false
    [ping_interval]=30
    [reconnect]=true
    [ipv6]=false
    [ssl]=false
    [debug_level]=7
    [work_dir]="/tmp/ttyd"
    [default_terminal]="bash"
    [qcli_command]="q chat"
    [python_command]="python3"
    [bash_command]="bash"
    [pid_dir]="pids"
    [log_dir]="logs"
    [health_check_timeout]=10
    [startup_wait]=3
)

# 加载配置文件
load_config() {
    if [[ -f "$CONFIG_FILE" ]]; then
        # 静默加载配置文件，不显示日志
        while IFS='=' read -r key value; do
            # 跳过注释和空行
            [[ $key =~ ^[[:space:]]*# ]] && continue
            [[ -z $key ]] && continue
            
            # 清理键值对
            key=$(echo "$key" | xargs)
            value=$(echo "$value" | xargs)
            
            # 移除引号
            value="${value%\"}"
            value="${value#\"}"
            
            if [[ -n $key && -n $value ]]; then
                CONFIG[$key]="$value"
            fi
        done < "$CONFIG_FILE"
    fi
}

# 获取配置值
get_config() {
    local key="$1"
    local default="${2:-}"
    echo "${CONFIG[$key]:-$default}"
}

# 创建必要目录
setup_directories() {
    local pid_dir="$PROJECT_ROOT/$(get_config pid_dir)"
    local log_dir="$PROJECT_ROOT/$(get_config log_dir)"
    local work_dir="$(get_config work_dir)"
    
    mkdir -p "$pid_dir" "$log_dir" "$work_dir"
}

# 获取文件路径
get_pid_file() {
    local terminal_type="${1:-$(get_config default_terminal)}"
    local port="${2:-$(get_config port)}"
    local pid_dir="$PROJECT_ROOT/$(get_config pid_dir)"
    echo "$pid_dir/ttyd-${terminal_type}-${port}.pid"
}

get_log_file() {
    local terminal_type="${1:-$(get_config default_terminal)}"
    local port="${2:-$(get_config port)}"
    local log_dir="$PROJECT_ROOT/$(get_config log_dir)"
    echo "$log_dir/ttyd-${terminal_type}-${port}.log"
}

# 检查服务是否运行
is_running() {
    local terminal_type="${1:-$(get_config default_terminal)}"
    local port="${2:-$(get_config port)}"
    local pid_file=$(get_pid_file "$terminal_type" "$port")
    
    if [[ -f "$pid_file" ]]; then
        local pid=$(cat "$pid_file")
        if kill -0 "$pid" 2>/dev/null; then
            return 0
        else
            rm -f "$pid_file"
        fi
    fi
    return 1
}

# 健康检查
health_check() {
    local port="${1:-$(get_config port)}"
    local credential="$(get_config credential)"
    local timeout="$(get_config health_check_timeout)"
    
    log "执行健康检查 (端口: $port)..."
    
    if timeout "$timeout" curl -u "$credential" "http://localhost:$port" -I -s >/dev/null 2>&1; then
        success "健康检查通过"
        return 0
    else
        warning "健康检查失败"
        return 1
    fi
}

# 获取终端命令
get_terminal_command() {
    local terminal_type="$1"
    
    case "$terminal_type" in
        "bash")
            echo "$(get_config bash_command)"
            ;;
        "qcli"|"q")
            local qcli_cmd="$(get_config qcli_command)"
            if ! command -v "$(echo "$qcli_cmd" | cut -d' ' -f1)" >/dev/null 2>&1; then
                error "Q CLI 未找到: $qcli_cmd"
                return 1
            fi
            echo "$qcli_cmd"
            ;;
        "python"|"python3")
            echo "$(get_config python_command)"
            ;;
        *)
            echo "$terminal_type"
            ;;
    esac
}

# 构建 ttyd 命令参数
build_ttyd_args() {
    local terminal_type="$1"
    local port="$2"
    local args=()
    
    # 基本参数（使用短格式）
    args+=(-p "$port")
    args+=(-c "$(get_config credential)")
    
    # 可选参数（使用短格式）
    [[ "$(get_config permit_write)" == "true" ]] && args+=(-W)
    [[ "$(get_config once)" == "true" ]] && args+=(-o)
    [[ "$(get_config check_origin)" == "true" ]] && args+=(-O)
    [[ "$(get_config ipv6)" == "true" ]] && args+=(-6)
    
    # 数值参数（使用短格式）
    args+=(-m "$(get_config max_clients)")
    args+=(-P "$(get_config ping_interval)")
    args+=(-d "$(get_config debug_level)")
    
    # 终端类型
    args+=(-T "$(get_config terminal_type)")
    
    # 标题格式（如果支持的话）
    local title_format="$(get_config title_format)"
    title_format="${title_format/\{terminal\}/$terminal_type}"
    # 注意：ttyd 可能不支持 --title-format，先注释掉
    # args+=(--title-format "$title_format")
    
    # SSL 配置（使用短格式）
    if [[ "$(get_config ssl)" == "true" ]]; then
        local ssl_cert="$(get_config ssl_cert)"
        local ssl_key="$(get_config ssl_key)"
        local ssl_ca="$(get_config ssl_ca)"
        
        args+=(-S)
        [[ -n "$ssl_cert" ]] && args+=(-C "$ssl_cert")
        [[ -n "$ssl_key" ]] && args+=(-K "$ssl_key")
        [[ -n "$ssl_ca" ]] && args+=(-A "$ssl_ca")
    fi
    
    echo "${args[@]}"
}

# 启动服务
start_service() {
    local terminal_type="${1:-$(get_config default_terminal)}"
    local port="${2:-$(get_config port)}"
    
    if is_running "$terminal_type" "$port"; then
        warning "服务已在运行 (${terminal_type}:${port})"
        return 1
    fi
    
    log "启动 $terminal_type 终端服务 (端口: $port)..."
    
    # 检查 ttyd
    if ! command -v ttyd >/dev/null 2>&1; then
        error "未找到 ttyd，请先安装: https://github.com/tsl0922/ttyd"
        return 1
    fi
    
    # 检查端口
    if ss -tlnp 2>/dev/null | grep -q ":$port "; then
        error "端口 $port 已被占用"
        return 1
    fi
    
    # 获取终端命令
    local terminal_cmd
    if ! terminal_cmd=$(get_terminal_command "$terminal_type"); then
        return 1
    fi
    
    # 构建 ttyd 参数
    local ttyd_args
    ttyd_args=$(build_ttyd_args "$terminal_type" "$port")
    
    # 获取文件路径
    local pid_file=$(get_pid_file "$terminal_type" "$port")
    local log_file=$(get_log_file "$terminal_type" "$port")
    
    # 启动服务
    log "执行命令: ttyd $ttyd_args $terminal_cmd"
    
    # shellcheck disable=SC2086
    nohup ttyd $ttyd_args $terminal_cmd >"$log_file" 2>&1 &
    local pid=$!
    echo "$pid" > "$pid_file"
    
    # 等待启动
    local startup_wait="$(get_config startup_wait)"
    log "等待服务启动 (${startup_wait}秒)..."
    sleep "$startup_wait"
    
    if is_running "$terminal_type" "$port"; then
        success "服务启动成功 (PID: $pid)"
        log "访问地址: http://localhost:$port"
        log "认证信息: $(get_config credential)"
        log "日志文件: $log_file"
        
        # 健康检查
        health_check "$port"
        return 0
    else
        error "服务启动失败，查看日志: $log_file"
        return 1
    fi
}

# 停止服务
stop_service() {
    local terminal_type="${1:-$(get_config default_terminal)}"
    local port="${2:-$(get_config port)}"
    local pid_file=$(get_pid_file "$terminal_type" "$port")
    
    if ! is_running "$terminal_type" "$port"; then
        warning "服务未运行 (${terminal_type}:${port})"
        return 1
    fi
    
    local pid=$(cat "$pid_file")
    log "停止服务 (PID: $pid)..."
    
    # 优雅停止
    if kill -TERM "$pid" 2>/dev/null; then
        local count=0
        while kill -0 "$pid" 2>/dev/null && [[ $count -lt 10 ]]; do
            sleep 1
            ((count++))
        done
        
        # 强制停止
        if kill -0 "$pid" 2>/dev/null; then
            warning "优雅停止失败，强制停止..."
            kill -KILL "$pid" 2>/dev/null || true
        fi
    fi
    
    rm -f "$pid_file"
    success "服务已停止"
}

# 重启服务
restart_service() {
    local terminal_type="${1:-$(get_config default_terminal)}"
    local port="${2:-$(get_config port)}"
    
    log "重启服务 (${terminal_type}:${port})..."
    stop_service "$terminal_type" "$port" || true
    sleep 2
    start_service "$terminal_type" "$port"
}

# 查看状态
show_status() {
    local terminal_type="${1:-$(get_config default_terminal)}"
    local port="${2:-$(get_config port)}"
    
    echo "=== TTYD 服务状态 ==="
    echo "终端类型: $terminal_type"
    echo "端口: $port"
    
    if is_running "$terminal_type" "$port"; then
        local pid_file=$(get_pid_file "$terminal_type" "$port")
        local pid=$(cat "$pid_file")
        success "服务运行中 (PID: $pid)"
        
        echo "访问地址: http://localhost:$port"
        echo "认证信息: $(get_config credential)"
        echo "日志文件: $(get_log_file "$terminal_type" "$port")"
    else
        warning "服务未运行"
    fi
}

# 停止所有服务
stop_all() {
    local pid_dir="$PROJECT_ROOT/$(get_config pid_dir)"
    local stopped=0
    
    log "停止所有 ttyd 服务..."
    
    for pid_file in "$pid_dir"/ttyd-*.pid; do
        [[ -f "$pid_file" ]] || continue
        
        local basename=$(basename "$pid_file" .pid)
        local terminal_type=$(echo "$basename" | cut -d'-' -f2)
        local port=$(echo "$basename" | cut -d'-' -f3)
        
        if is_running "$terminal_type" "$port"; then
            stop_service "$terminal_type" "$port"
            ((stopped++))
        fi
    done
    
    if [[ $stopped -eq 0 ]]; then
        warning "没有运行中的服务"
    else
        success "已停止 $stopped 个服务"
    fi
}

# 显示帮助
show_help() {
    cat << 'EOF'
TTYD Service Management Script

用法:
  ./ttyd-service.sh <command> [terminal_type] [port]

命令:
  start [type] [port]  - 启动服务
  stop [type] [port]   - 停止服务  
  restart [type] [port] - 重启服务
  status [type] [port] - 查看状态
  stop-all            - 停止所有服务
  help                - 显示帮助

终端类型:
  bash    - Bash Shell (默认)
  qcli    - Q CLI
  python  - Python REPL

示例:
  ./ttyd-service.sh start           # 启动默认服务 (bash:7681)
  ./ttyd-service.sh start qcli      # 启动 Q CLI (端口 7681)
  ./ttyd-service.sh start bash 8080 # 启动 Bash (端口 8080)
  ./ttyd-service.sh stop            # 停止默认服务
  ./ttyd-service.sh status          # 查看默认服务状态
  ./ttyd-service.sh stop-all        # 停止所有服务

配置文件: ttyd/conf.ini
日志目录: logs/
PID目录:  pids/
EOF
}

# 主函数
main() {
    # 加载配置
    load_config
    
    # 创建目录
    setup_directories
    
    # 解析参数
    local command="${1:-help}"
    local terminal_type="${2:-}"
    local port="${3:-}"
    
    case "$command" in
        start)
            start_service "$terminal_type" "$port"
            ;;
        stop)
            stop_service "$terminal_type" "$port"
            ;;
        restart)
            restart_service "$terminal_type" "$port"
            ;;
        status)
            show_status "$terminal_type" "$port"
            ;;
        stop-all)
            stop_all
            ;;
        help|--help|-h)
            show_help
            ;;
        *)
            error "未知命令: $command"
            echo
            show_help
            exit 1
            ;;
    esac
}

# 执行主函数
main "$@"
