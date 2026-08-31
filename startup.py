#!/usr/bin/env python
"""Startup script para Render - aguarda DB e executa migrações."""

import os
import sys
import time
import subprocess

os.environ.setdefault("FLASK_APP", "run:app")

print("\n" + "=" * 70)
print("🔧 MOTOSHOW CONTROLE - SISTEMA DE STARTUP")
print("=" * 70 + "\n")

# Check environment
print("📋 Verificando ambiente...")
print(f"   APP_ENV: {os.environ.get('APP_ENV', 'development')}")
db_url = os.environ.get('DATABASE_URL', 'sqlite (local)')
safe_db = db_url[:50] + '...' if len(db_url) > 50 else db_url
print(f"   DATABASE_URL: {safe_db}")
print()

# Try to connect to database
print("⏳ Aguardando banco de dados (até 120s)...")
db_ready = False
for attempt in range(60):  # 120 segundos (2 segundos cada)
    try:
        result = subprocess.run(
            [sys.executable, "-c", "from app import create_app, db; app = create_app(); ctx = app.app_context(); ctx.push(); db.session.execute('SELECT 1'); print('OK')"],
            capture_output=True,
            text=True,
            timeout=10
        )
        
        if result.returncode == 0 and "OK" in result.stdout:
            print(f"   ✓ Banco de dados pronto! (tentativa {attempt + 1})\n")
            db_ready = True
            break
            
    except Exception as e:
        pass
    
    if (attempt + 1) % 10 == 0:
        print(f"   ⏳ Tentativa {attempt + 1}/60...")
    
    time.sleep(2)

if not db_ready:
    print("   ⚠️  Banco indisponível, continuando mesmo assim...\n")
else:
    # Run migrations
    print("📦 Executando migrações...")
    try:
        result = subprocess.run(
            [sys.executable, "-m", "flask", "db", "upgrade"],
            timeout=120,
            capture_output=True,
            text=True
        )
        
        if result.returncode == 0 or "No new revisions" in result.stdout:
            print("   ✓ Migrações completadas\n")
        else:
            print(f"   ⚠️  {result.stderr[:100]}\n")
    except Exception as e:
        print(f"   ⚠️  Erro: {e}\n")

    # Create/update admin
    print("👤 Configurando administrador...")
    try:
        result = subprocess.run(
            [sys.executable, "-m", "flask", "ensure-admin"],
            timeout=60,
            capture_output=True,
            text=True
        )
        print(f"   ✓ {result.stdout.strip()}\n" if result.stdout else "   ✓ Configurado\n")
    except Exception as e:
        print(f"   ⚠️  {e}\n")

# Start server
port = os.environ.get("PORT", "5000")
print("=" * 70)
print(f"🚀 INICIANDO GUNICORN NA PORTA {port}")
print("=" * 70 + "\n")

try:
    os.execvp("gunicorn", [
        "gunicorn",
        f"--bind=0.0.0.0:{port}",
        "--workers=2",
        "--threads=4",
        "--timeout=120",
        "--access-logfile=-",
        "--error-logfile=-",
        "run:app"
    ])
except Exception as e:
    print(f"❌ Erro ao iniciar Gunicorn: {e}", file=sys.stderr)
    sys.exit(1)
