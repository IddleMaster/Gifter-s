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
 && rm -rf /var/lib/apt/lists/*

# Herramientas de wheel modernas
RUN python -m pip install --upgrade pip setuptools wheel

COPY requirements2.txt .
RUN pip install --no-cache-dir -r requirements2.txt

COPY . .

EXPOSE 8000
CMD ["gunicorn", "--bind", ":8000", "--workers", "2", "myproject.wsgi:application"]