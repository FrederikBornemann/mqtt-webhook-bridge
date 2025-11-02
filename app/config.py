from pydantic import BaseModel, Field
from typing import List, Optional, Literal, Any
import yaml


class ParameterConfig(BaseModel):
    name: str
    type: Literal["string", "integer", "float", "boolean"]
    required: bool = True
    location: Literal["query", "path", "body"] = "query"
    enum: Optional[List[str]] = None
    min: Optional[float] = None
    max: Optional[float] = None
    default: Optional[Any] = None


class RouteConfig(BaseModel):
    path: str
    method: Literal["GET", "POST", "PUT", "DELETE"] = "POST"
    mqtt_topic: str
    parameters: List[ParameterConfig] = []
    payload_template: str
    qos: int = Field(default=0, ge=0, le=2)  # MQTT QoS level
    retain: bool = False


class MQTTConfig(BaseModel):
    broker: str
    port: int = 1883
    username: Optional[str] = None
    password: Optional[str] = None
    client_id: str = "webhook-bridge"
    keepalive: int = 60


class Config(BaseModel):
    mqtt: MQTTConfig
    routes: List[RouteConfig]
    api_version: str = "v1"  # Default API version

    @classmethod
    def load_from_yaml(cls, path: str) -> "Config":
        with open(path, 'r') as f:
            data = yaml.safe_load(f)
        return cls(**data)
