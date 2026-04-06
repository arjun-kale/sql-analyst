from abc import ABC, abstractmethod
import sqlite3
from typing import Dict, List, Optional, Tuple

from app.models import SQLReward


class BaseGrader(ABC):
    def __init__(self, conn: sqlite3.Connection):
        self.conn = conn

    @abstractmethod
    def grade(self, query: str, result_rows: List[Dict], error: Optional[str]) -> SQLReward:
        """Return SQLReward with value in [0.0, 1.0]."""

    def _safe_execute(self, query: str) -> Tuple[List[Dict], Optional[str]]:
        try:
            cur = self.conn.execute(query)
            rows = [dict(r) for r in cur.fetchall()]
            return rows, None
        except Exception as exc:  # pragma: no cover
            return [], str(exc)
