from __future__ import annotations

from datetime import datetime
from pathlib import Path

from ..config import DB_PATH

from peewee import (
    AutoField,
    CharField,
    DateTimeField,
    ForeignKeyField,
    Model,
    SqliteDatabase,
    TextField,
)


_DB_PATH = Path(DB_PATH)
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


class DatabaseManager:
    """Wrapper class to perform all DB operations."""

    def __init__(self, database: SqliteDatabase) -> None:
        self._db = database

    def init_db(self) -> None:
        if self._db.is_closed():
            self._db.connect()
        self._db.create_tables([User, Conversation, Message, Document])

    def close(self) -> None:
        if not self._db.is_closed():
            self._db.close()

    # ------------------------------------------------------------------
    def get_or_create_user(self, username: str) -> User:
        self.init_db()
        user, _ = User.get_or_create(username=username)
        return user

    def get_or_create_conversation(self, user: User, session_name: str) -> Conversation:
        self.init_db()
        conv, _ = Conversation.get_or_create(user=user, session_name=session_name)
        return conv

    def create_message(self, conversation: Conversation, role: str, content: str) -> Message:
        self.init_db()
        return Message.create(conversation=conversation, role=role, content=content)

    def list_messages(self, conversation: Conversation) -> list[Message]:
        self.init_db()
        return list(
            Message.select()
            .where(Message.conversation == conversation)
            .order_by(Message.created_at)
        )

    def add_document(self, username: str, file_path: str, original_name: str) -> Document:
        self.init_db()
        user = self.get_or_create_user(username)
        return Document.create(user=user, file_path=file_path, original_name=original_name)

    def reset_history(self, username: str, session_name: str) -> int:
        self.init_db()
        try:
            user = User.get(User.username == username)
            conv = Conversation.get(
                Conversation.user == user,
                Conversation.session_name == session_name,
            )
        except (User.DoesNotExist, Conversation.DoesNotExist):
            return 0

        deleted = Message.delete().where(Message.conversation == conv).execute()
        conv.delete_instance()
        if not Conversation.select().where(Conversation.user == user).exists():
            user.delete_instance()
        return deleted

    def list_sessions(self, username: str) -> list[str]:
        self.init_db()
        try:
            user = User.get(User.username == username)
        except User.DoesNotExist:
            return []
        return [c.session_name for c in Conversation.select().where(Conversation.user == user)]

    def list_sessions_info(self, username: str) -> list[dict[str, str]]:
        self.init_db()
        try:
            user = User.get(User.username == username)
        except User.DoesNotExist:
            return []

        sessions = []
        for conv in Conversation.select().where(Conversation.user == user):
            last_msg = (
                Message.select()
                .where(Message.conversation == conv)
                .order_by(Message.created_at.desc())
                .first()
            )
            snippet = (last_msg.content[:50] + "…") if last_msg else ""
            sessions.append({"name": conv.session_name, "last_message": snippet})
        return sessions


db = DatabaseManager(_db)



__all__ = [
    "_db",
    "User",
    "Conversation",
    "Message",
    "Document",
    "db",
    "reset_history",
    "list_sessions",
    "list_sessions_info",
    "add_document",
]


def init_db() -> None:
    """Initialise the database and create tables if they do not exist."""
    db.init_db()


def reset_history(username: str, session_name: str) -> int:
    """Delete all messages for the given user and session."""

    return db.reset_history(username, session_name)


def add_document(username: str, file_path: str, original_name: str) -> Document:
    """Record an uploaded document and return the created entry."""

    return db.add_document(username, file_path, original_name)


def list_sessions(username: str) -> list[str]:
    """Return all session names for the given ``username``."""

    return db.list_sessions(username)


def list_sessions_info(username: str) -> list[dict[str, str]]:
    """Return session names and a snippet of the last message for ``username``."""

    return db.list_sessions_info(username)

from ..utils.debug import debug_all
debug_all(globals())

