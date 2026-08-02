from pathlib import Path
from uuid import uuid4


class VoiceCloneProvider:
    def clone_voice(self, audio_path: str) -> str:
        raise NotImplementedError


class MockVoiceCloneProvider(VoiceCloneProvider):
    def clone_voice(self, audio_path: str) -> str:
        stem = Path(audio_path).stem[:8]
        return f"mock_voice_{stem}_{uuid4().hex[:8]}"


def get_voice_clone_provider() -> VoiceCloneProvider:
    return MockVoiceCloneProvider()
