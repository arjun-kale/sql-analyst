from typing import Dict, List, Optional, Tuple

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
        self._gt_rows = gt
        self._gt_count = len(gt)
        self._gt_names = {r["name"] for r in gt}
        self._gt_by_name: Dict[str, Dict] = {r["name"]: dict(r) for r in gt}
        self._gt_ordered_names = [r["name"] for r in gt]

    def _find_col(self, row: Dict, candidates: Tuple[str, ...]) -> Optional[str]:
        for key in row.keys():
            if key.lower() in candidates:
                return key
        return None

    def grade(self, query: str, result_rows: List[Dict], error: Optional[str]) -> SQLReward:
        if error or not result_rows:
            exec_score = 0.0 if error else 0.1
            return SQLReward(
                value=round(0.05 * exec_score, 4),
                correctness=0.0,
                column_match=0.0,
                row_match=0.0,
                executability=exec_score,
                ordering_bonus=0.0,
            )

        executability = 1.0

        cols = {k.lower() for k in result_rows[0].keys()}
        has_name = "name" in cols
        has_segment = "segment" in cols
        has_spend = any(c in {"total_spend", "spend", "revenue", "amount", "total"} for c in cols)
        has_days = any(
            c in {"days_since_last_order", "days_since", "days", "recency"} for c in cols
        )
        column_match = (
            (0.20 * float(has_name))
            + (0.25 * float(has_segment))
            + (0.35 * float(has_spend))
            + (0.20 * float(has_days))
        )

        # --- Name overlap (churn identification accuracy) ---
        agent_names: List[str] = []
        for r in result_rows:
            name_col = self._find_col(r, ("name",))
            if name_col:
                agent_names.append(r[name_col])

        agent_name_set = set(agent_names)
        name_overlap = len(agent_name_set & self._gt_names)
        name_accuracy = name_overlap / max(self._gt_count, 1)

        # --- Row count penalty ---
        count_ratio = min(len(result_rows), self._gt_count) / max(
            len(result_rows), self._gt_count, 1
        )

        # --- Value accuracy (total_spend + days_since) per matched row ---
        spend_matches = 0
        days_matches = 0
        matched_rows = 0
        for r in result_rows:
            name_col = self._find_col(r, ("name",))
            if not name_col or r[name_col] not in self._gt_by_name:
                continue
            gt = self._gt_by_name[r[name_col]]
            matched_rows += 1

            spend_col = self._find_col(
                r, ("total_spend", "spend", "revenue", "amount", "total")
            )
            if spend_col:
                try:
                    agent_spend = float(r[spend_col])
                    gt_spend = float(gt["total_spend"])
                    if gt_spend > 0 and abs(agent_spend - gt_spend) / gt_spend < 0.02:
                        spend_matches += 1
                except (ValueError, TypeError):
                    pass

            days_col = self._find_col(
                r, ("days_since_last_order", "days_since", "days", "recency")
            )
            if days_col:
                try:
                    agent_days = int(float(r[days_col]))
                    gt_days = int(gt["days_since_last_order"])
                    if abs(agent_days - gt_days) <= 1:
                        days_matches += 1
                except (ValueError, TypeError):
                    pass

        denominator = max(self._gt_count, 1)
        spend_accuracy = spend_matches / denominator
        days_accuracy = days_matches / denominator

        row_match = (
            (0.30 * name_accuracy)
            + (0.20 * count_ratio)
            + (0.30 * spend_accuracy)
            + (0.20 * days_accuracy)
        )

        # --- Ordering: top-10 by total_spend DESC ---
        ordering_bonus = 0.0
        if agent_names:
            top_n = min(10, len(agent_names), len(self._gt_ordered_names))
            if top_n > 0:
                agent_top = agent_names[:top_n]
                gt_top = self._gt_ordered_names[:top_n]
                positional_hits = sum(
                    1 for a, g in zip(agent_top, gt_top) if a == g
                )
                ordering_bonus = positional_hits / top_n

        correctness = row_match * column_match
        value = round(
            (0.05 * executability)
            + (0.20 * column_match)
            + (0.50 * row_match)
            + (0.25 * ordering_bonus),
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
