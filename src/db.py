from __future__ import annotations

from datetime import datetime
from pathlib import Path

from peewee import (
    AutoField,
    CharField,
    DateTimeField,
    ForeignKeyField,
    Model,
    SqliteDatabase,
    TextField,
)


_DB_PATH = Path(__file__).resolve().parent.parent / "chat.db"
_db = SqliteDatabase(_DB_PATH)


class BaseModel(Model):
    class Meta:
        database = _db


class User(BaseModel):
    id = AutoField()
    username = CharField(unique=True)


class Conversation(BaseModel):
    id = AutoField()
    user = ForeignKeyField(User, backref="conversations")
    started_at = DateTimeField(default=datetime.utcnow)


class Message(BaseModel):
    id = AutoField()
    conversation = ForeignKeyField(Conversation, backref="messages")
    role = CharField()
    content = TextField()
    created_at = DateTimeField(default=datetime.utcnow)


__all__ = ["_db", "User", "Conversation", "Message"]


def init_db() -> None:
    """Initialise the database and create tables if they do not exist."""
    if _db.is_closed():
        _db.connect()
    _db.create_tables([User, Conversation, Message])
