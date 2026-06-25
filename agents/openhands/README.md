# OpenHands Agent

A first-class autonomous execution agent for AI Engineering OS. OpenHands specializes in complex tasks requiring full-codebase analysis, debugging, and code review.

## What is this Agent?

OpenHands is an AI agent that can:
- Analyze and understand complex codebases
- Perform autonomous code execution
- Debug issues across multiple files
- Conduct code reviews
- Execute multi-step tasks independently

## Supported Methods

### Method A — Pull (RECOMMENDED)

Uses the official pre-built OpenHands Docker image from GitHub Container Registry.

**Pros:**
- Faster deployment (no build required)
- Pre-configured and tested
- Smaller image size (shared layers)
- Recommended for production use

**Usage:**
```bash
# Build with pull method
docker build -f agents/openhands/Dockerfile.pull -t openhands-agent .

# Or update docker-compose.yml to use:
# build:
#   context: ./agents/openhands
#   dockerfile: Dockerfile.pull
```

### Method B — Local Build

Clones and builds OpenHands directly from the official GitHub repository.

**Pros:**
- Full control over source code
- Can customize OpenHands before building
- Can use specific branches or commits
- No dependency on pre-built images

**Usage:**
```bash
# Build with local method
docker build -f agents/openhands/Dockerfile.local -t openhands-agent .

# Build with specific branch
docker build -f agents/openhands/Dockerfile.local \
    --build-arg OPENHANDS_BRANCH=v0.8.0 \
    -t openhands-agent .
```

## Source Information

| Property | Value |
|----------|-------|
| **Official Repository** | https://github.com/All-Hands-AI/OpenHands |
| **Public Registry** | ghcr.io/all-hands-ai/openhands |
| **License** | MIT |

## Switching Methods

To switch between methods:

1. **Method A (Pull) → Method B (Local):**
   ```bash
   # Edit the default Dockerfile or docker-compose.yml
   # Change FROM ghcr.io/all-hands-ai/openhands:latest
   # TO: build from Dockerfile.local
   ```

2. **Method B (Local) → Method A (Pull):**
   ```bash
   # Edit the default Dockerfile or docker-compose.yml
   # Change to build from Dockerfile.pull
   ```

## Default Dockerfile

The main `Dockerfile` in this directory uses **Method A (Pull)** by default.

To change the default, replace the content of `Dockerfile` with either:
- `Dockerfile.pull` content (Method A)
- `Dockerfile.local` content (Method B)

## Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `OPENAI_API_KEY` | OpenAI API key for LLM access | Required |
| `ANTHROPIC_API_KEY` | Anthropic API key | Optional |
| `SANDBOX_RUNTIME_CONTAINER_IMAGE` | Runtime container image | Uses default |

## Port Configuration

- **Port:** 3001
- **Protocol:** HTTP

## Health Check

All Dockerfiles include a health check:
```bash
curl http://localhost:3001/health
```

## Integration with AI Engineering OS

The OpenHands adapter in `adapter.py` connects to `http://openhands:3001` when running via docker-compose.
