from pydantic import BaseModel


class LatestReportRead(BaseModel):
    training_count: int
    average_score: float
    suggestion: str
