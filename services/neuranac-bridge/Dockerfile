FROM python:3.12-slim AS builder

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir --target=/install -r requirements.txt

FROM python:3.12-slim

RUN groupadd -r neuranac && useradd -r -g neuranac -d /app -s /sbin/nologin neuranac

WORKDIR /app

COPY --from=builder /install /usr/local/lib/python3.12/site-packages
COPY . .

RUN chown -R neuranac:neuranac /app

USER neuranac

EXPOSE 8090

HEALTHCHECK --interval=10s --timeout=5s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8090/health')" || exit 1

CMD ["python", "-m", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8090"]
