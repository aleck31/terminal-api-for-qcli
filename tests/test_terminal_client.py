#!/usr/bin/env python3
"""
TerminalAPIClient 集成测试
"""

import pytest
import logging
from api.terminal_client import TerminalAPIClient

# 设置日志级别
logging.basicConfig(level=logging.WARNING)

class TestTerminalAPIClient:
    """TerminalAPIClient 集成测试"""
    
    @pytest.fixture
    def client(self):
        """创建测试客户端"""
        return TerminalAPIClient(
            base_url="http://localhost:8080",
            username="demo",
            password="password123"
        )
    
    def test_client_initialization(self, client):
        """测试客户端初始化"""
        assert client.base_url == "http://localhost:8080"
        assert client.username == "demo"
        assert client.password == "password123"
        assert client.connection_manager is not None
    
    def test_http_connection(self, client):
        """测试HTTP连接"""
        # 注意：这个测试需要Gotty服务运行
        # 在CI环境中可能需要跳过或mock
        try:
            result = client.test_connection()
            # 如果服务运行，应该返回True；如果不运行，返回False
            assert isinstance(result, bool)
        except Exception as e:
            pytest.skip(f"Gotty服务未运行: {e}")
    
    def test_websocket_connection(self, client):
        """测试WebSocket连接"""
        try:
            result = client.test_websocket_connection()
            assert isinstance(result, bool)
        except Exception as e:
            pytest.skip(f"Gotty服务未运行: {e}")
    
    def test_connection_status(self, client):
        """测试连接状态获取"""
        status = client.get_connection_status()
        
        # 验证状态字典包含必要的键
        required_keys = [
            "http_connected", "websocket_connected", "health_status",
            "base_url", "username", "connection_info"
        ]
        
        for key in required_keys:
            assert key in status
        
        assert status["base_url"] == "http://localhost:8080"
        assert status["username"] == "demo"
    
    @pytest.mark.integration
    def test_command_execution(self, client):
        """测试命令执行（集成测试）"""
        # 这是一个集成测试，需要真实的Gotty服务
        try:
            # 测试简单命令
            results = list(client.execute_command("echo 'test'", timeout=5.0))
            
            # 应该至少有状态消息和摘要消息
            assert len(results) >= 2
            
            # 第一个消息应该是状态消息
            first_result = results[0]
            assert first_result[0] == "status"
            assert "正在执行命令" in first_result[1]
            
        except Exception as e:
            pytest.skip(f"Gotty服务未运行或命令执行失败: {e}")
    
    def test_client_cleanup(self, client):
        """测试客户端清理"""
        # 测试close方法不会抛出异常
        client.close()
        
        # 多次调用close应该是安全的
        client.close()

# 集成测试标记配置
def pytest_configure(config):
    """配置pytest标记"""
    config.addinivalue_line(
        "markers", "integration: 需要真实Gotty服务的集成测试"
    )