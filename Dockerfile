# Use a lightweight Python image
FROM python:3.12.11-slim

# Set environment variables for Python
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

# Set working directory inside container
WORKDIR /app

# Install any system packages you might eventually need (like curl)
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
 && apt-get clean \
 && rm -rf /var/lib/apt/lists/*

# Copy requirements first for better caching
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY main.py .
COPY core ./core
COPY clients ./clients
COPY webapp ./webapp
COPY config.yaml.template config.yaml

# Create data directory
RUN mkdir -p data

# Set default command to run your app
CMD ["python", "main.py"]