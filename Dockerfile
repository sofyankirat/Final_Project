FROM python:3.10-slim-bookworm

# Set working directory in container
WORKDIR /app

# Install system dependencies (including OpenGL and GLib needed by OpenCV/Ultralytics)
# Forced IPv4 to prevent slow IPv6 timeouts/resolution on Railway's container builder network
RUN apt-get -o Acquire::ForceIPv4=true update && apt-get -o Acquire::ForceIPv4=true install -y --no-install-recommends \
    libgl1 \
    libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*

# Copy pip IPv4 helper wrapper
COPY pip_ipv4.py /app/pip_ipv4.py

# Copy front-end requirements first to leverage Docker cache
COPY front-end/requirements.txt /app/front-end/requirements.txt

# Install PyTorch CPU first to avoid heavy GPU/CUDA downloads and reduce memory consumption
# We increase default timeout to 1000s and force IPv4 via our wrapper script to prevent connection drops
RUN python /app/pip_ipv4.py install --default-timeout 1000 --no-cache-dir "torch==2.0.1" "torchvision==0.15.2" "numpy==1.23.5" --index-url https://download.pytorch.org/whl/cpu

# Install remaining requirements
RUN python /app/pip_ipv4.py install --default-timeout 1000 --no-cache-dir -r /app/front-end/requirements.txt

# Copy all required codebase parts into the container
COPY front-end /app/front-end
COPY Recommendation_System_Data /app/Recommendation_System_Data
COPY Smart-Attendance-System /app/Smart-Attendance-System

# Train ML recommendation models inside the container to ensure scikit-learn version match
WORKDIR /app/front-end
RUN python train_recommendation_models.py

# Expose port (Railway automatically injects PORT environment variable)
EXPOSE 5000

# Set environment variables
ENV PYTHONUNBUFFERED=1
ENV FLASK_APP=app.py

# Set working directory to front-end for executing the app
WORKDIR /app/front-end

# Run the Flask application using Gunicorn, binding to the port assigned by Railway with threads support for WebSockets
CMD gunicorn --bind 0.0.0.0:$PORT --timeout 120 --threads 8 --worker-class gthread app:app
