from app.core.config import get_settings


class LLMScoringProvider:
    provider_name = "base"

    def evaluate(self, target_text: str, transcript: str, task_type: str) -> dict:
        raise NotImplementedError


class MockLLMScoringProvider(LLMScoringProvider):
    provider_name = "mock"

    def __init__(self, requested_provider: str = "mock") -> None:
        self.requested_provider = requested_provider

    def evaluate(self, target_text: str, transcript: str, task_type: str) -> dict:
        base = 84 if task_type == "repeat" else 80
        return {
            "overall_score": base,
            "content_score": base + 2,
            "clarity_score": base - 4,
            "fluency_score": base - 1,
            "loudness_score": base - 5,
            "prompt_dependence_score": base + 3,
            "main_strength": "表达内容较完整",
            "main_issue": "音量略低",
            "suggestion": "下一次可以放慢一点，并把声音再提高一些。",
        }


def get_llm_scoring_provider() -> LLMScoringProvider:
    settings = get_settings()
    # Real LLM feedback providers will be added behind this factory. Until then,
    # non-mock values fall back to mock and keep the score dimensions stable.
    return MockLLMScoringProvider(requested_provider=settings.llm_feedback_provider)
