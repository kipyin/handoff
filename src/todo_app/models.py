"""SQLModel models for projects and todos."""

from datetime import datetime, timezone
from enum import Enum
from typing import Optional

from sqlmodel import Field, Relationship, SQLModel


class TodoStatus(str, Enum):
    """Status of a todo item.

    Values are persisted as strings in the database and used for filtering and display.
    """

    DELEGATED = "delegated"
    DONE = "done"
    CANCELED = "canceled"


class Project(SQLModel, table=True):
    """An engagement/project that contains many todos."""

    __tablename__ = "project"
    __table_args__ = {"extend_existing": True}

    id: Optional[int] = Field(default=None, primary_key=True)
    name: str = Field(index=True)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    todos: list["Todo"] = Relationship(back_populates="project")


class Todo(SQLModel, table=True):
    """A single todo item belonging to a project.

    The ``helper`` field is the person responsible for the todo; ``delegated`` status
    typically means the task is outstanding and assigned to that helper.
    """

    __tablename__ = "todo"
    __table_args__ = {"extend_existing": True}

    id: Optional[int] = Field(default=None, primary_key=True)
    project_id: int = Field(foreign_key="project.id", index=True)
    name: str
    status: TodoStatus = Field(default=TodoStatus.DELEGATED, index=True)
    deadline: Optional[datetime] = Field(default=None, index=True)
    helper: Optional[str] = Field(default=None, index=True)
    notes: Optional[str] = Field(default=None)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    project: Optional[Project] = Relationship(back_populates="todos")
