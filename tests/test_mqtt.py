import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from app.mqtt_client import MQTTManager
from app.config import MQTTConfig


@pytest.fixture
def mqtt_config():
    """MQTT configuration fixture"""
    return MQTTConfig(
        broker="localhost",
        port=1883,
        client_id="test-client"
    )


@pytest.mark.asyncio
async def test_mqtt_manager_init(mqtt_config):
    """Test MQTT manager initialization"""
    manager = MQTTManager(mqtt_config)
    assert manager.config == mqtt_config
    assert manager.client is None
    assert manager.is_connected is False


@pytest.mark.asyncio
async def test_mqtt_manager_connect(mqtt_config):
    """Test MQTT manager connection"""
    with patch('app.mqtt_client.Client') as mock_client:
        mock_instance = AsyncMock()
        mock_client.return_value = mock_instance

        manager = MQTTManager(mqtt_config)
        await manager.connect()

        mock_client.assert_called_once_with(
            hostname=mqtt_config.broker,
            port=mqtt_config.port,
            username=mqtt_config.username,
            password=mqtt_config.password,
            identifier=mqtt_config.client_id,
            keepalive=mqtt_config.keepalive
        )
        mock_instance.__aenter__.assert_called_once()


@pytest.mark.asyncio
async def test_mqtt_manager_publish_without_connection(mqtt_config):
    """Test publishing without connection raises error"""
    manager = MQTTManager(mqtt_config)

    with pytest.raises(RuntimeError, match="MQTT client not connected"):
        await manager.publish("test/topic", "test payload")


@pytest.mark.asyncio
async def test_mqtt_manager_disconnect(mqtt_config):
    """Test MQTT manager disconnection"""
    with patch('app.mqtt_client.Client') as mock_client:
        mock_instance = AsyncMock()
        mock_client.return_value = mock_instance

        manager = MQTTManager(mqtt_config)
        await manager.connect()
        await manager.disconnect()

        mock_instance.__aexit__.assert_called_once()
