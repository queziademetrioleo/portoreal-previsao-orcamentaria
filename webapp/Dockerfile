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

COPY webapp/backend/requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

# backend completo (inclui previsao.py e ia_parser.py copiados)
COPY webapp/backend/ ./

# frontend buildado
COPY --from=front /app/dist/ ./static/

ENV PREVISAO_SESSOES_DIR=/dados/sessoes
VOLUME /dados

EXPOSE 8000
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
