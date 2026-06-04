FROM python:3.11-slim

WORKDIR /app

# Install system deps
RUN apt-get update && apt-get install -y gcc libpq-dev && rm -rf /var/lib/apt/lists/*

# Copy requirements first (for layer caching)
COPY requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r /app/requirements.txt

# Copy source
COPY src/ /app/src/
COPY scripts/ /app/scripts/
COPY railway.json /app/

# Set Python path
ENV PYTHONPATH=/app/src

# Verify schedule is installed
RUN python -c "import schedule; print('schedule installed successfully')"

# Run the grader service
CMD ["python", "/app/scripts/grader_service.py"]
