FROM python:3.10-slim

# Set working directory in container
WORKDIR /app

# Install system dependencies (including OpenGL and GLib needed by OpenCV/Ultralytics)
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libgl1 \
    libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*

# Copy full requirements and install to include ML dependencies (monolith)
COPY requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r /app/requirements.txt

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

# Run the monolithic Flask application using Gunicorn (wsgi:app exposes the app)
CMD gunicorn --bind 0.0.0.0:$PORT --timeout 120 --threads 8 wsgi:app
