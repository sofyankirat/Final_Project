FROM python:3.10-slim-bookworm

# Set working directory in container
WORKDIR /app

# Install system dependencies (including OpenGL and GLib needed by OpenCV/Ultralytics)
# Removed build-essential to prevent downloading massive compilation dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    libgl1 \
    libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*

# Copy front-end requirements first to leverage Docker cache
COPY front-end/requirements.txt /app/front-end/requirements.txt

# Install PyTorch CPU first to avoid heavy GPU/CUDA downloads and reduce memory consumption
RUN pip install --no-cache-dir torch torchvision --index-url https://download.pytorch.org/whl/cpu

# Install remaining requirements
RUN pip install --no-cache-dir -r /app/front-end/requirements.txt

# Copy all required codebase parts into the container
COPY front-end /app/front-end
COPY Recommendation_System_Data /app/Recommendation_System_Data
COPY Smart-Attendance-System /app/Smart-Attendance-System

# Expose port (Railway automatically injects PORT environment variable)
EXPOSE 5000

# Set environment variables
ENV PYTHONUNBUFFERED=1
ENV FLASK_APP=app.py

# Set working directory to front-end for executing the app
WORKDIR /app/front-end

# Run the Flask application using Gunicorn, binding to the port assigned by Railway with threads support for WebSockets
CMD gunicorn --bind 0.0.0.0:$PORT --timeout 120 --threads 8 --worker-class gthread app:app
