from typing import Dict, List, Optional

from app.graders.base import BaseGrader
from app.models import SQLReward

CANONICAL_QUERY = """
SELECT p.category,
       ROUND(SUM(oi.quantity * oi.unit_price), 2) AS total_revenue
FROM orders o
JOIN order_items oi ON o.id = oi.order_id
JOIN products p ON oi.product_id = p.id
WHERE o.order_date BETWEEN '2023-10-01' AND '2023-12-31'
  AND o.status = 'completed'
GROUP BY p.category
ORDER BY total_revenue DESC
"""


class EasyGrader(BaseGrader):
    def __init__(self, conn):
        super().__init__(conn)
        self._ground_truth, _ = self._safe_execute(CANONICAL_QUERY)
        self._gt_categories = {r["category"] for r in self._ground_truth}
        self._gt_revenues: Dict[str, float] = {
            r["category"]: r["total_revenue"] for r in self._ground_truth
        }

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

        cols = set(result_rows[0].keys())
        has_category = any("cat" in c.lower() for c in cols)
        has_revenue = any(
            c.lower() in {"total_revenue", "revenue", "total", "amount", "sum"} for c in cols
        )
        column_match = (0.5 * float(has_category)) + (0.5 * float(has_revenue))

        agent_cats: Dict[str, float] = {}
        for row in result_rows:
            cat_val = None
            num_val = None
            for v in row.values():
                if isinstance(v, str) and v in self._gt_categories:
                    cat_val = v
                if isinstance(v, (int, float)) and num_val is None:
                    num_val = float(v)
            if cat_val is not None and num_val is not None:
                agent_cats[cat_val] = num_val

        correct_rows = 0
        for cat, gt_rev in self._gt_revenues.items():
            if cat in agent_cats and abs(agent_cats[cat] - gt_rev) / max(gt_rev, 1) < 0.01:
                correct_rows += 1
        row_match = correct_rows / max(len(self._gt_revenues), 1)

        # Ordering: extract first string value per row (handles any column name)
        agent_order = [
            list(r.values())[0]
            for r in result_rows
            if isinstance(list(r.values())[0], str)
        ]
        gt_order = [r["category"] for r in self._ground_truth]
        ordering_bonus = 1.0 if agent_order[: len(gt_order)] == gt_order else 0.3

        correctness = row_match * column_match
        value = round(
            (0.2 * executability)
            + (0.3 * column_match)
            + (0.35 * row_match)
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
