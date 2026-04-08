from typing import Dict, List, Optional, Tuple

from app.graders.base import BaseGrader
from app.models import SQLReward

CANONICAL_QUERY = """
WITH monthly_segment AS (
    SELECT
        strftime('%Y-%m', o.order_date) AS month,
        c.segment,
        ROUND(SUM(oi.quantity * oi.unit_price), 2) AS revenue,
        COUNT(DISTINCT o.customer_id) AS unique_customers
    FROM orders o
    JOIN customers c ON o.customer_id = c.id
    JOIN order_items oi ON o.id = oi.order_id
    WHERE o.status = 'completed'
      AND o.order_date BETWEEN '2023-01-01' AND '2023-12-31'
    GROUP BY strftime('%Y-%m', o.order_date), c.segment
)
SELECT
    month,
    segment,
    revenue,
    unique_customers,
    ROUND(AVG(revenue) OVER (
        PARTITION BY segment
        ORDER BY month
        ROWS BETWEEN 2 PRECEDING AND CURRENT ROW
    ), 2) AS rolling_3m_avg,
    ROUND(
        (revenue - LAG(revenue) OVER (PARTITION BY segment ORDER BY month))
        * 100.0 / LAG(revenue) OVER (PARTITION BY segment ORDER BY month),
    1) AS mom_growth_pct,
    RANK() OVER (PARTITION BY month ORDER BY revenue DESC) AS segment_rank
FROM monthly_segment
ORDER BY month, segment_rank
"""


class HardGrader(BaseGrader):
    def __init__(self, conn):
        super().__init__(conn)
        gt, _ = self._safe_execute(CANONICAL_QUERY)
        self._gt_rows = gt
        self._gt_count = len(gt)
        self._gt_by_key: Dict[Tuple[str, str], Dict] = {}
        self._gt_ordered_keys: List[Tuple[str, str]] = []
        for r in gt:
            key = (r["month"], r["segment"])
            self._gt_by_key[key] = dict(r)
            self._gt_ordered_keys.append(key)

    def _find_col(self, row: Dict, candidates: Tuple[str, ...]) -> Optional[str]:
        for key in row.keys():
            if key.lower() in candidates:
                return key
        return None

    def _extract_key(self, row: Dict) -> Optional[Tuple[str, str]]:
        month_col = self._find_col(row, ("month", "yr_month", "year_month", "period"))
        seg_col = self._find_col(row, ("segment",))
        if month_col and seg_col:
            return (str(row[month_col]), str(row[seg_col]))
        return None

    def _float_close(self, a, b, rel_tol: float = 0.02) -> bool:
        try:
            a, b = float(a), float(b)
        except (ValueError, TypeError):
            return False
        if b == 0:
            return abs(a) < 1.0
        return abs(a - b) / abs(b) < rel_tol

    def _abs_close(self, a, b, abs_tol: float = 0.5) -> bool:
        """For growth percentages where relative tolerance doesn't make sense."""
        try:
            a, b = float(a), float(b)
        except (ValueError, TypeError):
            return False
        return abs(a - b) <= abs_tol

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

        # --- Column matching (7 expected columns) ---
        cols = {k.lower() for k in result_rows[0].keys()}
        has_month = any(c in {"month", "yr_month", "year_month", "period"} for c in cols)
        has_segment = "segment" in cols
        has_revenue = any(c in {"revenue", "total_revenue", "amount"} for c in cols)
        has_customers = any(c in {"unique_customers", "customer_count", "customers"} for c in cols)
        has_rolling = any("rolling" in c or "avg" in c for c in cols)
        has_growth = any("growth" in c or "mom" in c for c in cols)
        has_rank = any("rank" in c for c in cols)

        column_match = (
            (0.10 * float(has_month))
            + (0.10 * float(has_segment))
            + (0.20 * float(has_revenue))
            + (0.10 * float(has_customers))
            + (0.20 * float(has_rolling))
            + (0.15 * float(has_growth))
            + (0.15 * float(has_rank))
        )

        # --- Row count penalty ---
        count_ratio = min(len(result_rows), self._gt_count) / max(
            len(result_rows), self._gt_count, 1
        )

        # --- Value accuracy per matched (month, segment) pair ---
        revenue_ok = 0
        rolling_ok = 0
        growth_ok = 0
        rank_ok = 0
        customers_ok = 0
        matched = 0

        for r in result_rows:
            key = self._extract_key(r)
            if key is None or key not in self._gt_by_key:
                continue
            gt = self._gt_by_key[key]
            matched += 1

            rev_col = self._find_col(r, ("revenue", "total_revenue", "amount"))
            if rev_col and self._float_close(r[rev_col], gt["revenue"]):
                revenue_ok += 1

            roll_col = self._find_col(r, ("rolling_3m_avg", "rolling_avg", "rolling_average"))
            if roll_col and self._float_close(r[roll_col], gt["rolling_3m_avg"]):
                rolling_ok += 1

            growth_col = self._find_col(r, ("mom_growth_pct", "growth_pct", "mom_growth", "growth"))
            if growth_col:
                agent_val = r[growth_col]
                gt_val = gt["mom_growth_pct"]
                if agent_val is None and gt_val is None:
                    growth_ok += 1
                elif agent_val is not None and gt_val is not None:
                    if self._abs_close(agent_val, gt_val, 0.5):
                        growth_ok += 1

            rank_col = self._find_col(r, ("segment_rank", "rank", "seg_rank"))
            if rank_col:
                try:
                    if int(r[rank_col]) == int(gt["segment_rank"]):
                        rank_ok += 1
                except (ValueError, TypeError):
                    pass

            cust_col = self._find_col(
                r, ("unique_customers", "customer_count", "customers", "num_customers")
            )
            if cust_col:
                try:
                    if int(r[cust_col]) == int(gt["unique_customers"]):
                        customers_ok += 1
                except (ValueError, TypeError):
                    pass

        d = max(self._gt_count, 1)
        revenue_acc = revenue_ok / d
        rolling_acc = rolling_ok / d
        growth_acc = growth_ok / d
        rank_acc = rank_ok / d
        customers_acc = customers_ok / d

        row_match = (
            (0.10 * count_ratio)
            + (0.25 * revenue_acc)
            + (0.25 * rolling_acc)
            + (0.20 * growth_acc)
            + (0.10 * rank_acc)
            + (0.10 * customers_acc)
        )

        # --- Ordering: check first 12 rows (months 01-04) ---
        ordering_bonus = 0.0
        agent_keys: List[Tuple[str, str]] = []
        for r in result_rows:
            key = self._extract_key(r)
            if key:
                agent_keys.append(key)

        if agent_keys:
            check_n = min(12, len(agent_keys), len(self._gt_ordered_keys))
            if check_n > 0:
                hits = sum(
                    1 for a, g in zip(agent_keys[:check_n], self._gt_ordered_keys[:check_n])
                    if a == g
                )
                ordering_bonus = hits / check_n

        correctness = row_match * column_match
        value = round(
            (0.05 * executability)
            + (0.15 * column_match)
            + (0.55 * row_match)
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
