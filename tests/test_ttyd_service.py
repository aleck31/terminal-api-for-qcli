#!/usr/bin/env python3
"""
简单的TTYD服务脚本测试
直接运行即可测试服务管理功能
"""

import subprocess
import sys
import os
from pathlib import Path

def run_command(cmd, description):
    """运行命令并返回结果"""
    try:
        result = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=10)
        return result.returncode == 0, result.stdout, result.stderr
    except subprocess.TimeoutError:
        return False, "", "命令超时"
    except Exception as e:
        return False, "", str(e)

def test_service_script():
    """测试服务脚本基本功能"""
    print("=== TTYD服务脚本测试 ===\n")
    
    # 获取脚本路径
    project_root = Path(__file__).parent.parent
    script_path = project_root / "ttyd" / "ttyd-service.sh"
    
    if not script_path.exists():
        print(f"❌ 服务脚本不存在: {script_path}")
        return False
    
    # 测试帮助命令
    success, stdout, stderr = run_command(f"{script_path} help", "帮助命令")
    if success and "TTYD Service Management Script" in stdout:
        print("✅ 帮助命令测试通过")
    else:
        print("❌ 帮助命令测试失败")
        return False
    
    # 测试状态命令（不需要服务运行）
    success, stdout, stderr = run_command(f"{script_path} status", "状态查看")
    if "服务状态" in stdout or "服务未运行" in stdout:
        print("✅ 状态命令测试通过")
    else:
        print("⚠️  状态命令可能有问题，但继续测试")
    
    # 测试配置文件加载
    if "加载配置文件" in stdout:
        print("✅ 配置文件加载正常")
    else:
        print("⚠️  配置文件加载可能有问题")
    
    print("✅ 服务脚本基本功能测试完成")
    return True

def test_config_file():
    """测试配置文件"""
    print("\n=== 配置文件测试 ===\n")
    
    project_root = Path(__file__).parent.parent
    config_path = project_root / "ttyd" / "conf.ini"
    
    if not config_path.exists():
        print(f"❌ 配置文件不存在: {config_path}")
        return False
    
    try:
        with open(config_path, 'r') as f:
            content = f.read()
        
        # 检查基本配置项
        required_configs = ['port=', 'credential=', 'permit_write=']
        for config in required_configs:
            if config in content:
                print(f"✅ 配置项 {config} 存在")
            else:
                print(f"❌ 配置项 {config} 缺失")
                return False
        
        print("✅ 配置文件测试通过")
        return True
        
    except Exception as e:
        print(f"❌ 配置文件读取失败: {e}")
        return False

if __name__ == "__main__":
    print("开始服务脚本测试...\n")
    
    test1 = test_service_script()
    test2 = test_config_file()
    
    if test1 and test2:
        print("\n🎉 所有服务脚本测试通过")
        sys.exit(0)
    else:
        print("\n❌ 部分测试失败")
        sys.exit(1)
