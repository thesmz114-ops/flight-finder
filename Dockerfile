FROM mcr.microsoft.com/playwright/python:v1.50.0-noble

WORKDIR /app

# Install Python deps
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Playwright is already installed in this image, but ensure browsers are there
RUN playwright install chromium

# Copy app
COPY . .

# Expose port
EXPOSE ${PORT:-5555}

# Run with gunicorn
CMD gunicorn --workers 1 --threads 4 --timeout 120 --bind 0.0.0.0:${PORT:-5555} app:app
