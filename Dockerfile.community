FROM python:3.12-slim
WORKDIR /app
RUN apt-get update && apt-get install -y --no-install-recommends fonts-noto-cjk && rm -rf /var/lib/apt/lists/*
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY config.py espn_api.py community_bot.py community_editorial.py community_cover.py community_daily.py ./
COPY modules/__init__.py modules/security.py ./modules/
ENV PYTHONUNBUFFERED=1
CMD ["python", "community_bot.py"]
