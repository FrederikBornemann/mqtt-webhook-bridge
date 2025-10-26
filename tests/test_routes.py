import pytest
from fastapi.testclient import TestClient
from unittest.mock import AsyncMock, patch, MagicMock
from app.main import app
from app.config import Config


@pytest.fixture
def mock_mqtt_manager():
    """Mock MQTT manager for testing"""
    with patch('app.main.mqtt_manager') as mock:
        mock.publish = AsyncMock()
        mock.is_connected = True
        yield mock


@pytest.fixture
def client():
    """FastAPI test client"""
    return TestClient(app)


def test_health_endpoint(client):
    """Test health check endpoint"""
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert "status" in data
    assert "mqtt_connected" in data


def test_root_endpoint(client):
    """Test root endpoint"""
    response = client.get("/")
    assert response.status_code == 200
    data = response.json()
    assert data["service"] == "MQTT-Webhook Bridge"
    assert "version" in data
    assert "docs" in data
    assert "health" in data


@pytest.mark.asyncio
async def test_mqtt_publish(mock_mqtt_manager):
    """Test MQTT publish functionality"""
    await mock_mqtt_manager.publish(
        topic="test/topic",
        payload='{"test": "value"}',
        qos=1,
        retain=False
    )
    mock_mqtt_manager.publish.assert_called_once_with(
        topic="test/topic",
        payload='{"test": "value"}',
        qos=1,
        retain=False
    )
