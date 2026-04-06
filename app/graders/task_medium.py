from typing import Dict, List, Optional

from app.graders.base import BaseGrader
from app.models import SQLReward

CANONICAL_QUERY = """
SELECT c.id,
       c.name,
       COUNT(DISTINCT o.id) AS order_count,
       ROUND(SUM(oi.quantity * oi.unit_price), 2) AS total_spend,
       ROUND(SUM(oi.quantity * oi.unit_price) / COUNT(DISTINCT o.id), 2) AS avg_order_value
FROM customers c
JOIN orders o ON c.id = o.customer_id
JOIN order_items oi ON o.id = oi.order_id
WHERE o.order_date BETWEEN '2023-01-01' AND '2023-12-31'
  AND o.status = 'completed'
GROUP BY c.id, c.name
ORDER BY total_spend DESC
LIMIT 10
"""


class MediumGrader(BaseGrader):
    def __init__(self, conn):
        super().__init__(conn)
        gt, _ = self._safe_execute(CANONICAL_QUERY)
        self._gt_customer_ids = [r["id"] for r in gt]

    def grade(self, query: str, result_rows: List[Dict], error: Optional[str]) -> SQLReward:
        if error or not result_rows:
            return SQLReward(
                value=0.0,
                correctness=0.0,
                column_match=0.0,
                row_match=0.0,
                executability=0.0,
                ordering_bonus=0.0,
            )

        executability = 1.0
        cols = {k.lower() for k in result_rows[0].keys()}
        has_name = any("name" in c for c in cols)
        has_spend = any(c in {"total_spend", "spend", "revenue", "amount"} for c in cols)
        has_count = any(c in {"order_count", "orders", "count"} for c in cols)
        has_avg = any("avg" in c for c in cols)
        column_match = (
            (0.25 * float(has_name))
            + (0.35 * float(has_spend))
            + (0.25 * float(has_count))
            + (0.15 * float(has_avg))
        )

        agent_ids: List[int] = []
        for row in result_rows[:10]:
            for key, value in row.items():
                if key.lower() in {"id", "customer_id", "cid"}:
                    agent_ids.append(int(value))
                    break

        overlap = len(set(agent_ids) & set(self._gt_customer_ids))
        row_match = overlap / 10.0

        ordering_bonus = 0.0
        if agent_ids[:5] == self._gt_customer_ids[:5]:
            ordering_bonus = 1.0
        elif agent_ids[:3] == self._gt_customer_ids[:3]:
            ordering_bonus = 0.6

        correctness = row_match * column_match
        value = round(
            (0.15 * executability)
            + (0.25 * column_match)
            + (0.45 * row_match)
            + (0.15 * ordering_bonus),
            4,
        )
        return SQLReward(
            value=min(value, 1.0),
            correctness=correctness,
            column_match=column_match,
            row_match=row_match,
            executability=executability,
            ordering_bonus=ordering_bonus,
        )
