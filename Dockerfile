FROM python:3.12-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY config.py espn_api.py community_bot.py community_editorial.py ./
COPY modules/__init__.py modules/security.py ./modules/
ENV PYTHONUNBUFFERED=1
CMD ["python", "community_bot.py"]
