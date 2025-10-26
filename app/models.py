from pydantic import BaseModel
from typing import Any, Dict


class HealthResponse(BaseModel):
    status: str
    mqtt_connected: bool


class WebhookResponse(BaseModel):
    status: str
    mqtt_topic: str
    payload: Dict[str, Any]
