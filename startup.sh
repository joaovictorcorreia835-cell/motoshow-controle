#!/bin/bash

export FLASK_APP=run:app

echo "Aguardando banco de dados..."
for i in {1..30}; do
    python -c "from app import create_app, db; app = create_app(); app.app_context().push(); db.session.execute('SELECT 1')" 2>/dev/null && break
    echo "Tentativa $i/30..."
    sleep 2
done

echo "Executando migrações..."
flask db upgrade --noinput || true

echo "Configurando administrador..."
flask ensure-admin || true

echo "Iniciando servidor..."
exec gunicorn --bind 0.0.0.0:${PORT:-5000} --workers 2 --threads 4 --timeout 120 run:app
