# Stage 1: Build Frontend
FROM node:18-slim AS frontend-build
WORKDIR /app/frontend
COPY frontend/package*.json ./
RUN npm install
COPY frontend/ ./
RUN npm run build

# Stage 2: Runtime
FROM python:3.11-slim
WORKDIR /app

# Install system dependencies (including playwright requirements)
RUN apt-get update && apt-get install -y \
    curl \
    gnupg \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements and install
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
RUN playwright install chromium
RUN playwright install-deps chromium

# Copy app code
COPY . .

# Install the project itself as a package
RUN pip install .

# Copy built frontend from Stage 1
COPY --from=frontend-build /app/frontend/dist ./frontend/dist

# Expose port (Railway/Render use $PORT)
ENV PORT=8340
EXPOSE $PORT

# Run the server using uvicorn directly to ensure it picks up the app correctly
# We use shell form to expand the $PORT variable provided by Railway
CMD uvicorn akari_cli.server:app --host 0.0.0.0 --port ${PORT:-8340}
