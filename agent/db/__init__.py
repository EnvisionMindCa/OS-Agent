from __future__ import annotations

from datetime import datetime
from pathlib import Path

from ..config import DB_PATH, DEFAULT_MEMORY_TEMPLATE

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


def configure_db(path: str) -> None:
    """Update the database location used by the manager."""

    global _db, _DB_PATH, db
    new_path = Path(path)
    if new_path == _DB_PATH:
        return
    if not _db.is_closed():
        _db.close()
    _DB_PATH = new_path
    _db = SqliteDatabase(_DB_PATH)
    db = DatabaseManager(_db)


class BaseModel(Model):
    class Meta:
        database = _db


class User(BaseModel):
    id = AutoField()
    username = CharField(unique=True)
    password_hash = CharField(null=True)
    memory = TextField(default="")


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

    def register_user(self, username: str, password_hash: str | None = None) -> User:
        """Create and return a ``User`` with optional ``password_hash``."""

        self.init_db()
        return User.create(username=username, password_hash=password_hash)

    def authenticate_user(self, username: str) -> User | None:
        self.init_db()
        try:
            return User.get(User.username == username)
        except User.DoesNotExist:
            return None

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

    def delete_history(self, username: str, session_name: str) -> int:
        """Remove all messages for ``username`` in ``session_name``.

        The conversation record itself is deleted as well. If no other
        conversations remain for the user, the user entry is removed.
        The number of deleted messages is returned.
        """

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

    def reset_memory(self, username: str, template: str = DEFAULT_MEMORY_TEMPLATE) -> str:
        """Reset ``username``'s memory to ``template`` and return the new value."""

        self.init_db()
        user = self.get_or_create_user(username)
        user.memory = template
        user.save()
        return user.memory

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

    def get_memory(self, username: str) -> str:
        self.init_db()
        user = self.get_or_create_user(username)
        return user.memory

    def set_memory(self, username: str, memory: str) -> str:
        self.init_db()
        user = self.get_or_create_user(username)
        user.memory = memory
        user.save()
        return memory


db = DatabaseManager(_db)



__all__ = [
    "_db",
    "User",
    "Conversation",
    "Message",
    "Document",
    "db",
    "configure_db",
    "delete_history",
    "reset_history",
    "reset_memory",
    "list_sessions",
    "list_sessions_info",
    "add_document",
    "get_memory",
    "set_memory",
    "register_user",
    "authenticate_user",
]


def init_db() -> None:
    """Initialise the database and create tables if they do not exist."""
    db.init_db()


def delete_history(username: str, session_name: str) -> int:
    """Delete all messages for the given user and session."""

    return db.delete_history(username, session_name)


def reset_history(username: str, session_name: str) -> int:
    """Backward-compatible alias for :func:`delete_history`."""

    return delete_history(username, session_name)


def reset_memory(username: str) -> str:
    """Reset persistent memory for ``username`` to the default template."""

    return db.reset_memory(username)


def add_document(username: str, file_path: str, original_name: str) -> Document:
    """Record an uploaded document and return the created entry."""

    return db.add_document(username, file_path, original_name)


def get_memory(username: str) -> str:
    """Return persistent memory for ``username``."""

    return db.get_memory(username)


def set_memory(username: str, memory: str) -> str:
    """Persist ``memory`` for ``username``."""

    return db.set_memory(username, memory)


def register_user(username: str, password_hash: str | None = None) -> User:
    """Create a new user with ``password_hash`` (optional)."""

    return db.register_user(username, password_hash)


def authenticate_user(username: str) -> User | None:
    """Return user record if ``username`` exists."""

    return db.authenticate_user(username)


def list_sessions(username: str) -> list[str]:
    """Return all session names for the given ``username``."""

    return db.list_sessions(username)


def list_sessions_info(username: str) -> list[dict[str, str]]:
    """Return session names and a snippet of the last message for ``username``."""

    return db.list_sessions_info(username)

from ..utils.debug import debug_all
debug_all(globals())

