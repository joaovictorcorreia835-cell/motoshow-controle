import os

import click
from flask import Flask, jsonify
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager
from flask_migrate import Migrate
from flask_wtf.csrf import CSRFProtect
from sqlalchemy import text, event
from sqlalchemy.pool import Pool
from dotenv import load_dotenv
from werkzeug.middleware.proxy_fix import ProxyFix

load_dotenv()

db = SQLAlchemy()
login_manager = LoginManager()
migrate = Migrate()
csrf = CSRFProtect()

login_manager.login_view = "auth.login"
login_manager.login_message_category = "warning"


def create_app(test_config=None):
    app = Flask(__name__, instance_relative_config=False)
    app.config.from_object("config.Config")

    if test_config is not None:
        app.config.update(test_config)

    if app.testing:
        app.config.setdefault("WTF_CSRF_ENABLED", False)
        app.config["WTF_CSRF_ENABLED"] = test_config.get(
            "WTF_CSRF_ENABLED", False
        ) if test_config else False

    if (
        app.config["APP_ENV"] == "production"
        and app.config["SECRET_KEY"] == "change-this-secret-key"
    ):
        raise RuntimeError("SECRET_KEY segura é obrigatória em produção.")

    # Configure connection pooling for production
    db_uri = app.config["SQLALCHEMY_DATABASE_URI"]
    if db_uri.startswith(("postgresql://", "postgresql+psycopg2://")):
        # PostgreSQL: use pool with pre-ping and recycling
        app.config.setdefault("SQLALCHEMY_ENGINE_OPTIONS", {
            "pool_pre_ping": True,      # Verifica conexão antes de usar
            "pool_recycle": 300,         # Recicla conexão a cada 5 min
            "pool_size": 5,              # Conexões no pool
            "max_overflow": 10,          # Conexões extras permitidas
            "connect_args": {
                "connect_timeout": 10,   # Timeout de 10s na conexão
                "keepalives": 1,
                "keepalives_idle": 30,
            }
        })

    if app.config["APP_ENV"] == "production":
        app.config.update(
            SESSION_COOKIE_SECURE=True,
            REMEMBER_COOKIE_SECURE=True,
            PREFERRED_URL_SCHEME="https",
        )
        app.wsgi_app = ProxyFix(
            app.wsgi_app, x_for=1, x_proto=1, x_host=1
        )

    db.init_app(app)
    migrate.init_app(app, db)
    login_manager.init_app(app)
    csrf.init_app(app)

    # Log database configuration on startup
    with app.app_context():
        db_uri = app.config.get("SQLALCHEMY_DATABASE_URI", "")
        if db_uri.startswith(("postgresql://", "postgresql+psycopg2://")):
            # Safe logging without password
            try:
                from urllib.parse import urlparse
                parsed = urlparse(db_uri)
                safe_uri = f"{parsed.scheme}://{parsed.username}@{parsed.hostname}:{parsed.port or 5432}/{parsed.database}"
                print(f"✓ Database configured: {safe_uri}")
            except:
                print(f"✓ Database configured (PostgreSQL)")
        elif db_uri.startswith("sqlite:"):
            print(f"✓ Database configured: SQLite (local)")
        
        # Log connection pooling config
        engine_opts = app.config.get("SQLALCHEMY_ENGINE_OPTIONS", {})
        if engine_opts:
            print(f"  - Pool size: {engine_opts.get('pool_size', 'default')}")
            print(f"  - Pool pre-ping: {engine_opts.get('pool_pre_ping', False)}")

    from app.auth import auth_bp
    from app.main import main_bp
    from app.motorcycles import motorcycles_bp

    app.register_blueprint(auth_bp)
    app.register_blueprint(main_bp)
    app.register_blueprint(motorcycles_bp)

    @app.get("/healthz")
    def healthz():
        # Sempre retorna 200 se o app está rodando
        # O banco pode estar inicializando ainda
        try:
            db.session.execute(text("SELECT 1"))
            status = "ok"
        except Exception:
            # Banco indisponível, mas app está alive
            status = "degraded"
        return jsonify(status=status), 200

    @app.cli.command("init-db")
    def init_db():
        """Cria as tabelas da aplicação."""
        db.create_all()
        click.echo("Banco de dados inicializado.")

    @app.cli.command("create-admin")
    @click.option("--name", prompt="Nome")
    @click.option("--email", prompt="E-mail")
    @click.password_option()
    def create_admin(name, email, password):
        """Cria o administrador inicial."""
        from app.models import User

        email = email.strip().lower()
        db.create_all()
        if User.query.filter_by(email=email).first():
            raise click.ClickException("Já existe um usuário com este e-mail.")
        user = User(name=name.strip(), email=email, role="admin")
        user.set_password(password)
        db.session.add(user)
        db.session.commit()
        click.echo(f"Administrador {email} criado.")

    @app.cli.command("import-spreadsheet")
    @click.argument(
        "file_path", type=click.Path(exists=True, dir_okay=False, path_type=str)
    )
    def import_spreadsheet(file_path):
        """Importa o modelo Controle de Motos Imobilizadas."""
        from app.spreadsheet_import import import_motoshow_workbook

        result = import_motoshow_workbook(file_path)
        click.echo(
            f"{result['created']} motos importadas; "
            f"{result['skipped']} já existentes; "
            f"{result['cities']} cidades processadas."
        )

    @app.cli.command("ensure-admin")
    def ensure_admin():
        """Cria o administrador inicial usando variáveis do ambiente."""
        from app.models import User

        email = os.environ.get("BOOTSTRAP_ADMIN_EMAIL", "").strip().lower()
        password = os.environ.get("BOOTSTRAP_ADMIN_PASSWORD", "")
        name = os.environ.get(
            "BOOTSTRAP_ADMIN_NAME", "Gestão Motoshow"
        ).strip()
        if not email or not password:
            click.echo("Administrador inicial não configurado; ignorando.")
            return
        if len(password) < 12:
            raise click.ClickException(
                "BOOTSTRAP_ADMIN_PASSWORD deve ter pelo menos 12 caracteres."
            )
        user = User.query.filter_by(email=email).first()
        if user:
            user.name = name
            user.role = "admin"
            user.city_id = None
            user.set_password(password)
            db.session.commit()
            click.echo(f"Administrador {email} sincronizado.")
            return
        user = User(name=name, email=email, role="admin")
        user.set_password(password)
        db.session.add(user)
        db.session.commit()
        click.echo(f"Administrador {email} criado.")

    return app
