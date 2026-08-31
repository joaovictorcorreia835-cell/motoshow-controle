#!/bin/bash

echo "MOTOSHOW CONTROLE - STARTUP"

export FLASK_APP=run:app

# Aguarda banco de dados estar pronto (até 60 segundos)
echo "Aguardando banco de dados..."
for i in {1..60}; do
  if python -c "from app import create_app, db; app = create_app(); app.app_context().push(); db.session.execute('SELECT 1')" 2>/dev/null; then
    echo "✓ Banco pronto!"
    break
  fi
  sleep 1
done

# Executa migrações
echo "Executando migrações..."
python -m flask db upgrade 2>&1 | head -3 || true

# Configura admin
echo "Configurando admin..."
python -m flask ensure-admin 2>&1 | head -1 || true

# Inicia Gunicorn
echo "Iniciando Gunicorn na porta ${PORT:-10000}..."
exec gunicorn \
  --bind 0.0.0.0:${PORT:-10000} \
  --workers 1 \
  --threads 4 \
  --timeout 120 \
  --access-logfile - \
  --error-logfile - \
  run:app
