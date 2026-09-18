FROM python:3.11-slim

WORKDIR /app

# Create non-root user
RUN addgroup --system appgroup && adduser --system --ingroup appgroup appuser

# Install uv then install requirements with parallel downloads
COPY requirements.txt .
RUN pip install --no-cache-dir uv && uv pip install --system --no-cache -r requirements.txt

# Copy source code, frontend assets, and test samples
COPY app /app/app
COPY sample_cases /app/sample_cases
COPY static /app/static

# Set permissions
RUN chown -R appuser:appgroup /app
USER appuser

# Expose API port
EXPOSE 8000

# Container healthcheck
HEALTHCHECK --interval=30s --timeout=5s --start-period=5s --retries=3 \
    CMD python -c "import urllib.request; sys_exit = 0 if urllib.request.urlopen('http://localhost:8000/health').getcode() == 200 else 1; exit(sys_exit)"

# Launch service
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
