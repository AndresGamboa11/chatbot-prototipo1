FROM python:3.11-slim

# Evita buffering
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

# Instala dependencias del sistema que sentence-transformers y chromadb necesitan
RUN apt-get update && apt-get install -y build-essential libmagic1 git && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .

# Instala dependencias Python (incluido torch)
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

ENV PORT=8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
