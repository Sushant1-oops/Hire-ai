FROM python:3.11-slim

# Install system dependencies (build-essential needed for some python packages like FAISS or standard C extensions)
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Hugging Face Spaces requires running as a non-root user
RUN useradd -m -u 1000 user
USER user
ENV HOME=/home/user \
    PATH=/home/user/.local/bin:$PATH \
    # Tell huggingface to cache models in the user's home directory so it has write access
    HF_HOME=/home/user/.cache/huggingface

WORKDIR $HOME/app

# Copy requirements and install
# We copy this first to leverage Docker layer caching
COPY --chown=user:user requirements.txt .

RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# Copy the backend code into the container
COPY --chown=user:user backend/ ./backend/

# Set working directory to the backend directory so relative paths work (like data/)
WORKDIR $HOME/app/backend

# Ensure data directory exists and is writable
RUN mkdir -p data

# Expose port 7860 which is the default for Hugging Face Spaces
EXPOSE 7860

# Run the FastAPI server on port 7860
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "7860"]
