import json
from typing import Dict, List, Optional, Tuple

from app.database import get_connection, get_schema_str
from app.graders.task_easy import EasyGrader
from app.graders.task_hard import HardGrader
from app.graders.task_medium import MediumGrader
from app.models import SQLAction, SQLObservation, SQLReward, StateResponse, StepResult
from app.tasks.registry import TASKS

GRADER_MAP = {
    "easy_sales_report": EasyGrader,
    "medium_customer_ltv": MediumGrader,
    "hard_churn_cohort": HardGrader,
}


class SQLAnalystEnv:
    def __init__(self):
        self.conn = get_connection()
        self.task_id: str = "easy_sales_report"
        self.step_number: int = 0
        self.done: bool = False
        self.cumulative_reward: float = 0.0
        self.query_history: List[str] = []
        self.grader = None
        self._max_steps: int = 8
        self._best_reward: float = 0.0

    def reset(self, task_id: str = "easy_sales_report") -> SQLObservation:
        if task_id not in TASKS:
            task_id = "easy_sales_report"
        self.task_id = task_id
        task = TASKS[task_id]
        self.step_number = 0
        self.done = False
        self.cumulative_reward = 0.0
        self.query_history = []
        self._best_reward = 0.0
        self._max_steps = task.max_steps
        self.grader = GRADER_MAP[task_id](self.conn)
        return SQLObservation(
            task_id=task_id,
            task_description=task.description,
            schema_info=get_schema_str(),
            step_number=0,
            max_steps=self._max_steps,
        )

    def step(self, action: SQLAction) -> StepResult:
        if self.done:
            raise ValueError("Episode done. Call reset() first.")

        self.step_number += 1
        task = TASKS[self.task_id]
        query = action.sql_query.strip()
        self.query_history.append(query)

        result_rows, error = self._safe_execute(query)
        reward_obj: SQLReward = self.grader.grade(query, result_rows, error)
        reward = reward_obj.value

        if reward > self._best_reward:
            self._best_reward = reward
        self.cumulative_reward += reward

        self.done = (reward >= 0.95) or (self.step_number >= self._max_steps)

        hint = None
        if self.step_number >= 6 and not self.done:
            hint = task.hint_2
        elif self.step_number >= 3 and not self.done:
            hint = task.hint_1

        obs = SQLObservation(
            task_id=self.task_id,
            task_description=task.description,
            schema_info=get_schema_str(),
            last_query=query,
            last_result=json.dumps(result_rows[:20]) if result_rows else None,
            last_error=error,
            step_number=self.step_number,
            max_steps=self._max_steps,
            hint=hint,
        )
        return StepResult(
            observation=obs,
            reward=reward,
            done=self.done,
            info={
                "reward_breakdown": reward_obj.model_dump(),
                "best_reward_this_episode": self._best_reward,
                "steps_remaining": self._max_steps - self.step_number,
            },
        )

    def state(self) -> StateResponse:
        return StateResponse(
            task_id=self.task_id,
            step_number=self.step_number,
            max_steps=self._max_steps,
            cumulative_reward=self.cumulative_reward,
            done=self.done,
            query_history=self.query_history,
        )

    def _safe_execute(self, query: str) -> Tuple[List[Dict], Optional[str]]:
        q_upper = query.upper()
        for kw in ["DROP", "DELETE", "INSERT", "UPDATE", "CREATE", "ALTER", "ATTACH"]:
            if kw in q_upper.split():
                return [], f"Operation {kw} is not permitted."
        try:
            cur = self.conn.execute(query)
            rows = [dict(r) for r in cur.fetchall()]
            return rows, None
        except Exception as exc:
            return [], str(exc)
