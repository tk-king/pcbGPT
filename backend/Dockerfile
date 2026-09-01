FROM python:3.11-slim-bookworm

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    UV_LINK_MODE=copy \
    UV_NO_CACHE=1

WORKDIR /app

RUN printf '%s\n' "deb http://deb.debian.org/debian bookworm-backports main" \
    > /etc/apt/sources.list.d/bookworm-backports.list \
    && apt-get update \
    && apt-get install -y --no-install-recommends \
    build-essential \
    ca-certificates \
    curl \
    git \
    ngspice \
    && apt-get install -y --no-install-recommends -t bookworm-backports \
    kicad \
    kicad-libraries \
    && rm -rf /var/lib/apt/lists/*

RUN pip install --no-cache-dir uv

COPY backend/pyproject.toml backend/uv.lock ./backend/
RUN cd backend && uv sync --frozen --no-install-project

COPY . .

RUN mkdir -p /app/runtime \
    && ln -sf /app/runtime/sessions.db /app/sessions.db \
    && ln -sf /app/runtime/custom_sessions.db /app/custom_sessions.db

EXPOSE 8000

CMD ["uv", "run", "--project", "backend", "--no-sync", "python", "-m", "backend.main"]
