from fastapi import FastAPI
from contextlib import asynccontextmanager
from typing import Optional
import uvicorn
import os
import sys
import logging

from app.config import Config
from app.mqtt_client import MQTTManager
from app.route_builder import RouteBuilder
from app.models import HealthResponse

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)


# Global instances
mqtt_manager: Optional[MQTTManager] = None
config: Optional[Config] = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup and shutdown events"""
    # Startup
    global mqtt_manager, config

    # Get config path from environment or use default
    config_path = os.getenv("CONFIG_PATH", "config/routes.yaml")

    logger.info(f"Loading configuration from: {config_path}")
    try:
        config = Config.load_from_yaml(config_path)
        logger.info("Configuration loaded successfully")
        logger.info(f"MQTT Broker: {config.mqtt.broker}:{config.mqtt.port}")
        logger.info(f"Routes configured: {len(config.routes)}")
    except Exception as e:
        logger.error(f"Error loading configuration: {e}", exc_info=True)
        sys.exit(1)

    # Initialize MQTT manager
    mqtt_manager = MQTTManager(config.mqtt)

    try:
        logger.info("Connecting to MQTT broker...")
        await mqtt_manager.connect()
        logger.info("Successfully connected to MQTT broker")
    except Exception as e:
        logger.error(f"Error connecting to MQTT broker: {e}", exc_info=True)
        sys.exit(1)

    # Build routes dynamically
    route_builder = RouteBuilder(mqtt_manager)
    route_builder.build_routes(config.routes)
    app.include_router(route_builder.router)
    logger.info(f"Routes built and registered: {len(config.routes)} endpoints")

    yield

    # Shutdown
    logger.info("Shutting down...")
    await mqtt_manager.disconnect()
    logger.info("Disconnected from MQTT broker")


app = FastAPI(
    title="MQTT-Webhook Bridge",
    description="Bridge between HTTP webhooks and MQTT topics",
    version="1.0.0",
    lifespan=lifespan
)


@app.get("/health", response_model=HealthResponse)
async def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "mqtt_connected": mqtt_manager.is_connected if mqtt_manager else False
    }


@app.get("/")
async def root():
    """Root endpoint with basic information"""
    return {
        "service": "MQTT-Webhook Bridge",
        "version": "1.0.0",
        "docs": "/docs",
        "health": "/health"
    }


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
