"""SQLModel models for projects and todos."""

from datetime import UTC, datetime
from enum import StrEnum

from sqlmodel import Field, Relationship, SQLModel


class TodoStatus(StrEnum):
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

    id: int | None = Field(default=None, primary_key=True)
    name: str = Field(index=True)
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))

    todos: list["Todo"] = Relationship(back_populates="project")


class Todo(SQLModel, table=True):
    """A single todo item belonging to a project.

    The ``helper`` field is the person responsible for the todo; ``delegated`` status
    typically means the task is outstanding and assigned to that helper.
    """

    __tablename__ = "todo"
    __table_args__ = {"extend_existing": True}

    id: int | None = Field(default=None, primary_key=True)
    project_id: int = Field(foreign_key="project.id", index=True)
    name: str
    status: TodoStatus = Field(default=TodoStatus.DELEGATED, index=True)
    deadline: datetime | None = Field(default=None, index=True)
    helper: str | None = Field(default=None, index=True)
    notes: str | None = Field(default=None)
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    completed_at: datetime | None = Field(default=None, index=True)

    project: Project | None = Relationship(back_populates="todos")
