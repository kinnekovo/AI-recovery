from datetime import datetime, timezone
import uuid

from sqlalchemy import DateTime
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class Base(DeclarativeBase):
    pass


class UUIDPrimaryKeyMixin:
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, onupdate=utc_now, nullable=False
    )


def import_models() -> None:
    from app.modules.agents import model as agents_model  # noqa: F401
    from app.modules.avatar_videos import model as avatar_videos_model  # noqa: F401
    from app.modules.assessment import model as assessment_model  # noqa: F401
    from app.modules.attempts import model as attempts_model  # noqa: F401
    from app.modules.consent import model as consent_model  # noqa: F401
    from app.modules.evaluations import model as evaluations_model  # noqa: F401
    from app.modules.files import model as files_model  # noqa: F401
    from app.modules.profiles import model as profiles_model  # noqa: F401
    from app.modules.pronunciation import model as pronunciation_model  # noqa: F401
    from app.modules.scoring import model as scoring_model  # noqa: F401
    from app.modules.scenario_dialogues import model as scenario_dialogues_model  # noqa: F401
    from app.modules.training import model as training_model  # noqa: F401
    from app.modules.users import model as users_model  # noqa: F401
