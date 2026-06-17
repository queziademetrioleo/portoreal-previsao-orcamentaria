# Build a partir da RAIZ do projeto (~/PrevisaoOrcamentaria):
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

# biblioteca core (parsers + regras + IA)
COPY previsao.py ./
COPY ia_parser.py ./
# backend
COPY webapp/backend/main.py webapp/backend/gerador_previsao.py ./backend/
# frontend buildado -> servido pelo FastAPI
COPY --from=front /app/dist/ ./backend/static/

ENV PREVISAO_SESSOES_DIR=/dados/sessoes
ENV PYTHONPATH=/app
VOLUME /dados

EXPOSE 8000
WORKDIR /app/backend
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
