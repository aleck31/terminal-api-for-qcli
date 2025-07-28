#!/usr/bin/env python3
"""
测试stdout和stderr输出的脚本
"""

import sys
import time

def test_stdout_stderr():
    """测试标准输出和错误输出"""
    
    print("这是标准输出 (stdout)", file=sys.stdout)
    time.sleep(0.5)
    
    print("这是错误输出 (stderr)", file=sys.stderr)
    time.sleep(0.5)
    
    print("更多标准输出内容", file=sys.stdout)
    time.sleep(0.5)
    
    print("更多错误输出内容", file=sys.stderr)
    time.sleep(0.5)
    
    print("最后的标准输出", file=sys.stdout)

if __name__ == "__main__":
    test_stdout_stderr()
