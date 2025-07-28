#!/usr/bin/env python3
"""
Terminal API MVP - 测试脚本
用于测试gotty提供的Web终端API接口
"""

import requests
import json
import time
import base64
from urllib.parse import urljoin

class TerminalAPITester:
    def __init__(self, base_url="http://localhost:8080", username="demo", password="password123"):
        self.base_url = base_url
        self.session = requests.Session()
        
        # 设置基本认证
        credentials = base64.b64encode(f"{username}:{password}".encode()).decode()
        self.session.headers.update({
            'Authorization': f'Basic {credentials}',
            'User-Agent': 'Terminal-API-MVP-Tester/1.0'
        })
    
    def test_connection(self):
        """测试连接是否正常"""
        try:
            response = self.session.get(self.base_url, timeout=5)
            print(f"✅ 连接测试成功 - 状态码: {response.status_code}")
            return True
        except requests.exceptions.RequestException as e:
            print(f"❌ 连接测试失败: {e}")
            return False
    
    def test_websocket_info(self):
        """获取WebSocket连接信息"""
        try:
            # gotty使用gotty-bundle.js作为客户端脚本
            response = self.session.get(f"{self.base_url}/js/gotty-bundle.js", timeout=5)
            if response.status_code == 200:
                print("✅ 获取到gotty客户端脚本")
                print(f"脚本大小: {len(response.content)} 字节")
                return True
            else:
                print(f"⚠️  无法获取gotty脚本 - 状态码: {response.status_code}")
                return False
        except requests.exceptions.RequestException as e:
            print(f"❌ 获取WebSocket信息失败: {e}")
            return False
    
    def get_terminal_page(self):
        """获取终端页面"""
        try:
            response = self.session.get(self.base_url, timeout=5)
            if response.status_code == 200:
                print("✅ 成功获取终端页面")
                print(f"页面大小: {len(response.text)} 字符")
                
                # 检查页面是否包含gotty相关内容
                if "gotty" in response.text.lower():
                    print("✅ 页面包含gotty内容")
                    return True
                else:
                    print("⚠️  页面可能不是gotty终端页面")
                    return False
            else:
                print(f"❌ 获取终端页面失败 - 状态码: {response.status_code}")
                return False
        except requests.exceptions.RequestException as e:
            print(f"❌ 获取终端页面失败: {e}")
            return False
    
    def run_all_tests(self):
        """运行所有测试"""
        print("=== Terminal API MVP 测试开始 ===")
        print(f"测试目标: {self.base_url}")
        print(f"测试时间: {time.strftime('%Y-%m-%d %H:%M:%S')}")
        print()
        
        tests = [
            ("连接测试", self.test_connection),
            ("WebSocket信息测试", self.test_websocket_info),
            ("终端页面测试", self.get_terminal_page),
        ]
        
        results = []
        for test_name, test_func in tests:
            print(f"🧪 执行测试: {test_name}")
            result = test_func()
            results.append((test_name, result))
            print()
        
        print("=== 测试结果汇总 ===")
        passed = 0
        for test_name, result in results:
            status = "✅ 通过" if result else "❌ 失败"
            print(f"{test_name}: {status}")
            if result:
                passed += 1
        
        print(f"\n总计: {passed}/{len(results)} 个测试通过")
        
        if passed == len(results):
            print("🎉 所有测试通过！终端API已就绪")
        else:
            print("⚠️  部分测试失败，请检查gotty服务状态")

def main():
    import argparse
    parser = argparse.ArgumentParser(description='Terminal API MVP 测试工具')
    parser.add_argument('--url', default='http://localhost:8080', help='Gotty服务URL')
    parser.add_argument('--username', default='demo', help='认证用户名')
    parser.add_argument('--password', default='password123', help='认证密码')
    
    args = parser.parse_args()
    
    tester = TerminalAPITester(args.url, args.username, args.password)
    tester.run_all_tests()

if __name__ == "__main__":
    main()
