# Render-ready Dockerfile - build OpenHands from source (Python 3.12)
FROM python:3.12-slim

ARG OPENHANDS_REPO=https://github.com/All-Hands-AI/OpenHands.git
ARG OPENHANDS_REF=main

ENV PYTHONUNBUFFERED=1 \
    PORT=3001

# System packages needed for building wheels and common libs
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential git curl ca-certificates libpq-dev \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# upgrade pip tooling (use latest pip for better resolver)
RUN pip install --upgrade pip setuptools wheel

# Copy constraints file into image
COPY constraints.txt /tmp/constraints.txt

# Clone the OpenHands source into /tmp/openhands
WORKDIR /tmp
RUN git clone --depth 1 --branch ${OPENHANDS_REF} ${OPENHANDS_REPO} /tmp/openhands

# Install OpenHands from source using constraints to force consistent opentelemetry versions
WORKDIR /tmp/openhands
RUN pip install --upgrade pip setuptools wheel && \
    pip install --no-cache-dir --constraint /tmp/constraints.txt --prefer-binary -e .

# Ensure a runtime server is available (uvicorn fallback)
RUN pip install --no-cache-dir "uvicorn[standard]"

# Clean up git metadata to reduce final image size (optional)
RUN rm -rf /tmp/openhands/.git

WORKDIR /app
EXPOSE 3001

HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=3 \
  CMD curl -f http://localhost:${PORT:-3001}/health || exit 1

CMD sh -c 'python -m openhands --http-server --host 0.0.0.0 --port ${PORT:-3001}'
