FROM python:3.11-slim

# System deps for OpenCV headless, Open3D (EGL/OSMesa), and build tools for detectron2
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    git \
    libgl1-mesa-glx \
    libegl1-mesa \
    libglib2.0-0 \
    libgomp1 \
    libsm6 \
    libxext6 \
    libxrender1 \
    libosmesa6 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install PyTorch CPU-only first (smaller image, no CUDA)
RUN pip install --no-cache-dir \
    torch torchvision --index-url https://download.pytorch.org/whl/cpu

# Install detectron2 from source
RUN pip install --no-cache-dir --no-build-isolation \
    'git+https://github.com/facebookresearch/detectron2.git'

# Install remaining Python deps
COPY requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code and model weights
COPY hold-detector/ /app/hold-detector/

# Set working directory to hold-detector so relative paths work
WORKDIR /app/hold-detector

# Cloud Run provides PORT env var (default 8080)
ENV PORT=8080

# Hint Open3D to use EGL for headless rendering
ENV OPEN3D_CPU_RENDERING=true

CMD uvicorn api.main:app --host 0.0.0.0 --port $PORT
