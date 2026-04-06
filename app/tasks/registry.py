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
            "2023 (completed orders only). Return: customer id, customer name, order_count, "
            "total_spend, avg_order_value. Order by total_spend descending."
        ),
        hint_1="Join customers -> orders -> order_items. Filter by year 2023.",
        hint_2="Use COUNT(DISTINCT o.id) for order count. LIMIT 10.",
        max_steps=10,
    ),
    "hard_churn_cohort": Task(
        id="hard_churn_cohort",
        name="Churn and Cohort Retention Analysis",
        difficulty="hard",
        description=(
            "You are a BI Analyst. Identify churned customers: those who placed at least one "
            "completed order in Q2 2023 (Apr-Jun) but had zero completed orders in Q3 2023 "
            "(Jul-Sep). For each churned customer, return: name, segment, total_spend "
            "(all-time, completed), days_since_last_order (as of 2023-09-30). "
            "Order by total_spend desc."
        ),
        hint_1=(
            "Use CTEs or subqueries to find Q2 active customers and Q3 active customers "
            "separately."
        ),
        hint_2="LEFT JOIN Q2 -> Q3 WHERE Q3.customer_id IS NULL gives churned set.",
        max_steps=15,
    ),
}
