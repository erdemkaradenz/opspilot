# ==========================================
# AŞAMA 1: BUILDER (Derleme ve Hazırlık)
# ==========================================
FROM python:3.10-slim AS builder

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    POETRY_VERSION=2.0.1

WORKDIR /app

# Sadece Builder aşamasında Poetry'yi kuruyoruz
RUN pip install --no-cache-dir "poetry==$POETRY_VERSION" poetry-plugin-export

# Sadece bağımlılık dosyalarını kopyala (Layer Caching için)
COPY pyproject.toml poetry.lock ./

# Docker içindeki Poetry sürümüyle kilit dosyasını senkronize et (Lokal sürüm farklarını ezmek için)
RUN poetry lock

# Mimarın Hamlesi: Poetry'i kullanarak kilitli ve güvenilir bir requirements.txt üret
RUN poetry export -f requirements.txt --output requirements.txt --without-hashes

# C derleyicilerini kur ve wheel'ları (tekerlekleri) derle
RUN apt-get update && apt-get install -y --no-install-recommends gcc build-essential libpq-dev \
    && pip wheel --no-cache-dir --no-deps --wheel-dir /usr/src/app/wheels -r requirements.txt

# ==========================================
# AŞAMA 2: RUNNER (Üretim İmajı - Poetry'siz ve Hafif)
# ==========================================
FROM python:3.10-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

# Güvenlik Kilidi: Yetkisiz kullanıcı
RUN addgroup --system opsgroup && adduser --system --group opsuser

# Sadece çalışmak için gereken PostgreSQL kütüphanesi
RUN apt-get update && apt-get install -y --no-install-recommends libpq5 \
    && rm -rf /var/lib/apt/lists/*

# Builder aşamasından SADECE derlenmiş paketleri (wheels) ve requirements.txt'yi al
# DİKKAT: Poetry burada yok!
COPY --from=builder /usr/src/app/wheels /wheels
COPY --from=builder /app/requirements.txt .

# Paketleri kur ve wheel klasörünü silerek imajı minimum boyuta indir
RUN pip install --no-cache /wheels/* \
    && rm -rf /wheels requirements.txt

# Uygulama kodlarını içeri al
COPY . .

# Dosya sahipliğini yetkisiz kullanıcıya devret
RUN chown -R opsuser:opsgroup /app

USER opsuser
EXPOSE 8000

# Önce şema güncellenir, sonra tohumlama yapılır, en son web sunucusu ayağa kalkar!
CMD ["sh", "-c", "alembic upgrade head && python seed.py && uvicorn main:app --host 0.0.0.0 --port 8000"]