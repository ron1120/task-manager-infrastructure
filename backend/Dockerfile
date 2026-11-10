FROM python:3.11-slim

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# Current build tools: the ones shipped in the base image carry known CVEs (pip, setuptools, wheel).
# No compiler or system libraries are needed: psycopg2-binary ships its own, and bcrypt ships wheels.
COPY requirements.txt .
RUN pip install --no-cache-dir pip==26.3 setuptools==84.2.1 wheel==0.48.0 \
    && pip install --no-cache-dir -r requirements.txt \
    # ensurepip's bundled copy of setuptools is old, never used at runtime, and scanners report it: remove it.
    && find /usr/local/lib -path '*/ensurepip/_bundled/*.whl' -delete

COPY . .

# Run as a normal user (numeric id), not root.
RUN useradd --uid 10001 --create-home appuser && chown -R 10001 /app
USER 10001

EXPOSE 8000

HEALTHCHECK --interval=15s --timeout=5s --start-period=30s --retries=5 \
    CMD ["python", "-c", "import urllib.request as u; u.urlopen('http://127.0.0.1:8000/health', timeout=4)"]

CMD ["sh", "-c", "alembic upgrade head && uvicorn app.main:app --host 0.0.0.0 --port 8000"]
