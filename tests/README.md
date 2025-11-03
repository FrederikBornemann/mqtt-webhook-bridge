# Integration Tests

Integration tests for the MQTT-Webhook Bridge using Docker containers.

## Quick Start

```bash
# Start services, run tests, and cleanup
docker-compose -f docker-compose.test.yml up -d --build && \
sleep 10 && \
pytest tests/test_integration.py -v -s && \
docker-compose -f docker-compose.test.yml down
```

## Prerequisites

- Docker and Docker Compose
- Python 3.11+
- Dependencies from requirements.txt

## Running Tests

```bash
# Start services
docker-compose -f docker-compose.test.yml up -d --build

# Run tests
pytest tests/test_integration.py -v -s

# Stop services
docker-compose -f docker-compose.test.yml down
```

## Test Coverage

- API authentication (valid, invalid, missing)
- Health and service info endpoints
- Query, path, and body parameters
- Parameter validation (min, max, enum)
- MQTT message publishing with QoS and retain
- Jinja2 template rendering
- Concurrent request handling
- Multiple HTTP methods (GET, POST, PUT)

## Debugging

```bash
# View logs
docker-compose -f docker-compose.test.yml logs -f

# Monitor MQTT messages
docker exec mqtt-broker-test mosquitto_sub -t "test/#" -v

# Test manually
curl -X POST "http://localhost:8000/v1/test/simple?message=hello" \
  -H "X-API-Key: test-api-key-12345"
```
