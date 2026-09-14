import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.database.base import Base, import_models
from app.modules.agents.model import Agent
from app.modules.avatar_videos.model import AvatarVideoTask, AvatarVideoTaskStatus
from app.modules.avatar_videos.service import claim_next_task, enqueue_for_audio, invalidate_agent_video_tasks, process_task, recover_stale_running_tasks
from app.modules.files.model import FileAsset, FileStatus, FileType
from app.modules.users.model import PatientProfile, User, UserRole


def video_settings(storage_root: Path):
    return SimpleNamespace(
        avatar_video_provider="mock", storage_root=storage_root, sadtalker_home=None,
        sadtalker_python=None, sadtalker_timeout_seconds=180, sadtalker_preprocess="crop",
        sadtalker_face_size=512, sadtalker_use_enhancer=False,
    )


class AvatarVideoTaskTest(unittest.TestCase):
    def setUp(self) -> None:
        import_models()
        self.engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(
            self.engine,
            tables=[User.__table__, PatientProfile.__table__, Agent.__table__, FileAsset.__table__, AvatarVideoTask.__table__],
        )
        self.SessionLocal = sessionmaker(bind=self.engine, expire_on_commit=False)
        self.temp_dir = tempfile.TemporaryDirectory()
        self.root = Path(self.temp_dir.name)
        self.db = self.SessionLocal()
        self.user = User(username="video-patient", password_hash="hash", role=UserRole.patient)
        self.db.add(self.user)
        self.db.flush()
        self.profile = PatientProfile(user_id=self.user.id)
        self.db.add(self.profile)
        self.db.flush()
        self.agent = Agent(patient_profile_id=self.profile.id, name="陪练", relationship="朋友", personality_style="gentle", image_consent_confirmed=True)
        self.db.add(self.agent)
        self.db.flush()
        image_path = self.root / "portrait.jpg"
        image_path.write_bytes(b"image")
        audio_path = self.root / "speech.wav"
        audio_path.write_bytes(b"audio")
        self.image = FileAsset(owner_user_id=self.user.id, file_type=FileType.agent_image, original_name="portrait.jpg", storage_path=str(image_path), mime_type="image/jpeg", size_bytes=image_path.stat().st_size, status=FileStatus.active)
        self.audio = FileAsset(owner_user_id=self.user.id, file_type=FileType.generated_audio, original_name="speech.wav", storage_path=str(audio_path), mime_type="audio/wav", size_bytes=audio_path.stat().st_size, status=FileStatus.active)
        self.db.add_all([self.image, self.audio])
        self.db.flush()
        self.agent.avatar_file_id = self.image.id
        self.db.commit()
        self.db.refresh(self.agent)
        self.db.refresh(self.audio)

    def tearDown(self) -> None:
        self.db.close()
        self.engine.dispose()
        self.temp_dir.cleanup()

    def test_duplicate_input_reuses_one_task_and_worker_persists_video(self) -> None:
        settings = video_settings(self.root)
        with patch("app.modules.avatar_videos.service.get_settings", return_value=settings), patch("app.integrations.avatar_video.provider.get_settings", return_value=settings), patch("app.modules.files.service.get_settings", return_value=settings):
            first = enqueue_for_audio(self.db, self.user, self.agent, self.audio)
            second = enqueue_for_audio(self.db, self.user, self.agent, self.audio)
            self.assertIsNotNone(first)
            self.assertEqual(first.id, second.id)
            claimed = claim_next_task(self.db)
            self.assertEqual(claimed.status, AvatarVideoTaskStatus.running)
            completed = process_task(self.db, claimed)
        self.assertEqual(completed.status, AvatarVideoTaskStatus.succeeded)
        self.assertIsNotNone(completed.video_file_id)
        self.assertTrue(Path(completed.video_file.storage_path).is_file())
        self.assertEqual(completed.video_file.file_type, FileType.generated_avatar_video)

    def test_missing_avatar_skips_video_task(self) -> None:
        self.agent.avatar_file_id = None
        self.db.commit()
        settings = video_settings(self.root)
        with patch("app.modules.avatar_videos.service.get_settings", return_value=settings), patch("app.integrations.avatar_video.provider.get_settings", return_value=settings), patch("app.modules.files.service.get_settings", return_value=settings):
            self.assertIsNone(enqueue_for_audio(self.db, self.user, self.agent, self.audio))
        self.assertEqual(self.db.query(AvatarVideoTask).count(), 0)

    def test_failed_task_is_requeued_for_the_same_cached_audio(self) -> None:
        settings = video_settings(self.root)
        with patch("app.modules.avatar_videos.service.get_settings", return_value=settings), patch("app.integrations.avatar_video.provider.get_settings", return_value=settings):
            task = enqueue_for_audio(self.db, self.user, self.agent, self.audio)
            task.status = AvatarVideoTaskStatus.failed
            task.error_code = "timeout"
            task.error_message = "previous run timed out"
            self.db.commit()
            retried = enqueue_for_audio(self.db, self.user, self.agent, self.audio)
        self.assertEqual(retried.id, task.id)
        self.assertEqual(retried.status, AvatarVideoTaskStatus.queued)
        self.assertIsNone(retried.error_code)
        self.assertIsNone(retried.error_message)

    def test_stale_running_task_is_failed_after_worker_interruption(self) -> None:
        settings = video_settings(self.root)
        with patch("app.modules.avatar_videos.service.get_settings", return_value=settings), patch("app.integrations.avatar_video.provider.get_settings", return_value=settings), patch("app.modules.files.service.get_settings", return_value=settings):
            task = enqueue_for_audio(self.db, self.user, self.agent, self.audio)
            claimed = claim_next_task(self.db)
            self.assertEqual(claimed.id, task.id)
            claimed.updated_at = claimed.updated_at.replace(year=2000)
            self.db.commit()
            self.assertEqual(recover_stale_running_tasks(self.db), 1)
        self.db.refresh(task)
        self.assertEqual(task.status, AvatarVideoTaskStatus.failed)
        self.assertEqual(task.error_code, "worker_interrupted")

    def test_revoking_image_access_invalidates_generated_video(self) -> None:
        settings = video_settings(self.root)
        with patch("app.modules.avatar_videos.service.get_settings", return_value=settings), patch("app.integrations.avatar_video.provider.get_settings", return_value=settings), patch("app.modules.files.service.get_settings", return_value=settings):
            task = enqueue_for_audio(self.db, self.user, self.agent, self.audio)
            completed = process_task(self.db, claim_next_task(self.db))
            invalidate_agent_video_tasks(self.db, self.agent.id, self.user.id)
            self.db.commit()
        self.db.refresh(completed.video_file)
        self.db.refresh(task)
        self.assertEqual(completed.video_file.status, FileStatus.deleted)


if __name__ == "__main__":
    unittest.main()
