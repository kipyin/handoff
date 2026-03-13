"""SQLModel models for projects, handoffs, and check-ins."""

from datetime import UTC, date, datetime
from enum import StrEnum

from sqlalchemy import Column, Enum
from sqlmodel import Field, Relationship, SQLModel

if "CheckInType" not in globals():

    class CheckInType(StrEnum):
        """Type of a check-in entry on a handoff's trail.

        Values are persisted as strings in the check_in table.
        """

        ON_TRACK = "on_track"
        DELAYED = "delayed"
        CONCLUDED = "concluded"


if "Project" not in globals():

    class Project(SQLModel, table=True):
        """An engagement/project that contains many handoffs."""

        __tablename__ = "project"  # type: ignore[assignment]
        __table_args__ = {"extend_existing": True}

        id: int | None = Field(default=None, primary_key=True)
        name: str = Field(index=True)
        created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
        is_archived: bool = Field(default=False, index=True)

        handoffs: list["Handoff"] = Relationship(
            back_populates="project",
            sa_relationship_kwargs={"cascade": "all, delete-orphan"},
        )


if "Handoff" not in globals():

    class Handoff(SQLModel, table=True):
        """A single handoff item belonging to a project.

        The pitchman is the person responsible for the deliverable. A handoff
        is closed when its latest check-in has type ``concluded``.
        """

        __tablename__ = "handoff"  # type: ignore[assignment]
        __table_args__ = {"extend_existing": True}

        id: int | None = Field(default=None, primary_key=True)
        project_id: int = Field(foreign_key="project.id", index=True)
        need_back: str
        pitchman: str | None = Field(default=None, index=True)
        next_check: date | None = Field(default=None, index=True)
        deadline: date | None = Field(default=None, index=True)
        notes: str | None = Field(default=None)
        created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))

        project: Project | None = Relationship(back_populates="handoffs")
        check_ins: list["CheckIn"] = Relationship(
            back_populates="handoff",
            sa_relationship_kwargs={
                "cascade": "all, delete-orphan",
                "order_by": "CheckIn.check_in_date, CheckIn.created_at",
            },
        )


if "CheckIn" not in globals():

    class CheckIn(SQLModel, table=True):
        """A check-in entry on a handoff's trail.

        The trail records on-track, delayed, and concluded events. A handoff
        is closed when the latest event in the trail is ``concluded``.
        """

        __tablename__ = "check_in"  # type: ignore[assignment]
        __table_args__ = {"extend_existing": True}

        id: int | None = Field(default=None, primary_key=True)
        handoff_id: int = Field(foreign_key="handoff.id", index=True)
        check_in_date: date
        note: str | None = Field(default=None)
        check_in_type: CheckInType = Field(
            sa_column=Column(
                Enum(
                    CheckInType,
                    values_callable=lambda x: [e.value for e in x],
                ),
                index=True,
                nullable=False,
            ),
        )
        created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))

        handoff: Handoff | None = Relationship(back_populates="check_ins")
