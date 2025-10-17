# Imagen base estable y liviana
FROM python:3.11-slim

# Logs sin buffer + no escribir .pyc
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

# Directorio de trabajo
WORKDIR /app

# Dependencias del sistema (compilación básica + libmagic para mimetypes)
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libmagic1 \
    git \
 && rm -rf /var/lib/apt/lists/*

# ---- (OPCIONAL pero recomendado) PREINSTALAR TORCH CPU ----
# Evita compilar y acelera el build:
# Si tu requirements NO trae torch, lo instalamos aquí para usar el wheel CPU oficial.
RUN pip install --no-cache-dir --upgrade pip setuptools wheel
RUN pip install --no-cache-dir --index-url https://download.pytorch.org/whl/cpu torch

# Copiamos requirements y los instalamos
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copiamos el código
COPY . .

# Puerto (Railway asigna $PORT; exponemos 8000 dentro del contenedor)
ENV PORT=8000

# Comando de arranque (Railway usará este CMD del contenedor)
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
