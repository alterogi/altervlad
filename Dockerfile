FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY bot.py logic.py soul.md ./

ENV PYTHONUNBUFFERED=1
ENV PERMISSIONS_FILE=/app/data/permissions.json
ENV USAGE_FILE=/app/data/usage.json
ENV DEPLOY_INFO_FILE=/app/data/deployed_info.json
ENV DEPLOYED_SHA_FILE=/app/data/.deployed_sha
ENV LAST_ANNOUNCED_FILE=/app/data/.last_announced_sha


CMD ["python", "bot.py"]
