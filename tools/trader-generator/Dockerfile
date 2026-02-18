FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Configurable via environment variables
ENV TRADER_COUNT=10
ENV MIN_TRADES=15
ENV RANDOM_SEED=42
ENV OUTPUT_DIR=/data
ENV PORT=8000

# Create data volume mount point
RUN mkdir -p /data

# Entrypoint: generate CSVs, then start the file server
COPY entrypoint.sh .
RUN chmod +x entrypoint.sh

EXPOSE 8000

CMD ["./entrypoint.sh"]
