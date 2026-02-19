FROM python:3.11-slim

WORKDIR /app

# Install dependencies
COPY services/behavioral-mirror/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy the service itself
COPY services/behavioral-mirror/ .

# Copy backend modules (parsers, analyzers) needed by the service
COPY backend/ /app/backend/

RUN chmod +x startup.sh

CMD ["./startup.sh"]
