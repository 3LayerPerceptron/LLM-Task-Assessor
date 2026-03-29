from collections import namedtuple

from backend.src.database.user import (
    User,
    Group
)


user = User(
    email="abc@example.com",
    name="test-account",
    description="this is test account"
)

PasswordAuthForm = namedtuple("PasswordAuthentication", ["email", "password"])
password_auth = PasswordAuthForm(
    email="abc@example.com",
    password="password"
)

group = Group(
    name="test-group",
    description="this is test group"
)
