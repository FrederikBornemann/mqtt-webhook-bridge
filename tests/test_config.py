import pytest
from app.config import Config, MQTTConfig, RouteConfig, ParameterConfig


def test_mqtt_config():
    """Test MQTT configuration model"""
    mqtt_config = MQTTConfig(
        broker="localhost",
        port=1883,
        username="test",
        password="test123"
    )
    assert mqtt_config.broker == "localhost"
    assert mqtt_config.port == 1883
    assert mqtt_config.username == "test"
    assert mqtt_config.client_id == "webhook-bridge"


def test_parameter_config():
    """Test parameter configuration model"""
    param = ParameterConfig(
        name="temperature",
        type="float",
        required=True,
        location="query"
    )
    assert param.name == "temperature"
    assert param.type == "float"
    assert param.required is True
    assert param.location == "query"


def test_route_config():
    """Test route configuration model"""
    route = RouteConfig(
        path="/test",
        method="POST",
        mqtt_topic="test/topic",
        payload_template='{"value": "{{param}}"}',
        qos=1
    )
    assert route.path == "/test"
    assert route.method == "POST"
    assert route.mqtt_topic == "test/topic"
    assert route.qos == 1
    assert route.retain is False


def test_config_load_from_yaml(tmp_path):
    """Test loading configuration from YAML file"""
    config_content = """
mqtt:
  broker: "localhost"
  port: 1883

routes:
  - path: "/test"
    method: "POST"
    mqtt_topic: "test/topic"
    payload_template: '{"test": "value"}'
"""
    config_file = tmp_path / "test_config.yaml"
    config_file.write_text(config_content)

    config = Config.load_from_yaml(str(config_file))
    assert config.mqtt.broker == "localhost"
    assert config.mqtt.port == 1883
    assert len(config.routes) == 1
    assert config.routes[0].path == "/test"
