# Build a partir da RAIZ do projeto:
#   docker build -f webapp/Dockerfile -t previsao .
# ---------- estagio 1: build do frontend ----------
FROM node:22-alpine AS front
WORKDIR /app
COPY webapp/frontend/package*.json ./
RUN npm ci
COPY webapp/frontend/ ./
RUN npm run build

# ---------- estagio 2: backend + estaticos ----------
FROM python:3.12-slim
WORKDIR /app

ENV PYTHONUNBUFFERED=1

COPY webapp/backend/requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

# backend (main.py, db.py, gerador_previsao.py, etc.)
# NOTA: previsao.py e ia_parser.py do webapp/backend/ foram removidos.
# Usamos os modulos raiz como fonte unica.
COPY webapp/backend/ ./

# modulos raiz — fonte unica, sem duplicatas
COPY previsao.py ./
COPY ia_parser.py ./

# frontend buildado
COPY --from=front /app/dist/ ./static/

ENV PREVISAO_SESSOES_DIR=/dados/sessoes
VOLUME /dados

EXPOSE 8000
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
