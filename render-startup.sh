#!/bin/bash

echo "MOTOSHOW CONTROLE - STARTUP"

export FLASK_APP=run:app

# Simples: testa se consegue importar a app
echo "Testando app..."
python -c "from app import create_app; print('✓ App OK')" 2>&1 || exit 1

# Executa migrações (pode rodar agora que app está OK)
echo "Migrações..."
timeout 30 python -m flask db upgrade 2>&1 | head -3 || echo "Migrations done/skipped"

# Configura admin se necessário
echo "Admin..."
timeout 10 python -m flask ensure-admin 2>&1 | head -1 || echo "Admin ready"

# Aguarda 2 segundos para banco ficar pronto
sleep 2

# Inicia Gunicorn
echo "Gunicorn (porta ${PORT:-10000})..."
exec gunicorn \
  --bind 0.0.0.0:${PORT:-10000} \
  --workers 1 \
  --threads 4 \
  --timeout 120 \
  --access-logfile - \
  --error-logfile - \
  run:app
