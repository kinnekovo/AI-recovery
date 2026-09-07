import unittest
from datetime import datetime
from uuid import uuid4

from app.modules.therapist.report_export import render_stage_report_html
from app.modules.therapist.schema import (
    TherapistStageAssessmentRead,
    TherapistStageReportRead,
    TherapistTrendBucketRead,
)


class StageReportExportTest(unittest.TestCase):
    def test_renders_printable_report_with_escaped_notes(self) -> None:
        report = TherapistStageReportRead(
            patient_user_id=uuid4(),
            patient_profile_id=uuid4(),
            username="patient-a",
            training_count=8,
            analyzed_attempt_count=7,
            failed_analysis_count=1,
            low_quality_attempt_count=2,
            low_quality_rate=0.25,
            provider_failure_count=1,
            process_summary=TherapistTrendBucketRead(
                key="selected_range",
                label="所选阶段",
                attempt_count=7,
                avg_overall_score=83.0,
                avg_script_accuracy=91.5,
                avg_error_count=1.0,
                avg_speech_rate=188.0,
                avg_loudness=64.0,
                summary="表达较稳定。",
            ),
            assessments=[
                TherapistStageAssessmentRead(
                    assessment_id=uuid4(),
                    assessment_type="during",
                    review_status="confirmed",
                    assessed_at=datetime(2026, 9, 3, 10, 0),
                    reviewed_at=datetime(2026, 9, 3, 11, 0),
                    therapist_notes="<继续短句>",
                    metrics={"script_accuracy": 91.5},
                )
            ],
            therapist_notes=["<继续短句>"],
        )

        html = render_stage_report_html(report)

        self.assertIn("阶段训练报告", html)
        self.assertIn("训练次数：8", html)
        self.assertIn("低质量比例", html)
        self.assertIn("91.5%", html)
        self.assertIn("&lt;继续短句&gt;", html)
        self.assertNotIn("<继续短句>", html)
        self.assertIn("window.print()", html)


if __name__ == "__main__":
    unittest.main()
