# Voice agent (#13): its own image, apart from the web app, so LiveKit and
# the provider SDKs never end up in the Django image and vice versa.
FROM python:3.13-slim AS base

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt

# Development and tests: dev tools on top, code comes in as a volume.
FROM base AS dev
COPY requirements-dev.txt .
RUN pip install -r requirements-dev.txt
COPY . .
CMD ["python", "-m", "mymvz_voice.agent", "dev"]

# Operation (#10): code baked in, no root.
FROM base AS prod
COPY . .
RUN useradd --system --no-create-home app
USER app
CMD ["python", "-m", "mymvz_voice.agent", "start"]
