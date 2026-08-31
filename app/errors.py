"""Error handlers para tratamento gracioso de falhas de banco de dados."""

from flask import jsonify
import sys
import traceback


def register_error_handlers(app):
    """Registra handlers para erros comuns."""
    
    @app.errorhandler(500)
    def internal_error(error):
        """Handle 500 errors com stack trace no stderr."""
        print(f"\n❌ 500 ERROR: {error}", file=sys.stderr)
        traceback.print_exc(file=sys.stderr)
        
        return jsonify({
            "error": "Erro interno do servidor",
            "status": "error"
        }), 500
    
    @app.errorhandler(503)
    def service_unavailable(error):
        """Handle 503 errors."""
        return jsonify({
            "error": "Serviço temporariamente indisponível",
            "status": "unavailable"
        }), 503
