class LLMScoringProvider:
    def evaluate(self, target_text: str, transcript: str, task_type: str) -> dict:
        raise NotImplementedError


class MockLLMScoringProvider(LLMScoringProvider):
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
    return MockLLMScoringProvider()
