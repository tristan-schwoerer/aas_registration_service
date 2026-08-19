FROM python:3.11-slim

WORKDIR /app

# Copy requirements first for better caching
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy the service (requires submodules to be initialized first:
#   git submodule update --init --recursive
# so that third_party/aas_pydantic and MQTTSchemas are present)
COPY . .

# Note: the AAS configs are asset-side (AP2030-UNS) and are mounted at
# /app/configs at runtime (see the compose files).

ENV PYTHONUNBUFFERED=1

# Default command runs the registration service as the MQTT registration listener
# (deep merge → AAS → post to BaSyx). Override via docker-compose.yml.
CMD ["python", "registration-service.py", "listen"]
