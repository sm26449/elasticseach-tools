# Multi-stage build pentru optimizare
FROM python:3.9-alpine as builder

# Instalare dependințe de build
RUN apk add --no-cache gcc musl-dev libffi-dev

# Setare director de lucru
WORKDIR /build

# Copiere și instalare dependințe
COPY requirements.txt .
RUN pip install --no-cache-dir --user -r requirements.txt

# Imagine finală optimizată
FROM python:3.9-alpine

# Instalare doar runtime dependencies
RUN apk add --no-cache libffi

# Crearea unui utilizator non-root
RUN addgroup -g 1000 appuser && \
    adduser -D -u 1000 -G appuser appuser

# Setare director de lucru
WORKDIR /app

# Copiere dependințe Python din builder
COPY --from=builder --chown=appuser:appuser /root/.local /home/appuser/.local

# Copiere aplicație
COPY --chown=appuser:appuser main.py ./
COPY --chown=appuser:appuser requirements.txt ./

# Crearea directorului pentru eventuale fișiere statice
RUN mkdir -p /app/static && chown -R appuser:appuser /app

# Setare PATH pentru pachetele instalate local
ENV PATH=/home/appuser/.local/bin:$PATH

# Schimbare la utilizator non-root
USER appuser

# Expose port
EXPOSE 80

# Health check
HEALTHCHECK --interval=30s --timeout=3s --start-period=5s --retries=3 \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:80/health')" || exit 1

# Comandă pentru a rula aplicația
CMD ["python", "-m", "uvicorn", "main:app", "--host", "0.0.0.0", "--port", "80"]