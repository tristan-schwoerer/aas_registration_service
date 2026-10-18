# Registration service container.
#
# The shared AAS data-model package (ADR-016, `aas-model`) is not on a public
# index yet, so the build installs it from the sibling submodule, passed as the
# named build context `aas_model` (the compose files do this with
# additional_contexts). Standalone:
#
#     docker build --build-context aas_model=../aas-model -t registration-service .
FROM python:3.11-slim

WORKDIR /app

# The vendored model installs first so nothing pulls the stale remote package.
COPY --from=aas_model . ./_aas_model/
COPY requirements.txt .
RUN pip install --no-cache-dir ./_aas_model \
    && pip install --no-cache-dir -r requirements.txt

# Copy the service (requires submodules to be initialized first:
#   git submodule update --init --recursive
# so that MQTTSchemas is present)
COPY . .

# Note: the AAS configs are asset-side (AP2030-UNS) and are mounted at
# /app/configs at runtime (see the compose files).

ENV PYTHONUNBUFFERED=1

# Default command runs the registration service as the MQTT registration listener
# (deep merge → AAS → post to BaSyx). Override via docker-compose.yml.
CMD ["python", "registration-service.py", "listen"]
