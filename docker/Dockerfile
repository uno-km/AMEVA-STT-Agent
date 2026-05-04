FROM python:3.10-slim

WORKDIR /app

# Install system dependencies (CPU only)
RUN apt-get update && apt-get install -y \
    ffmpeg \
    build-essential \
    cmake \
    && rm -rf /var/lib/apt/lists/*

# Install python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy source code
COPY . .

# Default command: headless batch processor (TBD)
# For now, it just waits or runs the main script if we implement a headless mode
CMD ["python", "main.py"]
