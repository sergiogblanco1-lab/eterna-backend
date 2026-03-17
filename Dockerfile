FROM python:3.10-slim

WORKDIR /app

# 🔥 INSTALAR FFMPEG (OBLIGATORIO)
RUN apt-get update && apt-get install -y ffmpeg && apt-get clean

# instalar dependencias
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# copiar proyecto
COPY . .

# ejecutar app
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "10000"]
