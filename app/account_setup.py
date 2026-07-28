import secrets
import string
import unicodedata

from app import db
from app.models import City, User


def _email_slug(name):
    normalized = unicodedata.normalize("NFKD", name)
    ascii_name = normalized.encode("ascii", "ignore").decode("ascii")
    return "".join(
        character.lower()
        for character in ascii_name
        if character.isalnum()
    )


def _password(length=16):
    alphabet = string.ascii_letters + string.digits + "#@!%"
    while True:
        value = "".join(secrets.choice(alphabet) for _ in range(length))
        if (
            any(char.islower() for char in value)
            and any(char.isupper() for char in value)
            and any(char.isdigit() for char in value)
            and any(char in "#@!%" for char in value)
        ):
            return value


def create_missing_city_accounts():
    credentials = []
    skipped = []
    for city in City.query.order_by(City.name).all():
        email = f"{_email_slug(city.name)}@motoshow.local"
        if User.query.filter_by(email=email).first():
            skipped.append(email)
            continue
        password = _password()
        user = User(
            name=f"Equipe {city.name}",
            email=email,
            role="city_user",
            city=city,
        )
        user.set_password(password)
        db.session.add(user)
        credentials.append(
            {"city": city.name, "email": email, "password": password}
        )
    db.session.commit()
    return credentials, skipped
