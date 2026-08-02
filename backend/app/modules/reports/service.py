from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.modules.attempts.model import Attempt
from app.modules.reports.schema import LatestReportRead
from app.modules.scoring.model import AttemptScore
from app.modules.training.model import SessionTask, TrainingSession
from app.modules.users.model import User
from app.modules.users.service import get_patient_profile


def latest_report(db: Session, user: User) -> LatestReportRead:
    profile = get_patient_profile(db, user)
    stmt = (
        select(func.count(AttemptScore.id), func.avg(AttemptScore.overall_score))
        .join(Attempt, Attempt.id == AttemptScore.attempt_id)
        .join(SessionTask, SessionTask.id == Attempt.session_task_id)
        .join(TrainingSession, TrainingSession.id == SessionTask.training_session_id)
        .where(TrainingSession.patient_profile_id == profile.id)
    )
    count, average = db.execute(stmt).one()
    avg = float(average or 0)
    suggestion = "继续加强自主表达" if avg >= 80 else "建议先稳定完成短句跟读"
    return LatestReportRead(training_count=int(count or 0), average_score=round(avg, 1), suggestion=suggestion)
