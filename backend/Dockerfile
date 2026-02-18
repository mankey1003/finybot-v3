FROM python:3.12-slim

# System libs required by pikepdf (libqpdf) and pdfplumber (poppler)
RUN apt-get update && apt-get install -y --no-install-recommends \
    libqpdf-dev \
    poppler-utils \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Cloud Run expects the service to listen on PORT env var (default 8080)
ENV PORT=8080
EXPOSE 8080

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8080", "--workers", "1"]
