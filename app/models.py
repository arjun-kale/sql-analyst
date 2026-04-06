from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class SQLObservation(BaseModel):
    """What the agent sees at each step."""

    task_id: str
    task_description: str = Field(description="Natural language business question")
    schema_info: str = Field(description="Database schema as CREATE TABLE statements")
    last_query: Optional[str] = None
    last_result: Optional[str] = Field(default=None, description="JSON string of query result")
    last_error: Optional[str] = None
    step_number: int
    max_steps: int
    hint: Optional[str] = Field(default=None, description="Progressive hints as steps increase")


class SQLAction(BaseModel):
    """What the agent does — write a SQL query."""

    sql_query: str = Field(description="A valid SQLite SQL query to execute")


class SQLReward(BaseModel):
    """Structured reward with partial credit breakdown."""

    value: float = Field(ge=0.0, le=1.0)
    correctness: float = Field(ge=0.0, le=1.0, description="Result set accuracy")
    column_match: float = Field(ge=0.0, le=1.0, description="Correct columns returned")
    row_match: float = Field(ge=0.0, le=1.0, description="Correct rows returned")
    executability: float = Field(ge=0.0, le=1.0, description="Query executed without error")
    ordering_bonus: float = Field(ge=0.0, le=1.0, description="Correct ORDER BY if required")


class StepResult(BaseModel):
    """Full response from env.step() — OpenEnv spec."""

    observation: SQLObservation
    reward: float
    done: bool
    info: Dict[str, Any]


class ResetRequest(BaseModel):
    task_id: Optional[str] = "easy_sales_report"


class StateResponse(BaseModel):
    task_id: str
    step_number: int
    max_steps: int
    cumulative_reward: float
    done: bool
    query_history: List[str]
