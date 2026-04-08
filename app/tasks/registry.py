from dataclasses import dataclass
from typing import Dict


@dataclass
class Task:
    id: str
    name: str
    difficulty: str
    description: str
    hint_1: str
    hint_2: str
    max_steps: int


TASKS: Dict[str, Task] = {
    "easy_sales_report": Task(
        id="easy_sales_report",
        name="Monthly Sales Report",
        difficulty="easy",
        description=(
            "You are a BI Analyst. Your task: Find the total revenue by product "
            "category for Q4 2023 (October to December 2023). Only include completed "
            "orders. Order results by revenue descending. Return: category, total_revenue."
        ),
        hint_1="Join orders -> order_items -> products. Filter order_date and status.",
        hint_2="Use GROUP BY p.category and ORDER BY total_revenue DESC.",
        max_steps=8,
    ),
    "medium_customer_ltv": Task(
        id="medium_customer_ltv",
        name="Customer Lifetime Value Analysis",
        difficulty="medium",
        description=(
            "You are a BI Analyst. Find the top 10 customers by total spend in calendar year "
            "2023 (completed orders only). Return: customer id, customer name, order_count "
            "(use COUNT(DISTINCT o.id)), total_spend (rounded to 2 decimals), avg_order_value "
            "(rounded to 2 decimals). Order by total_spend descending."
        ),
        hint_1="Join customers -> orders -> order_items. Filter by year 2023 and status='completed'.",
        hint_2="Use COUNT(DISTINCT o.id) for order count, ROUND(..., 2) for monetary values. LIMIT 10.",
        max_steps=10,
    ),
    "hard_churn_cohort": Task(
        id="hard_churn_cohort",
        name="Monthly Segment Revenue Trend with Growth Analysis",
        difficulty="hard",
        description=(
            "You are a BI Analyst. The VP of Sales wants a monthly performance dashboard "
            "for 2023 broken down by customer segment. For each month and segment, show:\n"
            "  - month (YYYY-MM format), segment, revenue (completed orders, rounded to 2 decimals)\n"
            "  - unique_customers (distinct customers who ordered that month)\n"
            "  - rolling_3m_avg (3-month moving average of revenue, rounded to 2 decimals)\n"
            "  - mom_growth_pct (month-over-month revenue change as %, rounded to 1 decimal, NULL for first month)\n"
            "  - segment_rank (rank of each segment within each month by revenue, highest first)\n\n"
            "Order results by month ascending, then by segment rank ascending."
        ),
        hint_1=(
            "You'll need a CTE or subquery to first aggregate revenue per month+segment, "
            "then compute the derived columns on top of that result. "
            "In SQLite, use strftime('%Y-%m', date_col) to extract month."
        ),
        hint_2=(
            "Window functions are needed for rolling average, growth rate, and ranking. "
            "Each one requires different PARTITION BY and ORDER BY clauses. "
            "For rolling average, use ROWS BETWEEN 2 PRECEDING AND CURRENT ROW."
        ),
        max_steps=20,
    ),
}
