from typing import Dict, List, Optional

from app.graders.base import BaseGrader
from app.models import SQLReward

CANONICAL_QUERY = """
WITH q2_active AS (
    SELECT DISTINCT customer_id
    FROM orders
    WHERE order_date BETWEEN '2023-04-01' AND '2023-06-30'
      AND status = 'completed'
),
q3_active AS (
    SELECT DISTINCT customer_id
    FROM orders
    WHERE order_date BETWEEN '2023-07-01' AND '2023-09-30'
      AND status = 'completed'
),
churned AS (
    SELECT q2.customer_id
    FROM q2_active q2
    LEFT JOIN q3_active q3 ON q2.customer_id = q3.customer_id
    WHERE q3.customer_id IS NULL
),
customer_stats AS (
    SELECT o.customer_id,
           ROUND(SUM(oi.quantity * oi.unit_price), 2) AS total_spend,
           MAX(o.order_date) AS last_order_date
    FROM orders o
    JOIN order_items oi ON o.id = oi.order_id
    WHERE o.status = 'completed'
    GROUP BY o.customer_id
)
SELECT c.name,
       c.segment,
       cs.total_spend,
       CAST(julianday('2023-09-30') - julianday(cs.last_order_date) AS INTEGER) AS days_since_last_order
FROM churned ch
JOIN customers c ON ch.customer_id = c.id
JOIN customer_stats cs ON ch.customer_id = cs.customer_id
ORDER BY cs.total_spend DESC
"""


class HardGrader(BaseGrader):
    def __init__(self, conn):
        super().__init__(conn)
        gt, _ = self._safe_execute(CANONICAL_QUERY)
        self._gt_names = {r["name"] for r in gt}
        self._gt_count = len(gt)

    def grade(self, query: str, result_rows: List[Dict], error: Optional[str]) -> SQLReward:
        if error or not result_rows:
            executability = 0.0 if error else 0.1
            return SQLReward(
                value=0.05 * executability,
                correctness=0.0,
                column_match=0.0,
                row_match=0.0,
                executability=executability,
                ordering_bonus=0.0,
            )

        executability = 1.0
        cols = {k.lower() for k in result_rows[0].keys()}
        has_segment = "segment" in cols
        has_spend = any(("spend" in c) or ("revenue" in c) or ("amount" in c) for c in cols)
        has_days = any(("day" in c) or ("last" in c) for c in cols)
        has_name = "name" in cols
        column_match = (
            (0.2 * float(has_name))
            + (0.3 * float(has_segment))
            + (0.35 * float(has_spend))
            + (0.15 * float(has_days))
        )

        # Case-insensitive name extraction
        agent_names: set = set()
        for r in result_rows:
            lower_keys = {k.lower(): k for k in r.keys()}
            if "name" in lower_keys:
                agent_names.add(r[lower_keys["name"]])

        overlap = len(agent_names & self._gt_names)
        row_match = min(overlap / max(self._gt_count, 1), 1.0)

        count_ratio = min(len(result_rows), self._gt_count) / max(
            len(result_rows), self._gt_count, 1
        )
        ordering_bonus = count_ratio

        correctness = row_match * column_match
        value = round(
            (0.1 * executability)
            + (0.25 * column_match)
            + (0.5 * row_match)
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
