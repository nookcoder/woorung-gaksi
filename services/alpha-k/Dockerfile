FROM python:3.12-slim

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    git \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Copy dependency definition
COPY requirements.txt ./

# Install dependencies
RUN pip install --no-cache-dir --upgrade pip
RUN pip install --no-cache-dir -r requirements.txt --pre

# Copy source code
COPY . .

# Expose port
EXPOSE 8001

# Set environment variables
ENV PYTHONPATH=/app

# Run application
# Note: src/api_main.py has 'app' instance
CMD ["uvicorn", "src.api_main:app", "--host", "0.0.0.0", "--port", "8001", "--reload"]
