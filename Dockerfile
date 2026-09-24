FROM node:22-slim AS frontend
WORKDIR /build
COPY frontend/package*.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build

FROM python:3.12-slim
WORKDIR /app
COPY backend/requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt && useradd -u 10001 app && mkdir /data && chown app /data
COPY backend/ ./
COPY --from=frontend /build/dist /app/public
ENV DATABASE_PATH=/data/observatory.sqlite STATIC_ROOT=/app/public PYTHONUNBUFFERED=1
USER app
EXPOSE 8080
CMD ["python", "service.py"]
