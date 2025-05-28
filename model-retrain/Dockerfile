FROM python:3.9-slim

WORKDIR /app

# Copy requirements and install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy source code
COPY src/ ./src/

# Create directories for data and models
RUN mkdir -p /data/raw /models /shared-models

# Expose port
EXPOSE 8080

# Run the retrain service
CMD ["python", "src/retrain_service.py"]