import os
import tempfile
import unittest

from app import create_app, db
from app.models import City, User


class AuthenticationTestCase(unittest.TestCase):
    def setUp(self):
        fd, self.db_path = tempfile.mkstemp(suffix=".db")
        os.close(fd)
        self.app = create_app(
            {
                "TESTING": True,
                "SECRET_KEY": "test-secret",
                "SQLALCHEMY_DATABASE_URI": f"sqlite:///{self.db_path}",
            }
        )
        self.client = self.app.test_client()
        with self.app.app_context():
            db.create_all()
            sao_paulo = City(name="São Paulo")
            campinas = City(name="Campinas")
            admin = User(name="Admin", email="admin@test.com", role="admin")
            admin.set_password("admin123")
            city_user = User(
                name="Usuário Campinas",
                email="campinas@test.com",
                role="city_user",
                city=campinas,
            )
            city_user.set_password("cidade123")
            db.session.add_all([sao_paulo, campinas, admin, city_user])
            db.session.commit()

    def tearDown(self):
        with self.app.app_context():
            db.session.remove()
            db.drop_all()
        os.unlink(self.db_path)

    def login(self, email, password):
        return self.client.post(
            "/auth/login",
            data={"email": email, "password": password},
            follow_redirects=True,
        )

    def test_admin_login_sees_all_cities(self):
        response = self.login("admin@test.com", "admin123")
        self.assertEqual(response.status_code, 200)
        self.assertIn("Login efetuado com sucesso".encode(), response.data)
        self.assertIn("São Paulo".encode(), response.data)
        self.assertIn("Campinas".encode(), response.data)

    def test_city_user_login_only_sees_own_city(self):
        response = self.login("campinas@test.com", "cidade123")
        self.assertEqual(response.status_code, 200)
        self.assertIn("Campinas".encode(), response.data)
        self.assertNotIn("São Paulo".encode(), response.data)

    def test_city_user_cannot_access_admin(self):
        self.login("campinas@test.com", "cidade123")
        response = self.client.get("/admin/users")
        self.assertEqual(response.status_code, 403)

    def test_invalid_login_is_rejected(self):
        response = self.login("admin@test.com", "wrong")
        self.assertIn("Credenciais inválidas".encode(), response.data)
        self.assertNotIn("Cidades disponíveis".encode(), response.data)


if __name__ == "__main__":
    unittest.main()
