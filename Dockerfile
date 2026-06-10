FROM python:3.11-slim AS builder
WORKDIR /build
RUN pip install --no-cache-dir pip==25.0.1
COPY requirements.txt .
RUN pip install --no-cache-dir --user -r requirements.txt

FROM python:3.11-slim
WORKDIR /app
COPY --from=builder /root/.local /root/.local
COPY alembic.ini .
COPY alembic/ alembic/
COPY app/ app/
COPY docker-entrypoint.sh .
ENV PATH=/root/.local/bin:$PATH
RUN chmod +x docker-entrypoint.sh
EXPOSE 8000
ENTRYPOINT ["./docker-entrypoint.sh"]