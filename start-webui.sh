#!/bin/bash

# Terminal API MVP - 修正版Gradio WebUI 启动脚本

echo "🎯 Terminal API MVP - Gradio WebUI"
echo "================================="
echo

# 检查uv
echo "🔍 检查环境依赖..."

if ! command -v uv &> /dev/null; then
    echo "❌ uv 未安装，请先安装 uv"
    echo "安装命令: curl -LsSf https://astral.sh/uv/install.sh | sh"
    exit 1
fi

echo "✅ uv 已安装"

# 检查Terminal API服务状态
echo "🔍 检查Terminal API服务..."
if curl -u demo:password123 http://localhost:7681 -I -s > /dev/null 2>&1; then
    echo "✅ Terminal API服务运行正常"
else
    echo "⚠️  Terminal API服务未运行，正在启动..."
    ./ttyd/ttyd-service.sh start bash 7681
    if [ $? -eq 0 ]; then
        echo "✅ Terminal API服务启动成功"
    else
        echo "❌ Terminal API服务启动失败"
        echo "请手动启动: ./ttyd/ttyd-service.sh start [type]"
    fi
fi

# 切换到项目目录
cd "$(dirname "$0")"

# 使用uv运行Gradio应用
PYTHONPATH=. uv run python webui/gradio_chat.py

echo
echo "🚀 使用uv启动Gradio WebUI..."
echo "访问地址: http://localhost:7860"
echo "Terminal API: http://localhost:7681"
echo
echo "✨ 功能特性:"
echo "- 智能命令解析和执行"
echo "- 实时流式输出显示"
echo "- stdout/stderr 区分显示"
echo "- 可折叠的手风琴界面"
echo "- 执行状态和时间统计"
echo
echo "按 Ctrl+C 停止服务"
echo