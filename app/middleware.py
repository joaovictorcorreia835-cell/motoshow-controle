"""Middleware para tratamento de banco de dados indisponível."""

from flask import render_template_string
from sqlalchemy.exc import OperationalError
import re


INITIALIZING_HTML = """
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Inicializando...</title>
    <style>
        body {
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", "Roboto", "Oxygen", "Ubuntu", sans-serif;
            display: flex;
            align-items: center;
            justify-content: center;
            height: 100vh;
            margin: 0;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        }
        .container {
            text-align: center;
            color: white;
        }
        h1 { font-size: 2em; margin: 0 0 1em 0; }
        p { font-size: 1.1em; margin: 0 0 2em 0; opacity: 0.9; }
        .spinner {
            display: inline-block;
            width: 40px;
            height: 40px;
            border: 4px solid rgba(255, 255, 255, 0.3);
            border-radius: 50%;
            border-top-color: white;
            animation: spin 1s linear infinite;
        }
        @keyframes spin { to { transform: rotate(360deg); } }
    </style>
    <meta http-equiv="refresh" content="3">
</head>
<body>
    <div class="container">
        <h1>🚀 Inicializando Sistema</h1>
        <p>Aguarde enquanto estamos preparando o banco de dados...</p>
        <div class="spinner"></div>
        <p style="margin-top: 2em; font-size: 0.9em;">
            Esta página será atualizada automaticamente
        </p>
    </div>
</body>
</html>
"""


def register_db_middleware(app):
    """Registra middleware para detectar banco indisponível."""
    
    @app.before_request
    def check_database():
        """Verifica se o banco está disponível antes de processar requisição."""
        # Skip para rotas que não precisam de DB
        from flask import request
        if request.path in ['/healthz', '/static/<path:filename>']:
            return
        
        try:
            from app import db
            # Tenta uma query simples
            db.session.execute("SELECT 1")
        except (OperationalError, Exception) as e:
            error_msg = str(e)
            # Se for erro de conexão, retorna página de inicialização
            if any(err in error_msg for err in ['could not translate', 'connection refused', 'Connection refused']):
                return INITIALIZING_HTML, 503
