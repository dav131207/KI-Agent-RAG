# --- Builder stage for the React frontend ---
FROM node:20-slim AS frontend-builder

WORKDIR /app/frontend
COPY frontend/package*.json ./
RUN npm ci

COPY frontend/ ./
RUN npm run build


# --- Production stage for the FastAPI backend ---
FROM python:3.11-slim

WORKDIR /app

# Install system dependencies for Pillow.
RUN apt-get update && apt-get install -y --no-install-recommends \
    libjpeg-dev zlib1g-dev \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies.
COPY backend/requirements.txt ./backend/
RUN pip install --no-cache-dir -r backend/requirements.txt

# Copy backend code.
COPY backend/ ./backend/

# Copy built frontend into the project so it can be served statically.
COPY --from=frontend-builder /app/frontend/dist ./frontend/dist

ENV PYTHONUNBUFFERED=1
ENV WATERMARK_PATH=/app/backend/assets/watermark.png

EXPOSE 8000

WORKDIR /app/backend
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
