import os
import tempfile
import unittest

from app import create_app, db
from app.models import User
from config import _database_url


class ProductionConfigurationTestCase(unittest.TestCase):
    def setUp(self):
        fd, self.db_path = tempfile.mkstemp(suffix=".db")
        os.close(fd)

    def tearDown(self):
        if os.path.exists(self.db_path):
            os.unlink(self.db_path)

    def production_config(self, **changes):
        config = {
            "TESTING": True,
            "APP_ENV": "production",
            "SECRET_KEY": "a-secure-production-secret",
            "SQLALCHEMY_DATABASE_URI": f"sqlite:///{self.db_path}",
        }
        config.update(changes)
        return config

    def test_production_requires_secure_secret(self):
        with self.assertRaises(RuntimeError):
            create_app(
                self.production_config(
                    SECRET_KEY="change-this-secret-key"
                )
            )

    def test_health_check_and_secure_cookies(self):
        app = create_app(self.production_config())
        with app.app_context():
            db.create_all()
        response = app.test_client().get("/healthz")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json, {"status": "ok"})
        self.assertTrue(app.config["SESSION_COOKIE_SECURE"])

    def test_ensure_admin_command_is_idempotent(self):
        app = create_app(self.production_config())
        with app.app_context():
            db.create_all()
        runner = app.test_cli_runner()
        environment = {
            "BOOTSTRAP_ADMIN_NAME": "Gestão",
            "BOOTSTRAP_ADMIN_EMAIL": "gestao@render.test",
            "BOOTSTRAP_ADMIN_PASSWORD": "SenhaRender#2026",
        }
        first = runner.invoke(args=["ensure-admin"], env=environment)
        with app.app_context():
            user = User.query.one()
            user.set_password("senha-antiga")
            db.session.commit()
        second = runner.invoke(args=["ensure-admin"], env=environment)
        self.assertEqual(first.exit_code, 0)
        self.assertEqual(second.exit_code, 0)
        with app.app_context():
            self.assertEqual(User.query.count(), 1)
            self.assertTrue(
                User.query.one().check_password("SenhaRender#2026")
            )

    def test_render_postgres_url_is_normalized_for_psycopg2(self):
        previous = os.environ.get("DATABASE_URL")
        os.environ["DATABASE_URL"] = "postgresql://user:pass@host/db"
        try:
            self.assertEqual(
                _database_url(),
                "postgresql://user:pass@host/db",
            )
        finally:
            if previous is None:
                os.environ.pop("DATABASE_URL", None)
            else:
                os.environ["DATABASE_URL"] = previous


if __name__ == "__main__":
    unittest.main()
