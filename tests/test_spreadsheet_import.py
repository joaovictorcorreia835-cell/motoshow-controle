import os
import tempfile
import unittest
from pathlib import Path

from app import create_app, db
from app.models import City, ImmobilizedMotorcycle
from app.spreadsheet_import import import_motoshow_workbook, read_motoshow_workbook


class SpreadsheetImportTestCase(unittest.TestCase):
    workbook_path = Path(
        r"C:\Users\User\Downloads\Controle_Motos_Imobilizadas_Motoshow.xlsx"
    )

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
        with self.app.app_context():
            db.create_all()

    def tearDown(self):
        with self.app.app_context():
            db.session.remove()
            db.drop_all()
        os.unlink(self.db_path)

    def test_reads_all_cities_and_records(self):
        cities, records = read_motoshow_workbook(self.workbook_path)
        self.assertEqual(len(cities), 9)
        self.assertEqual(len(records), 10)
        self.assertEqual(
            {record["city_name"] for record in records},
            {"Parauapebas", "Marabá"},
        )
        self.assertTrue(all(record["model"] for record in records))
        self.assertTrue(all(record["entry_date"] for record in records))

    def test_imports_every_record_without_duplicates(self):
        with self.app.app_context():
            first = import_motoshow_workbook(self.workbook_path)
            second = import_motoshow_workbook(self.workbook_path)
            self.assertEqual(first, {"created": 10, "skipped": 0, "cities": 9})
            self.assertEqual(second, {"created": 0, "skipped": 10, "cities": 9})
            self.assertEqual(City.query.count(), 9)
            self.assertEqual(ImmobilizedMotorcycle.query.count(), 10)
            sample = ImmobilizedMotorcycle.query.filter_by(
                city_id=City.query.filter_by(name="Parauapebas").one().id
            ).one()
            self.assertEqual(sample.model, "FACTOR 150 VERME. 25/25")
            self.assertEqual(sample.status, "Solicitações de garantia")
            self.assertEqual(sample.client, "Não informado na planilha")


if __name__ == "__main__":
    unittest.main()
