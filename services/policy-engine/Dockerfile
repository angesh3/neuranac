FROM python:3.12-slim AS builder
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

FROM python:3.12-slim
WORKDIR /app
COPY --from=builder /usr/local/lib/python3.12/site-packages /usr/local/lib/python3.12/site-packages
COPY --from=builder /usr/local/bin /usr/local/bin
COPY . .
# Generate gRPC stubs if proto files were copied into context
RUN python -c "\
import os, glob; \
from grpc_tools import protoc; \
os.makedirs('app/generated', exist_ok=True); \
open('app/generated/__init__.py','w').close(); \
protos = glob.glob('proto/*.proto'); \
[protoc.main(['','--proto_path=proto','--python_out=app/generated','--grpc_python_out=app/generated',p]) for p in protos]" 2>/dev/null || echo "Proto generation skipped (no proto files in context)"
RUN useradd -r -s /bin/false neuranac && chown -R neuranac:neuranac /app
USER neuranac
EXPOSE 8082 9091
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8082"]
