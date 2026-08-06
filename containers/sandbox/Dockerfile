FROM python:3.11-slim

# Install system dependencies, Node.js (for frontend builds), and curl
RUN apt-get update && apt-get install -y \
    curl \
    build-essential \
    git \
    procps \
    iproute2 \
    && curl -fsSL https://deb.nodesource.com/setup_20.x | bash - \
    && apt-get install -y nodejs \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# Pre-install some common Python data science and web tools to speed up the agent
RUN pip install --no-cache-dir \
    flask \
    fastapi \
    uvicorn \
    requests \
    numpy \
    pandas

WORKDIR /workspace

CMD ["sleep", "infinity"]
