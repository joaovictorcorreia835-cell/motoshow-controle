"""Error handlers para tratamento gracioso de falhas de banco de dados."""

from flask import jsonify


def register_error_handlers(app):
    """Registra handlers para erros comuns."""
    
    @app.errorhandler(500)
    def internal_error(error):
        """Handle 500 errors com mensagem melhor."""
        import traceback
        error_msg = str(error)
        traceback.print_exc()
        
        # Se for erro de conexão com DB
        if "could not translate host name" in error_msg or "connection refused" in error_msg:
            return jsonify({
                "error": "Banco de dados indisponível",
                "status": "database_unavailable"
            }), 503
        
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
