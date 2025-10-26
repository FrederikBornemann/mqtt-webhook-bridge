import asyncio
import logging
from aiomqtt import Client
from typing import Optional
from app.config import MQTTConfig

logger = logging.getLogger(__name__)


class MQTTManager:
    def __init__(self, config: MQTTConfig):
        self.config = config
        self.client: Optional[Client] = None

    async def connect(self):
        """Connect to MQTT broker"""
        logger.debug(f"Attempting to connect to MQTT broker at {self.config.broker}:{self.config.port}")
        self.client = Client(
            hostname=self.config.broker,
            port=self.config.port,
            username=self.config.username,
            password=self.config.password,
            client_id=self.config.client_id,
            keepalive=self.config.keepalive
        )
        await self.client.__aenter__()
        logger.debug("MQTT client connection established")

    async def disconnect(self):
        """Disconnect from MQTT broker"""
        if self.client:
            logger.debug("Disconnecting from MQTT broker")
            await self.client.__aexit__(None, None, None)
            logger.debug("MQTT client disconnected")

    async def publish(self, topic: str, payload: str, qos: int = 0, retain: bool = False):
        """Publish message to MQTT topic"""
        if not self.client:
            logger.error("Attempted to publish without connected MQTT client")
            raise RuntimeError("MQTT client not connected")

        logger.info(f"Publishing to topic '{topic}' (QoS: {qos}, Retain: {retain})")
        logger.debug(f"Payload: {payload}")

        try:
            await self.client.publish(topic, payload, qos=qos, retain=retain)
            logger.debug(f"Successfully published to topic '{topic}'")
        except Exception as e:
            logger.error(f"Failed to publish to topic '{topic}': {e}", exc_info=True)
            raise

    @property
    def is_connected(self) -> bool:
        """Check if client is connected"""
        return self.client is not None
