#!/usr/bin/env python
"""Startup script para Render - aguarda DB e executa migrações."""

import os
import sys
import time
import subprocess
from pathlib import Path

# Adiciona o diretório do projeto ao path
project_dir = Path(__file__).parent
sys.path.insert(0, str(project_dir))

os.environ.setdefault("FLASK_APP", "run:app")

print("\n" + "=" * 70)
print("🔧 MOTOSHOW CONTROLE - SISTEMA DE STARTUP")
print("=" * 70 + "\n")

# Check environment
print("📋 Verificando ambiente...")
print(f"   APP_ENV: {os.environ.get('APP_ENV', 'development')}")
print(f"   DATABASE_URL: {os.environ.get('DATABASE_URL', 'sqlite (local)')[:50]}...")
print()

# Wait for database with aggressive retry
print("⏳ Aguardando banco de dados (até 120s)...")
db_ready = False
for attempt in range(60):  # 120 segundos (2 segundos cada)
    try:
        # Clear any cached imports
        for mod in list(sys.modules.keys()):
            if mod.startswith('app') or mod.startswith('run'):
                del sys.modules[mod]
        
        from app import create_app, db
        
        app = create_app()
        with app.app_context():
            # Tenta conectar e validar
            result = db.session.execute("SELECT 1")
            db.session.close()
        
        print(f"   ✓ Banco de dados pronto! (tentativa {attempt + 1})")
        db_ready = True
        break
        
    except Exception as e:
        error_msg = str(e)
        if attempt < 59:
            # Mostra apenas a cada 5 tentativas para não poluir logs
            if (attempt + 1) % 5 == 0:
                print(f"   ⏳ Tentativa {attempt + 1}/60: {error_msg[:60]}...")
            time.sleep(2)
        else:
            print(f"   ✗ Falha após 120s: {error_msg}")
            print(f"      Continuando mesmo assim (migrações podem falhar)...\n")

if not db_ready:
    print("   ⚠️  Banco de dados indisponível, continuando...\n")
else:
    print()

# Run migrations (safely)
print("📦 Executando migrações...")
try:
    result = subprocess.run(
        [sys.executable, "-m", "flask", "db", "upgrade"],
        timeout=120,
        capture_output=True,
        text=True,
        cwd=str(project_dir)
    )
    
    if result.returncode == 0:
        print("   ✓ Migrações completadas com sucesso")
    elif "No new revisions" in result.stdout or "Target database" in result.stdout:
        print("   ✓ Banco já estava atualizado")
    else:
        error = result.stderr or result.stdout
        print(f"   ⚠️  Aviso: {error[:200]}")
        
except subprocess.TimeoutExpired:
    print("   ⚠️  Migrações demoraram muito (timeout), continuando...")
except Exception as e:
    print(f"   ⚠️  Migrações falharam: {e}")

print()

# Create/update admin
print("👤 Configurando administrador...")
try:
    result = subprocess.run(
        [sys.executable, "-m", "flask", "ensure-admin"],
        timeout=60,
        capture_output=True,
        text=True,
        cwd=str(project_dir)
    )
    
    output = result.stdout.strip() or "Configurado"
    print(f"   ✓ {output}")
    
except subprocess.TimeoutExpired:
    print("   ⚠️  Admin setup demoraram muito, continuando...")
except Exception as e:
    print(f"   ⚠️  Admin não configurado: {e}")

print()

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
