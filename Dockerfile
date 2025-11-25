FROM python:3.11-slim

ENV DEBIAN_FRONTEND=noninteractive \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

# SO deps: build chain, MySQL client, Cairo (pycairo), Pillow (jpeg/zlib/freetype)
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    pkg-config \
    default-libmysqlclient-dev \
    libcairo2-dev \
    libjpeg62-turbo-dev \
    zlib1g-dev \
    libfreetype6-dev \
    wget \
    gnupg \
    ca-certificates \
    libatk1.0-0 \
    libcups2 \
    libdbus-1-3 \
    libxkbcommon0 \
    libgtk-3-0 \
    libnss3 \
    libxcomposite1 \
    libxdamage1 \
    libxrandr2 \
    libasound2 \
 && rm -rf /var/lib/apt/lists/*

RUN python -m pip install --upgrade pip setuptools wheel

COPY requirements2.txt .
RUN pip install --no-cache-dir -r requirements2.txt

# ⬇️ INSTALAR PLAYWRIGHT + CHROMIUM DENTRO DEL CONTENEDOR
RUN python -m playwright install chromium --with-deps

COPY . .

EXPOSE 8000
CMD ["python", "manage.py", "runserver", "0.0.0.0:8000"]
