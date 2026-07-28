from urllib.parse import urljoin, urlparse

from flask import Blueprint, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required, login_user, logout_user

from app.models import User

auth_bp = Blueprint("auth", __name__, url_prefix="/auth")


def _is_safe_redirect(target):
    host_url = urlparse(request.host_url)
    redirect_url = urlparse(urljoin(request.host_url, target))
    return redirect_url.scheme in ("http", "https") and host_url.netloc == redirect_url.netloc


@auth_bp.route("/login", methods=["GET", "POST"])
def login():
    if current_user.is_authenticated:
        return redirect(url_for("main.index"))

    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        user = User.query.filter_by(email=email).first()

        if user is None or not user.check_password(password):
            flash("Credenciais inválidas. Verifique e tente novamente.", "danger")
            return render_template("login.html")

        login_user(user)
        flash("Login efetuado com sucesso.", "success")
        next_url = request.args.get("next")
        return redirect(
            next_url
            if next_url and _is_safe_redirect(next_url)
            else url_for("main.dashboard")
        )

    return render_template("login.html")


@auth_bp.route("/logout", methods=["POST"])
@login_required
def logout():
    logout_user()
    flash("Você saiu com sucesso.", "success")
    return redirect(url_for("main.index"))
