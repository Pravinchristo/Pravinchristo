FROM python:3.12-slim

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY agent ./agent
# Seed workspace; at runtime it is mounted as a volume so learned skills and memory persist.
COPY workspace ./workspace-seed

ENV PYTHONUNBUFFERED=1 AGENT_WORKSPACE=/app/workspace AGENT_DATA_DIR=/app/data
# Healthy while the supervisor's heartbeat is less than 2 minutes old.
HEALTHCHECK --interval=60s --timeout=5s --start-period=60s \
  CMD python -c "import time,sys; sys.exit(time.time()-int(open('/app/data/heartbeat').read())>120)"

CMD ["sh", "-c", "[ -f workspace/INSTRUCTIONS.md ] || cp -rn workspace-seed/. workspace/; exec python -m agent run"]
