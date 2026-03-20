# ── Stage 1: Build React UI ──────────────────────────────────────────────────
FROM node:20-alpine AS ui-builder
WORKDIR /app/ui
COPY ui/package.json ui/package-lock.json* ./
RUN npm install
COPY ui/ ./
RUN npm run build

# ── Stage 2: Python API ───────────────────────────────────────────────────────
FROM python:3.11-slim AS final
WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    libxml2-dev libxslt-dev \
    # Playwright/Chromium system dependencies
    libnss3 libatk1.0-0 libatk-bridge2.0-0 libcups2 libdrm2 \
    libxkbcommon0 libxcomposite1 libxdamage1 libxfixes3 libxrandr2 \
    libgbm1 libasound2 libpango-1.0-0 libpangocairo-1.0-0 \
    && rm -rf /var/lib/apt/lists/*

COPY pyproject.toml .
COPY src/ src/
RUN pip install --no-cache-dir -e ".[playwright]" \
    && playwright install chromium --with-deps
# Copy the built React app so FastAPI can serve it
COPY --from=ui-builder /app/ui/dist ui/dist

RUN mkdir -p data/feeds

EXPOSE 8000

CMD ["python", "-m", "rss_generator.main"]
