---
title: SQL Analyst Env
emoji: "\U0001F50D"
colorFrom: blue
colorTo: green
sdk: docker
pinned: false
tags:
  - openenv
  - sql
  - reinforcement-learning
  - business-intelligence
license: mit
---

# SQLAnalyst-Env: Business Intelligence SQL Agent Environment

[![OpenEnv](https://img.shields.io/badge/OpenEnv-compliant-brightgreen)](https://github.com/OpenEnv)
[![HuggingFace](https://img.shields.io/badge/HF-Space-yellow)](https://huggingface.co/spaces)

## Overview

SQLAnalyst-Env places an AI agent in the role of a Business Intelligence
analyst at a mid-size e-commerce company. The agent must answer real business
questions by writing and iteratively refining SQL queries against a live
SQLite database containing orders, customers, products, and session data.

This environment models the daily workflow of every data analyst: receive
a business question in natural language, write SQL, inspect results, refine.

## Observation Space

| Field              | Type   | Description                              |
|--------------------|--------|------------------------------------------|
| task_id            | str    | Which task is active                     |
| task_description   | str    | Natural language business question       |
| schema_info        | str    | Full DB schema (CREATE TABLE statements) |
| last_query         | str    | Agent's most recent SQL query            |
| last_result        | str    | JSON of query result (up to 20 rows)     |
| last_error         | str    | SQL error message if query failed        |
| step_number        | int    | Current step in episode                  |
| max_steps          | int    | Max steps for this task                  |
| hint               | str    | Progressive hint (appears after step 3)  |

## Action Space

| Field     | Type | Description                    |
|-----------|------|--------------------------------|
| sql_query | str  | A valid SQLite SELECT statement |

## Tasks

| Task ID               | Difficulty | Max Steps | Description                                        |
|-----------------------|------------|-----------|------------------------------------------------------|
| easy_sales_report     | Easy       | 8         | Revenue by category Q4 2023                          |
| medium_customer_ltv   | Medium     | 10        | Top 10 customers by 2023 spend                       |
| hard_churn_cohort     | Hard       | 20        | Monthly segment revenue trend with window functions  |

## Reward Function

Each step returns a reward in [0.0, 1.0] based on:

- **Executability** (0.10-0.20): Query ran without SQL error
- **Column Match** (0.25-0.30): Correct columns in result set
- **Row Match** (0.35-0.50): Correct data rows vs ground truth
- **Ordering Bonus** (0.15): Correct ORDER BY where specified

Rewards are **deterministic** — SQL result set comparison is mathematically
exact with no LLM-as-judge ambiguity.

## Model Benchmark Results

Benchmarks were run locally against this environment using the current `inference.py` and `ENV_URL=http://127.0.0.1:7860`.

| Model | Provider | Params | Easy | Medium | Hard (steps) | Avg |
|---|---|---:|---:|---:|---:|---:|
| `google/gemma-4-26B-A4B-it` | HF | 26B (4B active) | 1.00 | 1.00 | 1.00 (1) | **1.00** |
| `openai/gpt-oss-120b` | Groq | 120B | 1.00 | 1.00 | 0.98 (2) | **0.99** |
| `Qwen/Qwen2.5-7B-Instruct` | HF | 7B | 1.00 | 1.00 | 0.93 (20) | **0.98** |
| `google/gemma-3n-E4B-it` | HF | 4B | 1.00 | 1.00 | 0.79 (20) | **0.93** |
| `meta-llama/Llama-3.1-8B-Instruct` | HF | 8B | 1.00 | 1.00 | 0.57 (12\*) | **0.86** |

\*Llama 3.1 8B run was cut short at step 12 by HF credit limits; real score likely higher with full 20 steps.

**Key observations:**
- Easy + medium tasks are solvable by all model sizes in 1-2 steps
- The hard task (window functions: rolling average, MoM growth, ranking) creates clear difficulty tiers:
  - **26B+** models solve it in 1-2 steps with near-perfect scores
  - **7-8B** models use all 20 steps and plateau at 0.57-0.93, unable to perfect all window functions simultaneously
  - **4B** models struggle with persistent syntax errors and peak at 0.79
- The reward signal shows smooth improvement trajectories (e.g., Qwen 7B: 0.0 → 0.52 → 0.76 → 0.90 → 0.93)

Scores are deterministic for a given model + prompt loop but may shift if providers update hosted model weights.

## Setup & Usage

### Local

```bash
pip install -r requirements.txt
uvicorn app.main:app --host 0.0.0.0 --port 7860
```

### Docker

```bash
docker build -t sql-analyst-env .
docker run -p 7860:7860 sql-analyst-env
```

### API Endpoints

| Endpoint | Method | Input                         | Output                    |
|----------|--------|-------------------------------|---------------------------|
| /reset   | POST   | `{ "task_id": "..." }`        | SQLObservation            |
| /step    | POST   | `{ "sql_query": "..." }`      | observation, reward, done |
| /state   | GET    | (none)                        | Current state snapshot    |
| /tasks   | GET    | (none)                        | List of available tasks   |
| /health  | GET    | (none)                        | `{ "status": "ok" }`     |

### Run Inference

```bash
export API_BASE_URL=https://api.openai.com/v1
export MODEL_NAME=gpt-4o-mini
export HF_TOKEN=your_openai_key
export ENV_URL=http://localhost:7860
python inference.py
```

## Architecture

```
sql-analyst-env/
├── Dockerfile              # Container definition
├── openenv.yaml            # OpenEnv spec manifest
├── README.md               # This file
├── inference.py            # Baseline agent script (root level)
├── requirements.txt        # Python dependencies
├── app/
│   ├── main.py             # FastAPI server
│   ├── environment.py      # Core state machine
│   ├── models.py           # Pydantic models
│   ├── database.py         # SQLite seed data
│   ├── graders/
│   │   ├── base.py         # Abstract grader
│   │   ├── task_easy.py    # Monthly Sales Report grader
│   │   ├── task_medium.py  # Customer LTV grader
│   │   └── task_hard.py    # Churn Cohort grader
│   └── tasks/
│       └── registry.py     # Task definitions
└── scripts/
    └── validate-submission.sh
```
