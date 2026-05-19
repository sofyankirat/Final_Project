# # Dockerfile
# FROM python:3.11-slim

# # Create non-root user (required by HuggingFace)
# RUN useradd -m -u 1000 user
# USER user
# ENV PATH="/home/user/.local/bin:$PATH"

# WORKDIR /app

# # Install dependencies
# COPY --chown=user requirements.txt .
# RUN pip install --no-cache-dir -r requirements.txt

# # Copy all project files
# COPY --chown=user . /app

# # Create necessary folders
# RUN mkdir -p models database logs

# # Expose port 7860 (required by HuggingFace)
# EXPOSE 7860

# # Run Flask with gunicorn
# CMD ["gunicorn", "--bind", "0.0.0.0:7860", "--timeout", "120", "app:app"]

# Read the doc: https://huggingface.co/docs/hub/spaces-sdks-docker
# you will also find guides on how best to write your Dockerfile

FROM python:3.9

RUN useradd -m -u 1000 user
USER user
ENV PATH="/home/user/.local/bin:$PATH"

WORKDIR /app
# This installs the graphics libraries OpenCV needs to survive
USER root
RUN apt-get update && apt-get install -y \
    libgl1 \
    libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*
USER user
COPY --chown=user ./requirements.txt requirements.txt
RUN pip install --no-cache-dir --upgrade -r requirements.txt

COPY --chown=user . /app
CMD ["gunicorn", "--bind", "0.0.0.0:7860", "--timeout", "120", "app:app"]