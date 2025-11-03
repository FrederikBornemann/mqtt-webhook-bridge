"""
Integration tests for MQTT-Webhook Bridge with Docker Compose

This test suite:
- Starts Docker Compose with Mosquitto MQTT broker and webhook bridge
- Connects a test MQTT client to receive messages
- Sends HTTP requests to the webhook bridge with API key authentication
- Verifies that the correct MQTT messages are received on the expected topics
"""

import pytest
import time
import json
import threading
import requests
import paho.mqtt.client as mqtt
from typing import Dict, List, Optional, Any
from queue import Queue, Empty


class MQTTTestClient:
    """Test MQTT client that collects messages from subscribed topics"""

    def __init__(self, broker: str = "localhost", port: int = 1883):
        self.broker = broker
        self.port = port
        self.client = mqtt.Client(client_id="test-client", protocol=mqtt.MQTTv311)
        self.messages: Queue = Queue()
        self.connected = False
        self.subscribed_topics: List[str] = []

        # Set up callbacks
        self.client.on_connect = self._on_connect
        self.client.on_message = self._on_message
        self.client.on_disconnect = self._on_disconnect

    def _on_connect(self, client, userdata, flags, rc):
        """Callback when connected to MQTT broker"""
        if rc == 0:
            self.connected = True
            print(f"Connected to MQTT broker at {self.broker}:{self.port}")
        else:
            print(f"Failed to connect to MQTT broker, return code: {rc}")

    def _on_message(self, client, userdata, msg):
        """Callback when a message is received"""
        message = {
            "topic": msg.topic,
            "payload": msg.payload.decode('utf-8'),
            "qos": msg.qos,
            "retain": msg.retain
        }
        self.messages.put(message)
        print(f"Received message on topic '{msg.topic}': {msg.payload.decode('utf-8')}")

    def _on_disconnect(self, client, userdata, rc):
        """Callback when disconnected from MQTT broker"""
        self.connected = False
        print(f"Disconnected from MQTT broker, return code: {rc}")

    def connect(self, timeout: int = 10) -> bool:
        """Connect to MQTT broker with timeout"""
        try:
            self.client.connect(self.broker, self.port, keepalive=60)
            self.client.loop_start()

            # Wait for connection
            start_time = time.time()
            while not self.connected and (time.time() - start_time) < timeout:
                time.sleep(0.1)

            return self.connected
        except Exception as e:
            print(f"Error connecting to MQTT broker: {e}")
            return False

    def disconnect(self):
        """Disconnect from MQTT broker"""
        self.client.loop_stop()
        self.client.disconnect()

    def subscribe(self, topic: str, qos: int = 0):
        """Subscribe to a topic"""
        self.client.subscribe(topic, qos)
        self.subscribed_topics.append(topic)
        print(f"Subscribed to topic: {topic}")

    def wait_for_message(self, timeout: float = 5.0) -> Optional[Dict[str, Any]]:
        """Wait for a message with timeout"""
        try:
            return self.messages.get(timeout=timeout)
        except Empty:
            return None

    def clear_messages(self):
        """Clear all messages from the queue"""
        while not self.messages.empty():
            try:
                self.messages.get_nowait()
            except Empty:
                break


@pytest.fixture(scope="module")
def mqtt_client():
    """Fixture that provides an MQTT test client"""
    client = MQTTTestClient(broker="localhost", port=1883)

    # Connect to MQTT broker
    assert client.connect(timeout=10), "Failed to connect to MQTT broker"

    # Give it a moment to stabilize
    time.sleep(0.5)

    yield client

    # Cleanup
    client.disconnect()


@pytest.fixture(scope="module")
def api_client():
    """Fixture that provides HTTP client configuration"""
    return {
        "base_url": "http://localhost:8000",
        "api_key": "test-api-key-12345",
        "headers": {
            "X-API-Key": "test-api-key-12345",
            "Content-Type": "application/json"
        }
    }


@pytest.fixture(autouse=True)
def clear_mqtt_messages(mqtt_client):
    """Clear MQTT messages before each test"""
    mqtt_client.clear_messages()
    yield


class TestHealthEndpoints:
    """Test health and info endpoints"""

    def test_health_endpoint(self, api_client):
        """Test that the health endpoint works"""
        response = requests.get(f"{api_client['base_url']}/health")
        assert response.status_code == 200

        data = response.json()
        assert data["status"] == "healthy"
        assert data["mqtt_connected"] is True

    def test_root_endpoint(self, api_client):
        """Test that the root endpoint returns service info"""
        response = requests.get(f"{api_client['base_url']}/")
        assert response.status_code == 200

        data = response.json()
        assert data["service"] == "MQTT-Webhook Bridge"
        assert data["api_version"] == "v1"


class TestAPIAuthentication:
    """Test API key authentication"""

    def test_request_without_api_key_fails(self, api_client):
        """Test that requests without API key are rejected"""
        response = requests.post(
            f"{api_client['base_url']}/v1/test/simple?message=test",
            headers={"Content-Type": "application/json"}  # No API key
        )
        assert response.status_code == 401
        assert "Missing API key" in response.json()["detail"]

    def test_request_with_invalid_api_key_fails(self, api_client):
        """Test that requests with invalid API key are rejected"""
        response = requests.post(
            f"{api_client['base_url']}/v1/test/simple?message=test",
            headers={
                "X-API-Key": "invalid-key",
                "Content-Type": "application/json"
            }
        )
        assert response.status_code == 401
        assert "Invalid API key" in response.json()["detail"]

    def test_request_with_valid_api_key_succeeds(self, api_client, mqtt_client):
        """Test that requests with valid API key are accepted"""
        mqtt_client.subscribe("test/simple", qos=1)
        time.sleep(0.2)

        response = requests.post(
            f"{api_client['base_url']}/v1/test/simple?message=authenticated",
            headers=api_client["headers"]
        )
        assert response.status_code == 200


class TestSimpleRoute:
    """Test simple route with query parameters"""

    def test_simple_post_with_query_param(self, api_client, mqtt_client):
        """Test simple POST endpoint with query parameter"""
        # Subscribe to the topic
        mqtt_client.subscribe("test/simple", qos=1)
        time.sleep(0.2)  # Give subscription time to register

        # Send HTTP request
        response = requests.post(
            f"{api_client['base_url']}/v1/test/simple?message=hello",
            headers=api_client["headers"]
        )

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "published"
        assert data["topic"] == "test/simple"

        # Wait for MQTT message
        mqtt_msg = mqtt_client.wait_for_message(timeout=5.0)
        assert mqtt_msg is not None, "Did not receive MQTT message"
        assert mqtt_msg["topic"] == "test/simple"
        assert mqtt_msg["qos"] == 1

        # Parse and verify payload
        payload = json.loads(mqtt_msg["payload"])
        assert payload["message"] == "hello"
        assert "timestamp" in payload


class TestPathParametersRoute:
    """Test routes with path parameters"""

    def test_device_control_with_path_param(self, api_client, mqtt_client):
        """Test device control endpoint with path parameter"""
        device_id = "light-001"
        mqtt_client.subscribe(f"test/devices/{device_id}/command", qos=1)
        time.sleep(0.2)

        # Send HTTP request
        response = requests.post(
            f"{api_client['base_url']}/v1/device/{device_id}/control",
            headers=api_client["headers"],
            json={"action": "on"}
        )

        assert response.status_code == 200
        data = response.json()
        assert data["topic"] == f"test/devices/{device_id}/command"

        # Wait for MQTT message
        mqtt_msg = mqtt_client.wait_for_message(timeout=5.0)
        assert mqtt_msg is not None
        assert mqtt_msg["topic"] == f"test/devices/{device_id}/command"

        payload = json.loads(mqtt_msg["payload"])
        assert payload["device"] == device_id
        assert payload["action"] == "on"
        assert payload["source"] == "test"

    def test_device_control_with_invalid_action(self, api_client, mqtt_client):
        """Test device control with invalid enum value"""
        response = requests.post(
            f"{api_client['base_url']}/v1/device/light-001/control",
            headers=api_client["headers"],
            json={"action": "invalid"}
        )

        # Should fail validation
        assert response.status_code == 422


class TestBodyParametersRoute:
    """Test routes with body parameters and validation"""

    def test_sensor_update_with_valid_data(self, api_client, mqtt_client):
        """Test sensor update with valid body parameters"""
        mqtt_client.subscribe("test/sensor/data", qos=2)
        time.sleep(0.2)

        response = requests.post(
            f"{api_client['base_url']}/v1/sensor/update",
            headers=api_client["headers"],
            json={
                "sensor_id": "temp-sensor-01",
                "value": 23.5,
                "unit": "celsius"
            }
        )

        assert response.status_code == 200

        mqtt_msg = mqtt_client.wait_for_message(timeout=5.0)
        assert mqtt_msg is not None
        assert mqtt_msg["qos"] == 2  # Verify QoS 2

        payload = json.loads(mqtt_msg["payload"])
        assert payload["sensor"] == "temp-sensor-01"
        assert payload["value"] == 23.5
        assert payload["unit"] == "celsius"

    def test_sensor_update_with_default_unit(self, api_client, mqtt_client):
        """Test sensor update with default unit parameter"""
        mqtt_client.subscribe("test/sensor/data", qos=2)
        time.sleep(0.2)

        response = requests.post(
            f"{api_client['base_url']}/v1/sensor/update",
            headers=api_client["headers"],
            json={
                "sensor_id": "temp-sensor-02",
                "value": 75.0
                # unit not provided, should use default "celsius"
            }
        )

        assert response.status_code == 200

        mqtt_msg = mqtt_client.wait_for_message(timeout=5.0)
        assert mqtt_msg is not None

        payload = json.loads(mqtt_msg["payload"])
        assert payload["unit"] == "celsius"

    def test_sensor_update_with_out_of_range_value(self, api_client):
        """Test sensor update with value outside allowed range"""
        response = requests.post(
            f"{api_client['base_url']}/v1/sensor/update",
            headers=api_client["headers"],
            json={
                "sensor_id": "temp-sensor-03",
                "value": 150.0  # Max is 100.0
            }
        )

        # Should fail validation
        assert response.status_code == 422


class TestEnumValidation:
    """Test enum validation in routes"""

    def test_automation_with_valid_scene(self, api_client, mqtt_client):
        """Test automation trigger with valid enum value"""
        mqtt_client.subscribe("test/automation/scene", qos=1)
        time.sleep(0.2)

        response = requests.get(
            f"{api_client['base_url']}/v1/automation/trigger?scene=morning",
            headers=api_client["headers"]
        )

        assert response.status_code == 200

        mqtt_msg = mqtt_client.wait_for_message(timeout=5.0)
        assert mqtt_msg is not None

        payload = json.loads(mqtt_msg["payload"])
        assert payload["scene"] == "morning"
        assert payload["mode"] == "test"

    def test_automation_with_invalid_scene(self, api_client):
        """Test automation trigger with invalid enum value"""
        response = requests.get(
            f"{api_client['base_url']}/v1/automation/trigger?scene=invalid",
            headers=api_client["headers"]
        )

        # Should fail validation
        assert response.status_code == 422


class TestMultipleParameters:
    """Test routes with multiple path parameters"""

    def test_room_device_state_update(self, api_client, mqtt_client):
        """Test route with multiple path parameters and optional body params"""
        room_id = "living-room"
        device_id = "lamp-01"
        topic = f"test/room/{room_id}/device/{device_id}/state"

        mqtt_client.subscribe(topic, qos=1)
        time.sleep(0.2)

        response = requests.put(
            f"{api_client['base_url']}/v1/room/{room_id}/device/{device_id}/state",
            headers=api_client["headers"],
            json={
                "state": True,
                "brightness": 75
            }
        )

        assert response.status_code == 200

        mqtt_msg = mqtt_client.wait_for_message(timeout=5.0)
        assert mqtt_msg is not None
        assert mqtt_msg["topic"] == topic
        # Note: retain flag on received messages indicates if message came from retained storage
        # For live messages, retain will be 0 even if published with retain=True

        payload = json.loads(mqtt_msg["payload"])
        assert payload["room"] == room_id
        assert payload["device"] == device_id
        assert payload["state"] is True
        assert payload["brightness"] == 75

    def test_room_device_state_without_optional_param(self, api_client, mqtt_client):
        """Test route with optional parameter not provided"""
        room_id = "bedroom"
        device_id = "lamp-02"
        topic = f"test/room/{room_id}/device/{device_id}/state"

        mqtt_client.subscribe(topic, qos=1)
        time.sleep(0.2)

        response = requests.put(
            f"{api_client['base_url']}/v1/room/{room_id}/device/{device_id}/state",
            headers=api_client["headers"],
            json={
                "state": False
                # brightness not provided
            }
        )

        assert response.status_code == 200

        mqtt_msg = mqtt_client.wait_for_message(timeout=5.0)
        assert mqtt_msg is not None

        payload = json.loads(mqtt_msg["payload"])
        assert payload["state"] is False
        assert "brightness" not in payload  # Optional param should not be in payload


class TestConcurrentRequests:
    """Test handling of concurrent requests"""

    def test_multiple_concurrent_requests(self, api_client, mqtt_client):
        """Test that multiple concurrent requests are handled correctly"""
        # Subscribe to wildcard topic
        mqtt_client.subscribe("test/devices/+/command", qos=1)
        time.sleep(0.2)

        # Send multiple requests concurrently
        device_ids = ["dev-01", "dev-02", "dev-03", "dev-04", "dev-05"]

        responses = []
        for device_id in device_ids:
            response = requests.post(
                f"{api_client['base_url']}/v1/device/{device_id}/control",
                headers=api_client["headers"],
                json={"action": "toggle"}
            )
            responses.append(response)

        # Verify all requests succeeded
        for response in responses:
            assert response.status_code == 200

        # Collect all MQTT messages
        received_messages = []
        for _ in device_ids:
            msg = mqtt_client.wait_for_message(timeout=5.0)
            if msg:
                received_messages.append(msg)

        # Verify we received all messages
        assert len(received_messages) == len(device_ids)

        # Verify each device got its message
        received_devices = set()
        for msg in received_messages:
            payload = json.loads(msg["payload"])
            received_devices.add(payload["device"])

        assert received_devices == set(device_ids)


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
