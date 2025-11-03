from fastapi import APIRouter, Query, Path, Body, HTTPException, Request, Depends
from jinja2 import Template
from typing import List, Any, Dict, Optional
import json
import inspect
import logging
from datetime import datetime
from app.mqtt_client import MQTTManager
from app.config import RouteConfig, ParameterConfig
from app.auth import verify_api_key

logger = logging.getLogger(__name__)


class RouteBuilder:
    def __init__(self, mqtt_manager: MQTTManager):
        self.mqtt_manager = mqtt_manager
        self.router = APIRouter()

    def build_routes(self, route_configs: List[RouteConfig]):
        """Dynamically build FastAPI routes from configuration"""
        logger.info(f"Building {len(route_configs)} routes")
        for route_config in route_configs:
            self._create_route(route_config)
            logger.debug(f"Built route: {route_config.method} {route_config.path} -> {route_config.mqtt_topic}")

    def _create_route(self, config: RouteConfig):
        """Create a single route"""

        # Separate parameters by location
        query_params = [p for p in config.parameters if p.location == "query"]
        path_params = [p for p in config.parameters if p.location == "path"]
        body_params = [p for p in config.parameters if p.location == "body"]

        # Build the endpoint function dynamically
        async def endpoint(request: Request, api_key: str = Depends(verify_api_key), **kwargs):
            try:
                logger.debug(f"Handling request: {config.method} {config.path} with params: {kwargs}")

                # Collect all parameters
                all_params = {}

                # Add path parameters
                for param in path_params:
                    if param.name in kwargs:
                        all_params[param.name] = kwargs[param.name]

                # Add query parameters
                for param in query_params:
                    if param.name in kwargs:
                        all_params[param.name] = kwargs[param.name]

                # Handle body parameters
                if body_params:
                    try:
                        body_data = await request.json()
                        logger.debug(f"Received body data: {body_data}")
                        for param in body_params:
                            if param.name in body_data:
                                all_params[param.name] = body_data[param.name]
                            elif not param.required and param.default is not None:
                                all_params[param.name] = param.default
                    except json.JSONDecodeError:
                        if any(p.required for p in body_params):
                            logger.warning("Invalid JSON in request body")
                            raise HTTPException(status_code=400, detail="Invalid JSON in request body")

                # Add defaults for optional parameters not provided
                for param in config.parameters:
                    if param.name not in all_params and not param.required and param.default is not None:
                        all_params[param.name] = param.default

                # Validate parameters
                for param in config.parameters:
                    if param.name in all_params:
                        value = all_params[param.name]

                        # Enum validation
                        if param.enum is not None and value not in param.enum:
                            logger.warning(f"Invalid enum value for {param.name}: {value}, allowed: {param.enum}")
                            raise HTTPException(
                                status_code=422,
                                detail=f"Invalid value for {param.name}. Allowed values: {', '.join(param.enum)}"
                            )

                        # Min/Max validation for numeric types
                        if param.type in ["integer", "float"]:
                            if param.min is not None and value < param.min:
                                logger.warning(f"Value {value} for {param.name} is below minimum {param.min}")
                                raise HTTPException(
                                    status_code=422,
                                    detail=f"Value for {param.name} must be at least {param.min}"
                                )
                            if param.max is not None and value > param.max:
                                logger.warning(f"Value {value} for {param.name} is above maximum {param.max}")
                                raise HTTPException(
                                    status_code=422,
                                    detail=f"Value for {param.name} must be at most {param.max}"
                                )

                # Render MQTT topic with variables
                topic = config.mqtt_topic.format(**all_params)

                # Render payload template with Jinja2
                template = Template(config.payload_template)
                # Add template context with custom functions and filters
                template_context = {
                    **all_params,
                    'now': lambda: datetime.now().isoformat(),
                }
                # Render template
                payload = template.render(**template_context)

                # Fix Python boolean representation (True/False -> true/false) for JSON compatibility
                payload = payload.replace(': True', ': true').replace(': False', ': false')

                # Validate JSON
                payload_json = json.loads(payload)

                # Publish to MQTT
                await self.mqtt_manager.publish(
                    topic=topic,
                    payload=payload,
                    qos=config.qos,
                    retain=config.retain
                )

                logger.info(f"Request handled successfully: {config.method} {config.path} -> {topic}")
                return {
                    "status": "published",
                    "topic": topic,
                    "payload": payload_json
                }

            except HTTPException:
                # Re-raise HTTPExceptions (like validation errors) without modification
                raise
            except KeyError as e:
                logger.warning(f"Missing required parameter: {e}")
                raise HTTPException(status_code=400, detail=f"Missing required parameter: {e}")
            except json.JSONDecodeError as e:
                logger.error(f"Invalid JSON in payload template: {e}")
                raise HTTPException(status_code=500, detail=f"Invalid JSON in payload template: {e}")
            except Exception as e:
                logger.error(f"Internal error handling request: {e}", exc_info=True)
                raise HTTPException(status_code=500, detail=f"Internal error: {str(e)}")

        # Build parameter annotations dynamically
        parameters = {}
        annotations = {}

        # Add query parameters
        for param in query_params:
            param_type = self._get_python_type(param.type)
            if param.required:
                parameters[param.name] = Query(..., description=f"Query parameter: {param.name}")
            else:
                parameters[param.name] = Query(default=param.default, description=f"Query parameter: {param.name}")
            annotations[param.name] = param_type

        # Add path parameters
        for param in path_params:
            param_type = self._get_python_type(param.type)
            parameters[param.name] = Path(..., description=f"Path parameter: {param.name}")
            annotations[param.name] = param_type

        # Update function signature
        sig = inspect.signature(endpoint)
        new_params = [sig.parameters['request'], sig.parameters['api_key']]

        for param_name, param_default in parameters.items():
            new_params.append(
                inspect.Parameter(
                    param_name,
                    inspect.Parameter.POSITIONAL_OR_KEYWORD,
                    default=param_default,
                    annotation=annotations.get(param_name, Any)
                )
            )

        endpoint.__signature__ = sig.replace(parameters=new_params)
        endpoint.__annotations__ = annotations

        # Add route to router
        method = config.method.lower()
        route_decorator = getattr(self.router, method)
        route_decorator(config.path, summary=f"{config.method} {config.path}")(endpoint)

    def _get_python_type(self, type_str: str) -> type:
        """Convert string type to Python type"""
        type_map = {
            "string": str,
            "integer": int,
            "float": float,
            "boolean": bool
        }
        return type_map.get(type_str, str)
