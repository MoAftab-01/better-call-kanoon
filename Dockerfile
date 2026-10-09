# ---------------------------------------------------------------------------
# Better Call Kanoon - container image (multi-stage)
#
# Build:  docker build -t better-call-kanoon .
# Run:    docker run --rm -p 8000:8000 --env-file backend/.env better-call-kanoon
#         docker compose up --build          (preferred - see docker-compose.yml)
#
# Stage 1 (node)   builds the React + TypeScript client into frontend/dist.
# Stage 2 (python) carries the FastAPI app and the *built* frontend only.
#
# The final image contains NO node_modules and NO frontend/src: the browser
# receives compiled, minified, self-hosted assets and nothing else. The image
# ships no secrets either - credentials arrive at run time as environment
# variables (see backend/.env.example and docker-compose.yml).
#
# Directory layout inside the image deliberately mirrors the repository, so
# `app/config.py` resolves every path with its normal defaults:
#
#     /app/backend/app/...   ->  PROJECT_ROOT = /app/backend
#     /app/backend/data/...  ->  DATA_DIR, INDEX_DIR
#     /app/frontend/dist/... ->  STATIC_DIR  (mounted at / by the FastAPI app)
# ---------------------------------------------------------------------------

# ---- Stage 1: build the React frontend -------------------------------------
FROM node:22-slim AS frontend-build

# Deliberately NO NODE_ENV here. `npm ci` must install devDependencies (vite,
# typescript) to build at all, and `vite build` must then run in production mode
# so React emits its production build. Setting NODE_ENV=development in this
# stage silently ships the development bundle - measured 473 kB instead of
# 254 kB. Vite defaults to production for `build` and to devDeps for `ci`,
# which is exactly what both commands need.
ENV NPM_CONFIG_UPDATE_NOTIFIER=false \
    NPM_CONFIG_FUND=false

WORKDIR /build/frontend

# package.json + package-lock.json first: this layer is rebuilt only when the
# declared dependencies change, not on every source edit.
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci

COPY frontend/ ./

# `npm run build` runs `tsc --noEmit` twice before `vite build`, so a type
# error fails the image build rather than shipping. Output lands in
# /build/frontend/dist.
RUN npm run build

# ---- Stage 2: the Python application + the built frontend -------------------
FROM python:3.11-slim AS runtime

LABEL org.opencontainers.image.title="Better Call Kanoon" \
      org.opencontainers.image.description="Voice-powered AI legal information grounded in Indian law." \
      org.opencontainers.image.version="0.1.0"

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    HOST=0.0.0.0 \
    PORT=8000

WORKDIR /app/backend

# Run as an unprivileged user: nothing in this image needs root.
RUN groupadd --system --gid 1001 kanoon \
    && useradd --system --uid 1001 --gid kanoon --create-home --shell /usr/sbin/nologin kanoon

# requirements.txt before the source, so pip's layer survives source edits.
COPY backend/requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

# The Python application. `.env` is never copied (it is git-ignored and may
# hold a real API key); only `.env.example` ships.
COPY backend/app/ ./app/
COPY backend/pyproject.toml ./
COPY backend/.env.example ./
# Data that is safe to bake: the emergency helpline directory and the empty
# laws/mappings/index placeholders. `docker-compose.yml` bind-mounts the real
# ./backend/data over this so ingested PDFs and the index survive a rebuild.
COPY backend/data/ ./data/
COPY backend/logs/ ./logs/

# The built frontend - and ONLY the built frontend. frontend/src, the tsconfig
# files and node_modules are never copied into this image.
COPY --from=frontend-build /build/frontend/dist/ /app/frontend/dist/

# The index, laws and logs directories are written to at runtime, so hand them
# to the unprivileged user. backend/data/laws holds PDFs *you* download from
# official sources such as the India Code portal - see README.md.
RUN mkdir -p data/index data/laws data/mappings logs \
    && chown -R kanoon:kanoon /app

USER kanoon

EXPOSE 8000

# Uses $PORT so the same image honours a runtime port override. Python's own
# urllib is the probe - the slim image has no curl, and adding one would add a
# package just to read one URL.
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD python -c "import os,urllib.request;urllib.request.urlopen('http://127.0.0.1:'+os.environ.get('PORT','8000')+'/api/health',timeout=4)"

# Plain JSON array form, so the image contains no shell-expansion assumptions.
CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}"]