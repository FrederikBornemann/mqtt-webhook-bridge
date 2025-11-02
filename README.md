# MQTT-Webhook Bridge

A Python service that bridges HTTP webhooks to MQTT topics. Define webhooks in YAML that trigger MQTT messages with flexible templating.

## Quick Start

### Using Docker Compose

1. Create `docker-compose.yml`:

```yaml
services:
  webhook-bridge:
    image: ghcr.io/frederikbornemann/mqtt-webhook-bridge:latest
    ports:
      - "8000:8000"
    volumes:
      - ./config:/app/config
    environment:
      - CONFIG_PATH=/app/config/routes.yaml
```

2. Create `config/routes.yaml` (see Configuration below)

3. Start the service:

```bash
docker-compose up -d
```

4. Access API docs at [http://localhost:8000/docs](http://localhost:8000/docs)

### Using Docker

```bash
docker run -d \
  -p 8000:8000 \
  -v $(pwd)/config:/app/config \
  -e CONFIG_PATH=/app/config/routes.yaml \
  ghcr.io/frederikbornemann/mqtt-webhook-bridge:latest
```

## Configuration

Create `config/routes.yaml` to define webhooks and MQTT settings:

```yaml
mqtt:
  broker: "mqtt.example.com"  # MQTT broker hostname/IP
  port: 1883
  username: null              # Optional authentication
  password: null
  client_id: "webhook-bridge"
  keepalive: 60

# API version prefix for all routes (default: "v1")
api_version: "v1"

routes:
  - path: "/set_temperature"
    method: "POST"
    mqtt_topic: "command/set_temperature/{room}"
    parameters:
      - name: "room"
        type: "string"
        required: true
        location: "query"      # query, path, or body
      - name: "target"
        type: "float"
        required: true
        location: "query"
    payload_template: |
      {
        "room": "{{room}}",
        "target_temperature": {{target}}
      }
    qos: 1                     # MQTT QoS (0, 1, or 2)
    retain: false
```

### Parameter Options

**Types**: `string`, `integer`, `float`, `boolean`

**Locations**:
- `query`: URL parameters (`?room=kitchen`)
- `path`: Path variables (`/device/{id}`)
- `body`: JSON body fields

**Validation**:
- `required`: Boolean (default: true)
- `default`: Default value if not provided
- `enum`: List of allowed values
- `min`/`max`: Numeric range

### Payload Templates

Use Jinja2 syntax in `payload_template`:

```yaml
payload_template: |
  {
    "device": "{{device_id}}",
    "value": {{value if value else 0}},
    "status": "{{ 'on' if value > 0 else 'off' }}"
  }
```

## Examples

All routes are prefixed with the API version (default: `/v1/`).

### Basic Temperature Control

```bash
curl -X POST "http://localhost:8000/v1/set_temperature?room=bedroom&target=21.5"
```

Publishes to `command/set_temperature/bedroom`:
```json
{"room": "bedroom", "target_temperature": 21.5}
```

### Path + Body Parameters

Config:
```yaml
- path: "/device/{device_id}/control"
  method: "POST"
  mqtt_topic: "devices/{device_id}/cmd"
  parameters:
    - name: "device_id"
      type: "string"
      location: "path"
    - name: "state"
      type: "string"
      location: "body"
      enum: ["on", "off"]
```

Usage:
```bash
curl -X POST "http://localhost:8000/v1/device/sensor_01/control" \
  -H "Content-Type: application/json" \
  -d '{"state": "on"}'
```

## API Documentation

Interactive docs available at `/docs` when running:
- [http://localhost:8000/docs](http://localhost:8000/docs) - Swagger UI
- [http://localhost:8000/health](http://localhost:8000/health) - Health check

## Development

### Local Setup

```bash
# Install dependencies
pip install -r requirements.txt

# Run with hot-reload
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

### Testing

```bash
pytest
```