# AllHaven backend — FastAPI + PostgreSQL (production image)
FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

# Install deps first for better layer caching.
COPY requirements.txt ./
RUN pip install --upgrade pip && pip install -r requirements.txt

COPY . .

# Local Drive storage lives here (mount a volume in production).
RUN mkdir -p /data/drive
ENV DRIVE_STORAGE_DIR=/data/drive

EXPOSE 8000

# Apply migrations, then start the API. DATABASE_URL etc. come from the environment.
CMD ["sh", "-c", "alembic upgrade head && uvicorn app.main:app --host 0.0.0.0 --port 8000"]
