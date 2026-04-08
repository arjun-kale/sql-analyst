from typing import Dict, List, Optional, Tuple

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
        self._gt_rows = gt
        self._gt_customer_ids = [r["id"] for r in gt]
        self._gt_spends: Dict[int, float] = {r["id"]: r["total_spend"] for r in gt}
        self._gt_counts: Dict[int, int] = {r["id"]: r["order_count"] for r in gt}

    def _extract_id(self, row: Dict) -> Optional[int]:
        for key, value in row.items():
            if key.lower() in {"id", "customer_id", "cid"}:
                try:
                    return int(value)
                except (ValueError, TypeError):
                    pass
        return None

    def _extract_spend(self, row: Dict) -> Optional[float]:
        for key, value in row.items():
            kl = key.lower()
            if kl in {"total_spend", "spend", "revenue", "amount", "total"}:
                try:
                    return float(value)
                except (ValueError, TypeError):
                    pass
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
        has_name = any("name" in c for c in cols)
        has_spend = any(c in {"total_spend", "spend", "revenue", "amount", "total"} for c in cols)
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
            cid = self._extract_id(row)
            if cid is not None:
                agent_ids.append(cid)

        id_overlap = len(set(agent_ids) & set(self._gt_customer_ids))
        id_match = id_overlap / 10.0

        value_matches = 0
        count_matches = 0
        for row in result_rows[:10]:
            cid = self._extract_id(row)
            spend = self._extract_spend(row)
            if cid is not None and spend is not None and cid in self._gt_spends:
                gt_spend = self._gt_spends[cid]
                if gt_spend > 0 and abs(spend - gt_spend) / gt_spend < 0.01:
                    value_matches += 1
            if cid is not None and cid in self._gt_counts:
                for key, val in row.items():
                    kl = key.lower()
                    if kl in {"order_count", "orders", "count", "num_orders"}:
                        try:
                            if int(val) == self._gt_counts[cid]:
                                count_matches += 1
                        except (ValueError, TypeError):
                            pass
                        break
        value_accuracy = value_matches / 10.0
        count_accuracy = count_matches / 10.0

        row_match = (0.3 * id_match) + (0.5 * value_accuracy) + (0.2 * count_accuracy)

        ordering_bonus = 0.0
        if agent_ids[:5] == self._gt_customer_ids[:5]:
            ordering_bonus = 1.0
        elif agent_ids[:3] == self._gt_customer_ids[:3]:
            ordering_bonus = 0.6
        elif len(agent_ids) >= 2 and agent_ids[:2] == self._gt_customer_ids[:2]:
            ordering_bonus = 0.3

        correctness = row_match * column_match
        value = round(
            (0.10 * executability)
            + (0.25 * column_match)
            + (0.45 * row_match)
            + (0.20 * ordering_bonus),
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
