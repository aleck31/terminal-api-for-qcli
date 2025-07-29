#!/usr/bin/env python3
"""
WebSocket客户端测试
"""

import pytest
import time
import threading
from unittest.mock import Mock, patch, MagicMock
from api.websocket_client import WebSocketClient, MessageSerializer, WebSocketMessage, ConnectionState
from api.connection_manager import ConnectionManager, HealthStatus

class TestMessageSerializer:
    """消息序列化器测试"""
    
    def test_serialize_command(self):
        """测试命令序列化"""
        command = "ls -la"
        result = MessageSerializer.serialize_command(command)
        assert result == "0ls -la\n"
    
    def test_serialize_input(self):
        """测试输入序列化"""
        input_data = "hello"
        result = MessageSerializer.serialize_input(input_data)
        assert result == "0hello"
    
    def test_deserialize_output_message(self):
        """测试输出消息反序列化"""
        # 模拟base64编码的输出 - Gotty协议中'1'表示终端输出
        import base64
        original_text = "Hello World"
        encoded_text = base64.b64encode(original_text.encode()).decode()
        raw_message = "1" + encoded_text
        
        message = MessageSerializer.deserialize_message(raw_message)
        assert message.type == "output"
        assert message.data == original_text
    
    def test_deserialize_input_message(self):
        """测试输入消息反序列化"""
        raw_message = "0user_input"
        message = MessageSerializer.deserialize_message(raw_message)
        assert message.type == "input"
        assert message.data == "user_input"
    
    def test_deserialize_empty_message(self):
        """测试空消息反序列化"""
        message = MessageSerializer.deserialize_message("")
        assert message.type == "empty"
        assert message.data == ""
    
    def test_deserialize_json_message(self):
        """测试JSON消息反序列化"""
        json_data = '{"test": "value"}'
        message = MessageSerializer.deserialize_message(json_data)
        assert message.type == "json"
        assert message.data == {"test": "value"}

class TestWebSocketClient:
    """WebSocket客户端测试"""
    
    @pytest.fixture
    def client(self):
        """创建测试客户端"""
        return WebSocketClient(
            base_url="http://localhost:8080",
            username="test",
            password="test123",
            max_reconnect_attempts=3,
            reconnect_delay=0.1,  # 快速重试用于测试
            connection_timeout=5.0,
            ping_interval=10.0
        )
    
    def test_init(self, client):
        """测试初始化"""
        assert client.base_url == "http://localhost:8080"
        assert client.username == "test"
        assert client.password == "test123"
        assert client.state == ConnectionState.DISCONNECTED
        assert client.ws_url == "ws://localhost:8080/ws"
    
    def test_https_url_conversion(self):
        """测试HTTPS URL转换"""
        client = WebSocketClient("https://example.com", "user", "pass")
        assert client.ws_url == "wss://example.com/ws"
    
    @patch('websocket.WebSocket')
    def test_connect_success(self, mock_websocket, client):
        """测试连接成功"""
        mock_ws = Mock()
        mock_websocket.return_value = mock_ws
        
        result = client.connect()
        
        assert result is True
        assert client.state == ConnectionState.CONNECTED
        assert client.reconnect_attempts == 0
        mock_ws.connect.assert_called_once()
        mock_ws.send.assert_called_once()  # 认证消息
    
    @patch('websocket.WebSocket')
    def test_connect_failure(self, mock_websocket, client):
        """测试连接失败"""
        mock_ws = Mock()
        mock_ws.connect.side_effect = Exception("Connection failed")
        mock_websocket.return_value = mock_ws
        
        result = client.connect()
        
        assert result is False
        assert client.state == ConnectionState.FAILED
    
    @patch('websocket.WebSocket')
    def test_send_command(self, mock_websocket, client):
        """测试发送命令"""
        mock_ws = Mock()
        mock_websocket.return_value = mock_ws
        client.ws = mock_ws
        client.state = ConnectionState.CONNECTED
        
        result = client.send_command("ls -la")
        
        assert result is True
        mock_ws.send.assert_called_with("0ls -la\n")
    
    @patch('websocket.WebSocket')
    def test_send_command_not_connected(self, mock_websocket, client):
        """测试未连接时发送命令"""
        result = client.send_command("ls -la")
        assert result is False
    
    @patch('websocket.WebSocket')
    def test_receive_message(self, mock_websocket, client):
        """测试接收消息"""
        mock_ws = Mock()
        import base64
        test_data = "Hello World"
        encoded_data = base64.b64encode(test_data.encode()).decode()
        mock_ws.recv.return_value = "1" + encoded_data  # '1'表示终端输出
        mock_websocket.return_value = mock_ws
        
        client.ws = mock_ws
        client.state = ConnectionState.CONNECTED
        
        message = client.receive_message()
        
        assert message is not None
        assert message.type == "output"
        assert message.data == test_data
    
    def test_callback_registration(self, client):
        """测试回调注册"""
        message_callback = Mock()
        error_callback = Mock()
        state_callback = Mock()
        
        client.add_message_callback(message_callback)
        client.add_error_callback(error_callback)
        client.add_state_callback(state_callback)
        
        assert message_callback in client.message_callbacks
        assert error_callback in client.error_callbacks
        assert state_callback in client.state_callbacks
    
    def test_connection_info(self, client):
        """测试连接信息"""
        info = client.get_connection_info()
        
        assert "url" in info
        assert "state" in info
        assert "reconnect_attempts" in info
        assert "username" in info
        assert info["url"] == "ws://localhost:8080/ws"
        assert info["state"] == "disconnected"

class TestConnectionManager:
    """连接管理器测试"""
    
    @pytest.fixture
    def manager(self):
        """创建测试连接管理器"""
        return ConnectionManager(
            base_url="http://localhost:8080",
            username="test",
            password="test123",
            auto_reconnect=True,
            health_check_interval=1.0,  # 快速健康检查用于测试
            max_connection_pool_size=3
        )
    
    def test_init(self, manager):
        """测试初始化"""
        assert manager.base_url == "http://localhost:8080"
        assert manager.username == "test"
        assert manager.password == "test123"
        assert manager.auto_reconnect is True
        assert manager.health_status == HealthStatus.UNHEALTHY
        assert manager.primary_client is not None
    
    @patch('api.websocket_client.WebSocketClient.connect')
    def test_start_success(self, mock_connect, manager):
        """测试启动成功"""
        mock_connect.return_value = True
        
        result = manager.start()
        
        assert result is True
        assert manager.health_status == HealthStatus.HEALTHY
        assert manager.metrics.total_connections == 1
        assert manager.metrics.successful_connections == 1
    
    @patch('api.websocket_client.WebSocketClient.connect')
    def test_start_failure(self, mock_connect, manager):
        """测试启动失败"""
        mock_connect.return_value = False
        
        result = manager.start()
        
        assert result is False
        assert manager.health_status == HealthStatus.UNHEALTHY
        assert manager.metrics.failed_connections == 1
    
    @patch('api.websocket_client.WebSocketClient.is_connected')
    @patch('api.websocket_client.WebSocketClient.send_command')
    def test_send_command(self, mock_send, mock_connected, manager):
        """测试发送命令"""
        mock_connected.return_value = True
        mock_send.return_value = True
        
        result = manager.send_command("ls -la")
        
        assert result is True
        assert manager.metrics.messages_sent == 1
        mock_send.assert_called_with("ls -la")
    
    @patch('api.websocket_client.WebSocketClient.is_connected')
    def test_send_command_not_connected(self, mock_connected, manager):
        """测试未连接时发送命令"""
        mock_connected.return_value = False
        
        result = manager.send_command("ls -la")
        
        assert result is False
        assert manager.metrics.messages_sent == 0
    
    def test_get_metrics(self, manager):
        """测试获取指标"""
        metrics = manager.get_metrics()
        
        assert hasattr(metrics, 'total_connections')
        assert hasattr(metrics, 'successful_connections')
        assert hasattr(metrics, 'failed_connections')
        assert hasattr(metrics, 'success_rate')
        assert hasattr(metrics, 'uptime')
    
    def test_get_connection_info(self, manager):
        """测试获取连接信息"""
        info = manager.get_connection_info()
        
        assert "health_status" in info
        assert "metrics" in info
        assert "primary_connection" in info
        assert "pool_connections" in info
        assert info["health_status"] == "unhealthy"
    
    def test_callback_registration(self, manager):
        """测试回调注册"""
        connection_callback = Mock()
        message_callback = Mock()
        error_callback = Mock()
        
        manager.add_connection_callback(connection_callback)
        manager.add_message_callback(message_callback)
        manager.add_error_callback(error_callback)
        
        assert connection_callback in manager.connection_callbacks
        assert message_callback in manager.message_callbacks
        assert error_callback in manager.error_callbacks

# 集成测试
class TestIntegration:
    """集成测试"""
    
    @pytest.mark.integration
    @patch('api.websocket_client.WebSocketClient.connect')
    @patch('api.websocket_client.WebSocketClient.send_command')
    @patch('api.websocket_client.WebSocketClient.is_connected')
    def test_full_workflow(self, mock_connected, mock_send, mock_connect):
        """测试完整工作流程"""
        # 设置模拟
        mock_connect.return_value = True
        mock_connected.return_value = True
        mock_send.return_value = True
        
        # 创建连接管理器
        manager = ConnectionManager("http://localhost:8080", "test", "test123")
        
        # 启动管理器
        assert manager.start() is True
        
        # 发送命令
        assert manager.send_command("echo hello") is True
        
        # 检查状态
        assert manager.is_connected() is True
        assert manager.get_health_status() == HealthStatus.HEALTHY
        
        # 停止管理器
        manager.stop()
        assert manager.health_status == HealthStatus.UNHEALTHY

if __name__ == "__main__":
    pytest.main([__file__, "-v"])