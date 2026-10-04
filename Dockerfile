FROM python:3.11-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    g++ \
    make \
    libffi-dev \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first for better caching
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY main.py .
COPY sites.txt /data/sites.txt

# Create data directory for persistent storage
RUN mkdir -p /data

# Set environment variables
ENV PYTHONUNBUFFERED=1

# Run the bot
CMD ["python", "main.py", "--bot"]