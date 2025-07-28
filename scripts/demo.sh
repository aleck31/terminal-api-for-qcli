#!/bin/bash

# Terminal API MVP 演示脚本

echo "🎯 Terminal API MVP 演示"
echo "======================="
echo

# 检查gotty是否在运行
if pgrep -f "gotty" > /dev/null; then
    echo "⚠️  检测到gotty正在运行，正在停止..."
    pkill -f gotty
    sleep 2
fi

GOTTY_BIN="../gotty"
BASE_PORT=8080

echo "📋 可用的演示选项:"
echo "1. Bash Shell (端口 8080)"
echo "2. Python REPL (端口 8081)" 
echo "3. 多终端演示 (端口 8080-8083)"
echo "4. 停止所有服务"
echo

read -p "请选择演示选项 (1-4): " choice

case $choice in
    1)
        echo "🚀 启动 Bash Shell 终端..."
        $GOTTY_BIN -w -c demo:password123 -p 8080 bash &
        echo "✅ Bash 终端已启动"
        echo "🌐 访问地址: http://localhost:8080"
        echo "👤 用户名: demo"
        echo "🔑 密码: password123"
        ;;
    2)
        echo "🚀 启动 Python REPL..."
        $GOTTY_BIN -w -c demo:password123 -p 8081 python3 &
        echo "✅ Python REPL 已启动"
        echo "🌐 访问地址: http://localhost:8081"
        echo "👤 用户名: demo"
        echo "🔑 密码: password123"
        ;;
    3)
        echo "🚀 启动多终端演示..."
        
        # Bash
        $GOTTY_BIN -w -c demo:password123 -p 8080 bash &
        echo "✅ Bash 终端启动 (端口 8080)"
        
        # Python
        $GOTTY_BIN -w -c demo:password123 -p 8081 python3 &
        echo "✅ Python REPL 启动 (端口 8081)"
        
        # 系统监控
        $GOTTY_BIN -w -c demo:password123 -p 8082 htop &
        echo "✅ 系统监控启动 (端口 8082)"
        
        # 文件管理
        $GOTTY_BIN -w -c demo:password123 -p 8083 bash -c "cd /home && bash" &
        echo "✅ 文件管理启动 (端口 8083)"
        
        echo
        echo "🌐 访问地址:"
        echo "  - Bash Shell: http://localhost:8080"
        echo "  - Python REPL: http://localhost:8081" 
        echo "  - 系统监控: http://localhost:8082"
        echo "  - 文件管理: http://localhost:8083"
        echo "👤 用户名: demo"
        echo "🔑 密码: password123"
        ;;
    4)
        echo "🛑 停止所有gotty服务..."
        pkill -f gotty
        echo "✅ 所有服务已停止"
        exit 0
        ;;
    *)
        echo "❌ 无效选项"
        exit 1
        ;;
esac

echo
echo "📊 服务状态:"
sleep 2
ps aux | grep gotty | grep -v grep

echo
echo "🧪 测试连接:"
case $choice in
    1)
        curl -u demo:password123 http://localhost:8080 -I -s | head -1
        ;;
    2)
        curl -u demo:password123 http://localhost:8081 -I -s | head -1
        ;;
    3)
        for port in 8080 8081 8082 8083; do
            echo -n "端口 $port: "
            curl -u demo:password123 http://localhost:$port -I -s | head -1
        done
        ;;
esac

echo
echo "💡 提示:"
echo "- 使用 Ctrl+C 停止服务"
echo "- 运行 './demo.sh' 选择选项 4 停止所有服务"
echo "- 查看 web/client.html 获取更好的客户端体验"

# 保持脚本运行
echo
echo "按 Ctrl+C 停止服务..."
trap 'echo "正在停止服务..."; pkill -f gotty; exit 0' INT
while true; do
    sleep 1
done
