# Use official Playwright Python image (has Chromium + deps)
FROM mcr.microsoft.com/playwright/python:v1.47.0-focal

# Set work directory
WORKDIR /app

# Copy requirements and install
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy rest of the code
COPY . .

# Environment variables will be set on the platform, but we keep defaults
ENV PORT=8000

# Expose port (for docs only; actual port is decided by platform)
EXPOSE 8000

# Start FastAPI app
CMD ["sh", "-c", "uvicorn app:app --host 0.0.0.0 --port ${PORT:-8000}"]
