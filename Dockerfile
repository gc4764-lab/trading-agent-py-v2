# Dockerfile
FROM python:3.10-slim

# Install system dependencies
RUN apt-get update && apt-get install -y \
gcc \
g++ \
curl \
&& rm -rf /var/lib/apt/lists/*

# Install Ollama
RUN curl -fsSL https://ollama.com/install.sh | sh

# Set working directory
WORKDIR /app

# Copy requirements
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application files
COPY . .

# Create directories
RUN mkdir -p reports data logs

# Expose ports
EXPOSE 8000

# Set environment variables
ENV PYTHONUNBUFFERED=1
ENV DATABASE_PATH=/app/data/trading_agent.db

# Run the application
CMD ["python", "trading_agent.py"]
