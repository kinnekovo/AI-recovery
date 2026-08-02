class ASRProvider:
    def transcribe(self, audio_path: str) -> str:
        raise NotImplementedError


class MockASRProvider(ASRProvider):
    def transcribe(self, audio_path: str) -> str:
        return "这是一次模拟转写结果"


def get_asr_provider() -> ASRProvider:
    return MockASRProvider()
