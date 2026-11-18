FROM python:3.11-slim

WORKDIR /app

# quant core (astock_core) + MCP transport: public data APIs, pandas/numpy needed
RUN pip install --no-cache-dir "mcp>=1.2" "pandas>=2.0" "numpy>=1.24"

COPY server.py runner.py ./
COPY astock_core ./astock_core

# MCP stdio server: starts and responds to initialize/introspection over stdin/stdout
ENTRYPOINT ["python", "server.py"]
