FROM python:3.11-slim

# System deps for OpenCV, Open3D (EGL/OSMesa), psycopg2, and detectron2 build
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    git \
    libgl1 \
    libglx-mesa0 \
    libegl1 \
    libglib2.0-0 \
    libgomp1 \
    libsm6 \
    libxext6 \
    libxrender1 \
    libosmesa6 \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install PyTorch CPU-only (no CUDA, smaller image)
RUN pip install --no-cache-dir \
    torch torchvision --index-url https://download.pytorch.org/whl/cpu

# Install detectron2 from source
RUN pip install --no-cache-dir --no-build-isolation \
    'git+https://github.com/facebookresearch/detectron2.git'

# Install remaining Python deps
COPY requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY database/ /app/database/
COPY hold-detector/ /app/hold-detector/

# Both packages must be importable
ENV PYTHONPATH=/app:/app/hold-detector

# Cloud Run provides PORT (default 8080)
ENV PORT=8080

# Open3D headless rendering via OSMesa
ENV OPEN3D_CPU_RENDERING=true

CMD uvicorn database.server:app --host 0.0.0.0 --port $PORT
