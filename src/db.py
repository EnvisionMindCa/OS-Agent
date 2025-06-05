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
    session_name = CharField()
    started_at = DateTimeField(default=datetime.utcnow)

    class Meta:
        indexes = ((("user", "session_name"), True),)


class Message(BaseModel):
    id = AutoField()
    conversation = ForeignKeyField(Conversation, backref="messages")
    role = CharField()
    content = TextField()
    created_at = DateTimeField(default=datetime.utcnow)


class Document(BaseModel):
    id = AutoField()
    user = ForeignKeyField(User, backref="documents")
    file_path = CharField()
    original_name = CharField()
    created_at = DateTimeField(default=datetime.utcnow)


__all__ = [
    "_db",
    "User",
    "Conversation",
    "Message",
    "Document",
    "reset_history",
    "add_document",
]


def init_db() -> None:
    """Initialise the database and create tables if they do not exist."""
    if _db.is_closed():
        _db.connect()
    _db.create_tables([User, Conversation, Message, Document])


def reset_history(username: str, session_name: str) -> int:
    """Delete all messages for the given user and session."""

    init_db()
    try:
        user = User.get(User.username == username)
        conv = Conversation.get(
            Conversation.user == user, Conversation.session_name == session_name
        )
    except (User.DoesNotExist, Conversation.DoesNotExist):
        return 0

    deleted = Message.delete().where(Message.conversation == conv).execute()
    conv.delete_instance()
    if not Conversation.select().where(Conversation.user == user).exists():
        user.delete_instance()
    return deleted


def add_document(username: str, file_path: str, original_name: str) -> Document:
    """Record an uploaded document and return the created entry."""

    init_db()
    user, _ = User.get_or_create(username=username)
    doc = Document.create(user=user, file_path=file_path, original_name=original_name)
    return doc
