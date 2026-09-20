import enum
import uuid

from sqlalchemy import Enum, ForeignKey, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class UserRole(str, enum.Enum):
    patient = "patient"
    family = "family"
    therapist = "therapist"
    admin = "admin"


class UserStatus(str, enum.Enum):
    active = "active"
    disabled = "disabled"


class User(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "users"

    username: Mapped[str] = mapped_column(String(80), unique=True, index=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[UserRole] = mapped_column(Enum(UserRole, name="user_role"), default=UserRole.patient, nullable=False)
    status: Mapped[UserStatus] = mapped_column(
        Enum(UserStatus, name="user_status"), default=UserStatus.active, nullable=False
    )

    patient_profile: Mapped["PatientProfile | None"] = relationship(back_populates="user", uselist=False)


class OnboardingStatus(str, enum.Enum):
    pending_agent = "pending_agent"
    ready = "ready"


class PatientProfile(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "patient_profiles"

    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), unique=True, nullable=False)
    current_agent_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("agents.id"), nullable=True)
    onboarding_status: Mapped[OnboardingStatus] = mapped_column(
        Enum(OnboardingStatus, name="onboarding_status"), default=OnboardingStatus.pending_agent, nullable=False
    )
    assessment_status: Mapped[str] = mapped_column(String(40), default="not_started", nullable=False)
    training_status: Mapped[str] = mapped_column(String(40), default="not_started", nullable=False)
    timezone: Mapped[str] = mapped_column(String(64), default="Asia/Shanghai", nullable=False)

    user: Mapped[User] = relationship(back_populates="patient_profile")
    current_agent: Mapped["Agent | None"] = relationship("Agent", foreign_keys=[current_agent_id], post_update=True)


class FamilyPatientBinding(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "family_patient_bindings"

    family_user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), index=True, nullable=False)
    patient_profile_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("patient_profiles.id"), index=True, nullable=False
    )
    relationship_label: Mapped[str] = mapped_column(String(40), default="家属", nullable=False)
    status: Mapped[str] = mapped_column(String(40), default="active", nullable=False)

    family_user: Mapped[User] = relationship("User", foreign_keys=[family_user_id])
    patient_profile: Mapped[PatientProfile] = relationship("PatientProfile")


class TherapistPatientAssignment(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "therapist_patient_assignments"
    __table_args__ = (UniqueConstraint("therapist_user_id", "patient_profile_id", name="uq_therapist_patient_assignment"),)

    therapist_user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), index=True, nullable=False)
    patient_profile_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("patient_profiles.id"), index=True, nullable=False
    )
    status: Mapped[str] = mapped_column(String(40), default="active", nullable=False)

    therapist_user: Mapped[User] = relationship("User", foreign_keys=[therapist_user_id])
    patient_profile: Mapped[PatientProfile] = relationship("PatientProfile")


from app.modules.agents.model import Agent  # noqa: E402

PatientProfile.agents = relationship(
    Agent,
    back_populates="patient_profile",
    foreign_keys=[Agent.patient_profile_id],
)
