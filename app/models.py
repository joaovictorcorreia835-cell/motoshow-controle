from datetime import datetime
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash

from app import db, login_manager


class User(UserMixin, db.Model):
    __tablename__ = "users"

    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(255), unique=True, nullable=False)
    name = db.Column(db.String(128), nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    role = db.Column(db.String(20), nullable=False, default="city_user")
    city_id = db.Column(db.Integer, db.ForeignKey("cities.id"), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    city = db.relationship("City", back_populates="users")

    @property
    def is_admin(self) -> bool:
        return self.role == "admin"

    def set_password(self, password: str) -> None:
        self.password_hash = generate_password_hash(password)

    def check_password(self, password: str) -> bool:
        return check_password_hash(self.password_hash, password)


class City(db.Model):
    __tablename__ = "cities"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(128), unique=True, nullable=False)
    users = db.relationship("User", back_populates="city")
    immobilized_motorcycles = db.relationship(
        "ImmobilizedMotorcycle", back_populates="city"
    )


class ImmobilizedMotorcycle(db.Model):
    __tablename__ = "immobilized_motorcycles"

    id = db.Column(db.Integer, primary_key=True)
    city_id = db.Column(db.Integer, db.ForeignKey("cities.id"), nullable=False)
    client = db.Column(db.String(160), nullable=False)
    model = db.Column(db.String(120), nullable=False)
    plate = db.Column(db.String(10), nullable=False, index=True)
    chassis = db.Column(db.String(40), nullable=False)
    service_order = db.Column(db.String(40), nullable=False, index=True)
    reason = db.Column(db.Text, nullable=False)
    entry_date = db.Column(db.Date, nullable=False)
    expected_date = db.Column(db.Date, nullable=False)
    status = db.Column(db.String(60), nullable=False)
    responsible = db.Column(db.String(120), nullable=True)
    notes = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(
        db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False
    )

    city = db.relationship("City", back_populates="immobilized_motorcycles")

    def days_in_yard(self, today):
        return max(0, (today - self.entry_date).days)

    def days_overdue(self, today, delay_days=30):
        return max(0, self.days_in_yard(today) - delay_days)


@login_manager.user_loader
def load_user(user_id: str):
    try:
        return db.session.get(User, int(user_id))
    except (TypeError, ValueError):
        return None
