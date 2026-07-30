import os
import tempfile
import unittest
from datetime import date, timedelta

from app import create_app, db
from app.main import calculate_dashboard_metrics
from app.models import City, ImmobilizedMotorcycle, User


class DashboardTestCase(unittest.TestCase):
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
        self.today = date.today()
        with self.app.app_context():
            db.create_all()
            campinas = City(name="Campinas")
            sorocaba = City(name="Sorocaba")
            admin = User(name="Admin", email="admin@test.com", role="admin")
            admin.set_password("admin123")
            user = User(
                name="Campinas", email="user@test.com", role="city_user", city=campinas
            )
            user.set_password("cidade123")
            db.session.add_all([campinas, sorocaba, admin, user])
            db.session.flush()
            self.campinas_id = campinas.id
            self.sorocaba_id = sorocaba.id
            self._add_motorcycle(
                campinas, "Ana", "ABC1A11", 40, -2, "Aguardando peças"
            )
            self._add_motorcycle(
                campinas, "Bruno", "ABC2B22", 20, 2, "Em manutenção"
            )
            self._add_motorcycle(
                sorocaba, "Carla", "ABC3C33", -3, -1, "Aguardando diagnóstico"
            )
            self._add_motorcycle(
                sorocaba, "Daniel", "ABC4D44", 35, -5, "Finalizada"
            )
            db.session.commit()

    def _add_motorcycle(
        self, city, client, plate, entry_days_ago, expected_days, status
    ):
        db.session.add(
            ImmobilizedMotorcycle(
                city=city,
                client=client,
                model=f"Moto {client}",
                plate=plate,
                chassis=f"CHASSI-{plate}",
                service_order=f"OS-{plate}",
                reason=f"Motivo {client}",
                entry_date=self.today - timedelta(days=entry_days_ago),
                expected_date=self.today + timedelta(days=expected_days),
                status=status,
            )
        )

    def tearDown(self):
        with self.app.app_context():
            db.session.remove()
            db.drop_all()
        os.unlink(self.db_path)

    def login(self, email="admin@test.com", password="admin123"):
        self.client.post("/auth/login", data={"email": email, "password": password})

    def test_all_dashboard_calculations(self):
        with self.app.app_context():
            motorcycles = ImmobilizedMotorcycle.query.all()
            metrics = calculate_dashboard_metrics(motorcycles, self.today)
            self.assertEqual(metrics["total"], 4)
            self.assertEqual(metrics["overdue"], 2)
            self.assertEqual(metrics["average_days"], 23.8)
            self.assertEqual(
                metrics["by_city"], {"Campinas": 2, "Sorocaba": 2}
            )
            self.assertEqual(
                metrics["by_status"],
                {
                    "Aguardando diagnóstico": 1,
                    "Aguardando peças": 1,
                    "Em manutenção": 1,
                    "Finalizada": 1,
                },
            )

    def test_empty_dashboard_calculations(self):
        metrics = calculate_dashboard_metrics([], self.today)
        self.assertEqual(metrics["total"], 0)
        self.assertEqual(metrics["overdue"], 0)
        self.assertEqual(metrics["average_days"], 0)
        self.assertEqual(metrics["by_city"], {})
        self.assertEqual(metrics["by_status"], {})

    def test_search_and_status_filters_recalculate_metrics(self):
        self.login()
        search_response = self.client.get("/dashboard?q=Ana")
        self.assertIn(b'data-metric="total">1<', search_response.data)
        self.assertIn("Ana".encode(), search_response.data)
        self.assertIn(b"OS-ABC1A11", search_response.data)
        self.assertNotIn("Bruno".encode(), search_response.data)

        status_response = self.client.get(
            "/dashboard?status=Em+manutenção"
        )
        self.assertIn(b'data-metric="total">1<', status_response.data)
        self.assertIn("Bruno".encode(), status_response.data)

    def test_overdue_filter_recalculates_results(self):
        self.login()
        response = self.client.get("/dashboard?delay=overdue")
        self.assertIn(b'data-metric="total">2<', response.data)
        self.assertIn(b'data-metric="overdue">2<', response.data)
        self.assertIn("Ana".encode(), response.data)
        self.assertIn("Daniel".encode(), response.data)
        self.assertNotIn("Carla".encode(), response.data)

    def test_city_filter_and_city_user_scope(self):
        self.login()
        response = self.client.get(f"/dashboard?city_id={self.sorocaba_id}")
        self.assertIn(b'data-metric="total">2<', response.data)
        self.assertNotIn("Ana".encode(), response.data)
        self.assertIn("Carla".encode(), response.data)

        self.client.post("/auth/logout")
        self.login("user@test.com", "cidade123")
        scoped = self.client.get(f"/dashboard?city_id={self.sorocaba_id}")
        self.assertIn(b'data-metric="total">2<', scoped.data)
        self.assertIn("Ana".encode(), scoped.data)
        self.assertNotIn("Carla".encode(), scoped.data)


if __name__ == "__main__":
    unittest.main()
