FROM python:3.12-slim AS builder

# Prevent Python from buffering stdout/stderr
ENV PYTHONUNBUFFERED=1

# Set working directory
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    build-essential \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Copy dependency files first (for caching)
COPY requirements.txt ./

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy the rest of the project
COPY . .

FROM python:3.12-slim AS runner

ENV PYTHONUNBUFFERED=1
WORKDIR /app

# Copy dependencies and app code from builder
COPY --from=builder /usr/local /usr/local
COPY --from=builder /app /app

# Expose Django’s default port
EXPOSE 8000

# Collect static files (optional, if you use static)
RUN python manage.py collectstatic --noinput || true

# Run Django app (Gunicorn recommended for production)
CMD ["gunicorn", "kalbe_be.wsgi:application", "--bind", "0.0.0.0:8000"]
