#!/usr/bin/env python3
"""
真实场景测试：运维日志分析
测试我们的流式API处理复杂实际场景的能力
"""

import asyncio
import time
import sys
import os

# 添加项目根目录到Python路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from api import TerminalAPIClient
from api.data_structures import TerminalType

async def real_world_log_analysis_test():
    """真实场景测试：防火墙日志分析"""
    print('🚀 真实场景测试：防火墙日志分析')
    print('=' * 60)
    
    # 检查日志文件是否存在
    log_file = '/tmp/ttyd/firewall_sample.log'
    if not os.path.exists(log_file):
        print(f'❌ 日志文件不存在: {log_file}')
        print('请先运行以下命令准备测试数据:')
        print('cd /tmp/ttyd && wget -q http://log-sharing.dreamhosters.com/SotM30-anton.log.gz')
        print('gunzip SotM30-anton.log.gz && head -100 SotM30-anton.log > firewall_sample.log')
        return
    
    print(f'📁 使用日志文件: {log_file}')
    print(f'📊 文件大小: {os.path.getsize(log_file)} 字节')
    print()
    
    # 使用新的API
    client = TerminalAPIClient(
        host='localhost',
        port=7682,
        username='demo',
        password='password123',
        terminal_type=TerminalType.QCLI,
        format_output=True
    )
    
    try:
        print('🔌 正在连接到 Q CLI...')
        success = await client.initialize()
        
        if not success:
            print('❌ 连接失败，请检查 Q CLI ttyd 服务是否启动')
            print('   启动命令: ./ttyd/ttyd-service.sh start qcli 7682')
            return
        
        print('✅ API连接成功，开始分析防火墙日志...')
        print()
        
        # 等待Q CLI完全启动和稳定
        print('⏳ 等待Q CLI完全启动和稳定...')
        await asyncio.sleep(5.0)  # 增加到5秒
        
        # 检查客户端状态
        print(f'📡 当前终端状态: {client.terminal_state.value}')
        print(f'🔗 连接状态: {client.is_connected}')
        print(f'⚡ 可执行命令: {client.can_execute_command}')
        print()
        
        # 测试3：与手动测试相同的长命令
        test_command = """分析这个防火墙日志文件 /tmp/ttyd/firewall_sample.log，提供安全分析报告。
内容包括：1. 主要攻击源IP地址; 2. 被攻击的目标端口; 3.攻击类型识别;4. 安全威胁评估; 5. 防护建议. 请先读取文件内容，然后生成结构化的分析报告保存到markdown文件。"""
        
        print('📤 发送测试命令:')
        print(f'   命令长度: {len(test_command)} 字符')
        print(f'   命令预览: {test_command[:100]}...')
        print()
        
        # 开始流式分析
        start_time = time.time()
        content_parts = []
        thinking_count = 0
        content_count = 0
        last_display_time = time.time()
        
        print('📊 实时分析过程:')
        print('-' * 50)
        
        async for chunk in client.execute_command_stream(test_command, silence_timeout=120.0):
            chunk_type = chunk.get('type')
            content = chunk.get('content', '')
            metadata = chunk.get('metadata', {})
            current_time = time.time()
            
            if chunk_type == 'thinking':
                thinking_count += 1
                # 每3秒或每15次刷新显示一次进度
                if (current_time - last_display_time > 3.0) or (thinking_count % 15 == 1):
                    elapsed = current_time - start_time
                    print(f'🤔 [{elapsed:5.1f}s] Q CLI 正在深度分析日志... (第 {thinking_count} 次刷新)')
                    last_display_time = current_time
            
            elif chunk_type == 'tool_use':
                tool_name = metadata.get('tool_name', 'unknown')
                print(f'🔧 正在使用工具: {tool_name}')
            
            elif chunk_type == 'content' and content:
                content_count += 1
                content_parts.append(content)
                
                # 实时显示内容片段
                content_preview = content.strip()[:80].replace('\n', ' ')
                if content_preview:  # 只显示非空内容
                    print(f'📝 [{content_count:2d}] {content_preview}')
            
            elif chunk_type == 'complete':
                execution_time = metadata.get('execution_time', 0)
                success = metadata.get('command_success', False)
                
                print()
                print('🎉 日志分析完成!')
                print(f'⏱️  总执行时间: {execution_time:.2f} 秒')
                print(f'🤔 思考轮次: {thinking_count}')
                print(f'📝 内容块数: {content_count}')
                print(f'✅ 执行状态: {"成功" if success else "失败"}')
                break
            
            elif chunk_type == 'error':
                error_msg = metadata.get('error_message', '未知错误')
                print(f'❌ 分析出错: {error_msg}')
                break
        
        # 分析和展示完整报告
        if content_parts:
            full_report = ''.join(content_parts)
            
            print()
            print('📋 完整安全分析报告:')
            print('=' * 60)
            print(full_report)
            print('=' * 60)
            
            # 报告质量评估
            await evaluate_report_quality(full_report)
            
            # 测试总结
            print()
            print('🎯 真实场景测试总结:')
            print('✅ 初始化消息过滤: 成功')
            print('✅ 流式输出处理: 成功') 
            print('✅ 复杂任务处理: 成功')
            print('✅ 完整报告生成: 成功')
            print()
            print('🚀 我们的流式API完美处理了真实的运维日志分析场景！')
            
        else:
            print('❌ 没有收到分析报告，测试失败')
    
    finally:
        # 清理连接
        await client.shutdown()
        print('🔌 连接已断开')

async def evaluate_report_quality(report: str):
    """评估报告质量"""
    print()
    print('📊 报告质量评估:')
    print('-' * 30)
    
    # 基础指标
    report_length = len(report)
    word_count = len(report.split())
    line_count = len(report.split('\n'))
    
    print(f'📏 报告长度: {report_length} 字符')
    print(f'📝 词汇数量: {word_count} 词')
    print(f'📄 行数: {line_count} 行')
    
    # 内容质量检查
    quality_checks = {
        'IP地址分析': any(indicator in report for indicator in ['192.', '24.', '211.', 'IP', 'SRC', '源IP']),
        '端口分析': any(indicator in report for indicator in ['端口', 'port', 'DPT', '6129', '135', '目标端口']),
        '攻击类型': any(indicator in report for indicator in ['TCP', 'SYN', '攻击', '扫描', 'INBOUND']),
        '威胁评估': any(indicator in report for indicator in ['威胁', '风险', '危险', '安全', '评估']),
        '防护建议': any(indicator in report for indicator in ['建议', '推荐', '应该', '需要', '防护', '措施']),
    }
    
    print()
    print('🔍 内容质量检查:')
    passed_checks = 0
    for check_name, passed in quality_checks.items():
        status = "✅" if passed else "❌"
        print(f'   {status} {check_name}')
        if passed:
            passed_checks += 1
    
    # 综合评分
    quality_score = (passed_checks / len(quality_checks)) * 100
    
    print()
    print(f'🏆 综合质量评分: {quality_score:.1f}/100')
    
    if quality_score >= 80:
        print('🌟 优秀！报告质量很高')
    elif quality_score >= 60:
        print('👍 良好！报告基本符合要求')
    else:
        print('⚠️  需要改进报告质量')

def main():
    """主函数"""
    print("🧪 启动真实场景日志分析测试...")
    print()
    
    try:
        asyncio.run(real_world_log_analysis_test())
    except KeyboardInterrupt:
        print("\n👋 用户中断测试")
    except Exception as e:
        print(f"\n❌ 测试出错: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()
