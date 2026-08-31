#!/bin/bash

echo "🔧 MOTOSHOW CONTROLE - STARTUP"

# Tenta migrações em background (sem bloquear)
(
  sleep 5
  echo "📦 Executando migrações em background..."
  FLASK_APP=run:app python -m flask db upgrade 2>/dev/null || true
  echo "✓ Migrações completadas"
  
  echo "👤 Configurando administrador..."
  FLASK_APP=run:app python -m flask ensure-admin 2>/dev/null || true
) &

# Inicia o Gunicorn imediatamente
echo "🚀 Iniciando Gunicorn..."
exec gunicorn \
  --bind 0.0.0.0:${PORT:-5000} \
  --workers 2 \
  --threads 4 \
  --timeout 120 \
  --access-logfile - \
  --error-logfile - \
  run:app
