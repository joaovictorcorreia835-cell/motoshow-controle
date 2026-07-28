import os
import tempfile
import unittest
from datetime import date

from app import create_app, db
from app.models import City, ImmobilizedMotorcycle, User


class ImmobilizedMotorcycleTestCase(unittest.TestCase):
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
            campinas = City(name="Campinas")
            sorocaba = City(name="Sorocaba")
            admin = User(name="Admin", email="admin@test.com", role="admin")
            admin.set_password("admin123")
            user = User(
                name="Campinas", email="user@test.com", role="city_user", city=campinas
            )
            user.set_password("cidade123")
            db.session.add_all([campinas, sorocaba, admin, user])
            db.session.commit()
            self.campinas_id = campinas.id
            self.sorocaba_id = sorocaba.id

    def tearDown(self):
        with self.app.app_context():
            db.session.remove()
            db.drop_all()
        os.unlink(self.db_path)

    def login(self, email="admin@test.com", password="admin123"):
        return self.client.post(
            "/auth/login", data={"email": email, "password": password}
        )

    def valid_data(self, **changes):
        data = {
            "city_id": str(self.campinas_id),
            "client": "Maria Silva",
            "model": "Honda CG 160",
            "plate": "abc1d23",
            "chassis": "9C2KC2200RR000001",
            "service_order": "OS-1001",
            "reason": "Aguardando peça do motor",
            "entry_date": "2026-07-20",
            "expected_date": "2026-07-30",
            "status": "Aguardando peças",
            "responsible": "João Oficina",
            "notes": "Prioridade para entrega",
        }
        data.update(changes)
        return data

    def create_record(self, city_id=None):
        with self.app.app_context():
            motorcycle = ImmobilizedMotorcycle(
                city_id=city_id or self.campinas_id,
                client="Cliente Original",
                model="Yamaha Fazer",
                plate="DEF4G56",
                chassis="9C6RG5010R0000001",
                service_order="OS-2002",
                reason="Diagnóstico",
                entry_date=date(2026, 7, 21),
                expected_date=date(2026, 7, 31),
                status="Aguardando diagnóstico",
            )
            db.session.add(motorcycle)
            db.session.commit()
            return motorcycle.id

    def test_create_motorcycle(self):
        self.login()
        response = self.client.post(
            "/motos-imobilizadas/nova",
            data=self.valid_data(),
            follow_redirects=True,
        )
        self.assertEqual(response.status_code, 200)
        self.assertIn("cadastrada com sucesso".encode(), response.data)
        with self.app.app_context():
            motorcycle = ImmobilizedMotorcycle.query.one()
            self.assertEqual(motorcycle.city_id, self.campinas_id)
            self.assertEqual(motorcycle.plate, "ABC1D23")
            self.assertEqual(motorcycle.responsible, "João Oficina")
            self.assertEqual(motorcycle.notes, "Prioridade para entrega")

    def test_edit_motorcycle(self):
        motorcycle_id = self.create_record()
        self.login()
        response = self.client.post(
            f"/motos-imobilizadas/{motorcycle_id}/editar",
            data=self.valid_data(
                client="Cliente Editado",
                status="Em manutenção",
                responsible="Maria Técnica",
                notes="Peça recebida",
            ),
            follow_redirects=True,
        )
        self.assertIn("atualizada com sucesso".encode(), response.data)
        with self.app.app_context():
            motorcycle = db.session.get(ImmobilizedMotorcycle, motorcycle_id)
            self.assertEqual(motorcycle.client, "Cliente Editado")
            self.assertEqual(motorcycle.status, "Em manutenção")
            self.assertEqual(motorcycle.responsible, "Maria Técnica")
            self.assertEqual(motorcycle.notes, "Peça recebida")

    def test_delete_motorcycle(self):
        motorcycle_id = self.create_record()
        self.login()
        response = self.client.post(
            f"/motos-imobilizadas/{motorcycle_id}/excluir",
            follow_redirects=True,
        )
        self.assertIn("excluída com sucesso".encode(), response.data)
        with self.app.app_context():
            self.assertIsNone(db.session.get(ImmobilizedMotorcycle, motorcycle_id))

    def test_city_user_is_forced_to_own_city_on_create(self):
        self.login("user@test.com", "cidade123")
        response = self.client.post(
            "/motos-imobilizadas/nova",
            data=self.valid_data(city_id=str(self.sorocaba_id)),
            follow_redirects=True,
        )
        self.assertEqual(response.status_code, 200)
        with self.app.app_context():
            motorcycle = ImmobilizedMotorcycle.query.one()
            self.assertEqual(motorcycle.city_id, self.campinas_id)

    def test_city_user_cannot_edit_or_delete_another_city(self):
        motorcycle_id = self.create_record(self.sorocaba_id)
        self.login("user@test.com", "cidade123")
        edit_response = self.client.get(
            f"/motos-imobilizadas/{motorcycle_id}/editar"
        )
        delete_response = self.client.post(
            f"/motos-imobilizadas/{motorcycle_id}/excluir"
        )
        self.assertEqual(edit_response.status_code, 404)
        self.assertEqual(delete_response.status_code, 404)
        with self.app.app_context():
            self.assertIsNotNone(
                db.session.get(ImmobilizedMotorcycle, motorcycle_id)
            )

    def test_invalid_dates_do_not_create_record(self):
        self.login()
        response = self.client.post(
            "/motos-imobilizadas/nova",
            data=self.valid_data(expected_date="2026-07-19"),
            follow_redirects=True,
        )
        self.assertIn("previsão não pode ser anterior".encode(), response.data)
        with self.app.app_context():
            self.assertEqual(ImmobilizedMotorcycle.query.count(), 0)


if __name__ == "__main__":
    unittest.main()
