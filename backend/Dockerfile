FROM python:3.12-slim
ARG PIP_INDEX_URL=https://pypi.org/simple
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PIP_DEFAULT_TIMEOUT=180 PIP_RETRIES=10 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 PIP_INDEX_URL=${PIP_INDEX_URL}
WORKDIR /app
# All dependencies ship as wheels for Python 3.12 — no apt packages needed.
# The cache mount keeps already-downloaded wheels if a slow connection interrupts the build.
COPY requirements.txt requirements-dev.txt ./
RUN --mount=type=cache,target=/root/.cache/pip \
    pip install -r requirements-dev.txt && \
    python -c "import fastapi, sqlalchemy, alembic, psycopg, pydantic, pandas, sklearn, bcrypt, jwt, openpyxl, httpx, pytest; print('backend dependencies OK')"
COPY . .
RUN useradd --create-home --uid 10001 tradeflow && chown -R tradeflow /app
USER tradeflow
EXPOSE 8000
HEALTHCHECK --interval=10s --timeout=5s --start-period=30s --retries=12 \
  CMD python -c "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://localhost:8000/api/health', timeout=4).status == 200 else 1)"
CMD ["sh", "./entrypoint.sh"]
