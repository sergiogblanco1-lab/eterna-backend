# =========================
# BASE
# =========================
FROM python:3.11-slim

# =========================
# SISTEMA (para vídeo/audio)
# =========================
RUN apt-get update && apt-get install -y ffmpeg && rm -rf /var/lib/apt/lists/*

# =========================
# APP
# =========================
WORKDIR /app

# Copiar dependencias
COPY requirements.txt .

# Instalar dependencias
RUN pip install --no-cache-dir -r requirements.txt

# Copiar todo el proyecto
COPY . .

# =========================
# PUERTO
# =========================
ENV PORT=10000

# =========================
# RUN (CLAVE 🔥)
# =========================
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "10000"]
