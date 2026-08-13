from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import get_settings
from app.modules.agents.router import router as agents_router
from app.modules.assessment.router import router as assessment_router
from app.modules.attempts.router import router as attempts_router
from app.modules.auth.router import router as auth_router
from app.modules.consent.router import router as consent_router
from app.modules.evaluations.router import router as evaluations_router
from app.modules.family.router import router as family_router
from app.modules.files.router import router as files_router
from app.modules.profiles.router import router as profiles_router
from app.modules.reports.router import router as reports_router
from app.modules.scoring.router import router as scoring_router
from app.modules.therapist.router import router as therapist_router
from app.modules.training.router import router as training_router
from app.modules.users.router import router as users_router


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(title=settings.app_name)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.backend_cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.include_router(auth_router, prefix=settings.api_prefix)
    app.include_router(users_router, prefix=settings.api_prefix)
    app.include_router(agents_router, prefix=settings.api_prefix)
    app.include_router(training_router, prefix=settings.api_prefix)
    app.include_router(attempts_router, prefix=settings.api_prefix)
    app.include_router(scoring_router, prefix=settings.api_prefix)
    app.include_router(evaluations_router, prefix=settings.api_prefix)
    app.include_router(assessment_router, prefix=settings.api_prefix)
    app.include_router(reports_router, prefix=settings.api_prefix)
    app.include_router(profiles_router, prefix=settings.api_prefix)
    app.include_router(therapist_router, prefix=settings.api_prefix)
    app.include_router(family_router, prefix=settings.api_prefix)
    app.include_router(files_router, prefix=settings.api_prefix)
    app.include_router(consent_router, prefix=settings.api_prefix)
    return app


app = create_app()
