#!/usr/bin/env python3
"""
测试运行脚本 - 提供不同的测试运行选项
"""

import subprocess
import sys
import argparse

def run_command(cmd, description):
    """运行命令并显示结果"""
    print(f"\n🚀 {description}")
    print("=" * 50)
    
    try:
        result = subprocess.run(cmd, shell=True, check=True, capture_output=False)
        print(f"✅ {description} 完成")
        return True
    except subprocess.CalledProcessError as e:
        print(f"❌ {description} 失败 (退出码: {e.returncode})")
        return False

def main():
    parser = argparse.ArgumentParser(description="运行测试套件")
    parser.add_argument("--unit", action="store_true", help="只运行单元测试")
    parser.add_argument("--integration", action="store_true", help="只运行集成测试")
    parser.add_argument("--coverage", action="store_true", help="运行测试并生成覆盖率报告")
    parser.add_argument("--fast", action="store_true", help="快速测试（跳过慢速测试）")
    
    args = parser.parse_args()
    
    # 基础测试命令
    base_cmd = "uv run python -m pytest"
    
    if args.unit:
        cmd = f"{base_cmd} -m 'not integration'"
        run_command(cmd, "单元测试")
    elif args.integration:
        cmd = f"{base_cmd} -m integration"
        run_command(cmd, "集成测试")
    elif args.coverage:
        # 需要安装 pytest-cov: uv add pytest-cov
        cmd = f"{base_cmd} --cov=api --cov-report=html --cov-report=term"
        run_command(cmd, "测试覆盖率分析")
    elif args.fast:
        cmd = f"{base_cmd} -m 'not slow'"
        run_command(cmd, "快速测试")
    else:
        # 运行所有测试
        cmd = f"{base_cmd}"
        run_command(cmd, "完整测试套件")

if __name__ == "__main__":
    main()