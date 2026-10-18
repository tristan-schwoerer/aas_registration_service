# Registration service container.
#
# The shared AAS data-model package (ADR-016) is the `aas-model` submodule; it
# is not on a public index, so the build installs it from there. Initialize the
# submodules first:
#
#     git submodule update --init --recursive
#     docker build -t registration-service .
FROM python:3.11-slim

WORKDIR /app

# The model installs first so its layer is cached across service changes.
COPY aas-model ./aas-model/
COPY requirements.txt .
RUN pip install --no-cache-dir ./aas-model \
    && pip install --no-cache-dir -r requirements.txt

COPY . .

# Note: the AAS configs are asset-side (AP2030-UNS) and are mounted at
# /app/configs at runtime (see the compose files).

ENV PYTHONUNBUFFERED=1

# Default command runs the registration service as the MQTT registration listener
# (deep merge → AAS → post to BaSyx). Override via docker-compose.yml.
CMD ["python", "registration-service.py", "listen"]
