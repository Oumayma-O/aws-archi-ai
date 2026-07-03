FROM python:3.12-slim AS base

WORKDIR /app

# Install curl for health check and graphviz for diagram rendering
RUN apt-get update && apt-get install -y --no-install-recommends curl graphviz \
    && rm -rf /var/lib/apt/lists/*

# Install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Ensure agents/ and agentcore/ directories are included
# (they are already part of COPY . . but we verify they exist)
RUN test -d /app/agents && test -d /app/agentcore

# Expose Streamlit port
EXPOSE 8501

# Health check for ECS
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD curl -f http://localhost:8501/_stcore/health || exit 1

# Default: local Strands execution (ECS Fargate fallback mode)
ENV AGENTCORE_ENABLED=false
ENV AGENTCORE_ENDPOINT=""
ENV SESSION_TABLE_NAME=architect-sessions

# Run Streamlit
ENTRYPOINT ["streamlit", "run", "app.py", "--server.port=8501", "--server.address=0.0.0.0"]
