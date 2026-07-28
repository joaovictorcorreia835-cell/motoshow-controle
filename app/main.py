from functools import wraps
from datetime import date, timedelta
from zipfile import BadZipFile

from flask import Blueprint, abort, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required
from sqlalchemy import or_

from app import db
from app.models import City, ImmobilizedMotorcycle, User
from app.motorcycles import STATUS_OPTIONS
from app.spreadsheet_import import import_motoshow_workbook

main_bp = Blueprint("main", __name__)
DELAY_DAYS = 30


def admin_required(view):
    @wraps(view)
    @login_required
    def wrapped(*args, **kwargs):
        if not current_user.is_admin:
            abort(403)
        return view(*args, **kwargs)

    return wrapped


@main_bp.route("/")
def index():
    return render_template("index.html")


@main_bp.route("/dashboard")
@login_required
def dashboard():
    cities = (
        City.query.order_by(City.name).all()
        if current_user.is_admin
        else ([current_user.city] if current_user.city else [])
    )
    query = ImmobilizedMotorcycle.query
    if not current_user.is_admin:
        query = query.filter(
            ImmobilizedMotorcycle.city_id == current_user.city_id
        )

    search = request.args.get("q", "").strip()
    city_id = request.args.get("city_id", type=int)
    status = request.args.get("status", "").strip()
    delay = request.args.get("delay", "").strip()
    today = date.today()
    delay_cutoff = today - timedelta(days=DELAY_DAYS)

    if search:
        term = f"%{search}%"
        query = query.filter(
            or_(
                ImmobilizedMotorcycle.client.ilike(term),
                ImmobilizedMotorcycle.model.ilike(term),
                ImmobilizedMotorcycle.plate.ilike(term),
                ImmobilizedMotorcycle.chassis.ilike(term),
                ImmobilizedMotorcycle.service_order.ilike(term),
                ImmobilizedMotorcycle.reason.ilike(term),
            )
        )
    if current_user.is_admin and city_id:
        query = query.filter(ImmobilizedMotorcycle.city_id == city_id)
    if status in STATUS_OPTIONS:
        query = query.filter(ImmobilizedMotorcycle.status == status)
    if delay == "overdue":
        query = query.filter(ImmobilizedMotorcycle.entry_date < delay_cutoff)
    elif delay == "on_time":
        query = query.filter(ImmobilizedMotorcycle.entry_date >= delay_cutoff)

    motorcycles = query.order_by(
        ImmobilizedMotorcycle.entry_date.desc()
    ).all()
    metrics = calculate_dashboard_metrics(motorcycles, today)
    return render_template(
        "dashboard.html",
        user=current_user,
        cities=cities,
        statuses=STATUS_OPTIONS,
        motorcycles=motorcycles,
        metrics=metrics,
        filters={
            "q": search,
            "city_id": city_id,
            "status": status,
            "delay": delay,
        },
        delay_days=DELAY_DAYS,
        today=today,
    )


def calculate_dashboard_metrics(motorcycles, today=None):
    today = today or date.today()
    total = len(motorcycles)
    overdue = sum(
        motorcycle.days_in_yard(today) > DELAY_DAYS
        for motorcycle in motorcycles
    )
    total_days = sum(
        motorcycle.days_in_yard(today)
        for motorcycle in motorcycles
    )
    average_days = round(total_days / total, 1) if total else 0

    by_city = {}
    overdue_by_city = {}
    days_by_city = {}
    by_status = {}
    for motorcycle in motorcycles:
        by_city[motorcycle.city.name] = by_city.get(motorcycle.city.name, 0) + 1
        overdue_by_city[motorcycle.city.name] = (
            overdue_by_city.get(motorcycle.city.name, 0)
            + (motorcycle.days_in_yard(today) > DELAY_DAYS)
        )
        days_by_city[motorcycle.city.name] = (
            days_by_city.get(motorcycle.city.name, 0)
            + motorcycle.days_in_yard(today)
        )
        by_status[motorcycle.status] = by_status.get(motorcycle.status, 0) + 1

    city_summary = [
        {
            "name": name,
            "total": count,
            "average_days": round(days_by_city[name] / count, 1),
            "overdue": overdue_by_city[name],
        }
        for name, count in sorted(by_city.items())
    ]
    return {
        "total": total,
        "overdue": overdue,
        "average_days": average_days,
        "by_city": dict(sorted(by_city.items())),
        "by_status": dict(sorted(by_status.items())),
        "overdue_by_city": dict(sorted(overdue_by_city.items())),
        "city_summary": city_summary,
    }


@main_bp.route("/admin/users", methods=["GET", "POST"])
@admin_required
def manage_users():
    cities = City.query.order_by(City.name).all()
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        try:
            city_id = int(request.form.get("city_id", ""))
        except ValueError:
            city_id = 0
        city = db.session.get(City, city_id)

        if not name or not email or len(password) < 8 or city is None:
            flash("Preencha os dados e use uma senha com pelo menos 8 caracteres.", "danger")
        elif User.query.filter_by(email=email).first():
            flash("Já existe um usuário com este e-mail.", "danger")
        else:
            user = User(name=name, email=email, role="city_user", city=city)
            user.set_password(password)
            db.session.add(user)
            db.session.commit()
            flash(f"Usuário de {city.name} criado com sucesso.", "success")
            return redirect(url_for("main.manage_users"))

    users = User.query.order_by(User.name).all()
    return render_template("admin_users.html", users=users, cities=cities)


@main_bp.route("/admin/cities", methods=["POST"])
@admin_required
def create_city():
    name = request.form.get("name", "").strip()
    if not name:
        flash("Informe o nome da cidade.", "danger")
    elif City.query.filter(db.func.lower(City.name) == name.lower()).first():
        flash("Esta cidade já está cadastrada.", "danger")
    else:
        db.session.add(City(name=name))
        db.session.commit()
        flash(f"Cidade {name} criada com sucesso.", "success")
    return redirect(url_for("main.manage_users"))


@main_bp.route("/admin/import-spreadsheet", methods=["POST"])
@admin_required
def import_spreadsheet():
    spreadsheet = request.files.get("spreadsheet")
    if (
        spreadsheet is None
        or not spreadsheet.filename
        or not spreadsheet.filename.lower().endswith(".xlsx")
    ):
        flash("Selecione uma planilha válida no formato .xlsx.", "danger")
        return redirect(url_for("main.manage_users"))
    try:
        result = import_motoshow_workbook(spreadsheet.stream)
    except (BadZipFile, ValueError, KeyError, OSError):
        db.session.rollback()
        flash("Não foi possível importar esta planilha.", "danger")
        return redirect(url_for("main.manage_users"))
    flash(
        f"Importação concluída: {result['created']} motos adicionadas, "
        f"{result['skipped']} já existentes e "
        f"{result['cities']} cidades processadas.",
        "success",
    )
    return redirect(url_for("main.dashboard"))
