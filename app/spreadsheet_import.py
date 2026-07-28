from datetime import datetime, timedelta
from pathlib import Path
from xml.etree import ElementTree as ET
from zipfile import ZipFile

from app import db
from app.models import City, ImmobilizedMotorcycle

SHEET_NS = {"x": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}
REL_NS = {"r": "http://schemas.openxmlformats.org/package/2006/relationships"}
RELATIONSHIP_ID = (
    "{http://schemas.openxmlformats.org/officeDocument/2006/relationships}id"
)
STATUS_MAP = {
    "SOLICITAÇÕES DE GARANTIA": "Solicitações de garantia",
    "AGUARD. CHEGADA DAS PEÇAS": "Aguardando chegada das peças",
    "AGUARDANDO APRO. SEGURO": "Aguardando aprovação do seguro",
}


def _node_text(node):
    return "".join(
        part.text or "" for part in node.findall(".//x:t", SHEET_NS)
    )


def _excel_date(value):
    if not value:
        return None
    return (datetime(1899, 12, 30) + timedelta(days=float(value))).date()


def read_motoshow_workbook(file_path):
    """Lê registros do modelo Motoshow sem alterar a planilha original."""
    with ZipFile(Path(file_path)) as archive:
        shared_root = ET.fromstring(archive.read("xl/sharedStrings.xml"))
        shared = [
            _node_text(item)
            for item in shared_root.findall("x:si", SHEET_NS)
        ]
        workbook = ET.fromstring(archive.read("xl/workbook.xml"))
        rels = ET.fromstring(archive.read("xl/_rels/workbook.xml.rels"))
        targets = {
            rel.attrib["Id"]: rel.attrib["Target"]
            for rel in rels.findall("r:Relationship", REL_NS)
        }

        records = []
        city_names = []
        for sheet in workbook.findall("x:sheets/x:sheet", SHEET_NS):
            city_name = sheet.attrib["name"]
            if city_name.upper() == "PAINEL GERAL":
                continue
            city_names.append(city_name)
            target = targets[sheet.attrib[RELATIONSHIP_ID]].lstrip("/")
            if not target.startswith("xl/"):
                target = f"xl/{target}"
            root = ET.fromstring(archive.read(target))

            for row in root.findall("x:sheetData/x:row", SHEET_NS):
                row_number = int(row.attrib["r"])
                if row_number < 6:
                    continue
                values = {}
                for cell in row.findall("x:c", SHEET_NS):
                    column = "".join(
                        character
                        for character in cell.attrib["r"]
                        if character.isalpha()
                    )
                    value_node = cell.find("x:v", SHEET_NS)
                    value = value_node.text if value_node is not None else ""
                    if value and cell.attrib.get("t") == "s":
                        value = shared[int(value)]
                    inline = cell.find("x:is", SHEET_NS)
                    if inline is not None:
                        value = _node_text(inline)
                    values[column] = value or ""

                if not values.get("A", "").strip():
                    continue
                records.append(
                    {
                        "source_key": f"PLANILHA:{city_name}:{row_number}",
                        "city_name": city_name,
                        "model": values["A"].strip(),
                        "chassis": values.get("B", "").strip().upper(),
                        "reason": values.get("C", "").strip(),
                        "status": STATUS_MAP.get(
                            values.get("D", "").strip().upper(),
                            values.get("D", "").strip().title(),
                        ),
                        "expected_date": _excel_date(values.get("E")),
                        "entry_date": _excel_date(values.get("F")),
                        "responsible": values.get("I", "").strip() or None,
                        "notes": values.get("J", "").strip() or None,
                    }
                )
    return city_names, records


def import_motoshow_workbook(file_path):
    city_names, records = read_motoshow_workbook(file_path)
    cities = {}
    for name in city_names:
        city = City.query.filter(
            db.func.lower(City.name) == name.lower()
        ).first()
        if city is None:
            city = City(name=name)
            db.session.add(city)
            db.session.flush()
        cities[name] = city

    created = 0
    skipped = 0
    for record in records:
        if ImmobilizedMotorcycle.query.filter_by(
            service_order=record["source_key"]
        ).first():
            skipped += 1
            continue
        if not record["entry_date"]:
            raise ValueError(
                f"Data de entrada ausente em {record['source_key']}."
            )
        motorcycle = ImmobilizedMotorcycle(
            city=cities[record["city_name"]],
            client="Não informado na planilha",
            model=record["model"],
            plate="S/PLACA",
            chassis=record["chassis"] or "Não informado",
            service_order=record["source_key"],
            reason=record["reason"] or "Não informado na planilha",
            entry_date=record["entry_date"],
            expected_date=record["expected_date"] or record["entry_date"],
            status=record["status"] or "Não informado",
            responsible=record["responsible"],
            notes=record["notes"],
        )
        db.session.add(motorcycle)
        created += 1

    db.session.commit()
    return {"created": created, "skipped": skipped, "cities": len(city_names)}
