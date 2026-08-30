FROM python:3.11-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

# Las dependencias se instalan primero para aprovechar la caché de capas.
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# El bot no necesita privilegios: se ejecuta como usuario sin root.
RUN useradd --create-home --shell /bin/bash botuser \
    && mkdir -p /app/data \
    && chown -R botuser:botuser /app
USER botuser

VOLUME ["/app/data"]

CMD ["python", "main.py"]
