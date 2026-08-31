#!/bin/bash

echo "� MOTOSHOW CONTROLE - INICIANDO"

export FLASK_APP=run:app

# Executa migrações e admin em background (não bloqueia startup)
(
  sleep 2
  echo "📦 Executando migrações em background..."
  python -m flask db upgrade 2>&1 | head -5 || true
  
  echo "👤 Configurando administrador..."
  python -m flask ensure-admin 2>&1 | head -3 || true
  
  echo "✓ Setup background concluído"
) &

# Inicia Gunicorn imediatamente
echo "⏳ Gunicorn iniciando..."
exec gunicorn \
  --bind 0.0.0.0:${PORT:-10000} \
  --workers 1 \
  --threads 4 \
  --timeout 120 \
  --access-logfile - \
  --error-logfile - \
  run:app
