import json
import os
import time
from typing import List

import httpx
from openai import OpenAI

API_BASE_URL = os.environ.get("API_BASE_URL", "https://api.openai.com/v1")
MODEL_NAME = os.environ.get("MODEL_NAME", "gpt-4o-mini")
API_KEY = os.environ.get("HF_TOKEN", "none")
ENV_BASE_URL = os.environ.get("ENV_URL", "http://localhost:7860")
TASKS = ["easy_sales_report", "medium_customer_ltv", "hard_churn_cohort"]
MAX_STEPS = {"easy_sales_report": 8, "medium_customer_ltv": 10, "hard_churn_cohort": 15}
SUCCESS_THRESHOLD = 0.75
TEMPERATURE = 0.1
MAX_TOKENS = 1000


def log_start(task: str, env: str, model: str) -> None:
    print(f"[START] task={task} env={env} model={model}", flush=True)


def log_step(step: int, action: str, reward: float, done: bool, error) -> None:
    print(
        f"[STEP] step={step} action={json.dumps(action)[:80]} "
        f"reward={reward:.4f} done={done} error={error}",
        flush=True,
    )


def log_end(success: bool, steps: int, score: float, rewards: List[float]) -> None:
    print(
        f"[END] success={success} steps={steps} score={score:.4f} rewards={rewards}",
        flush=True,
    )


def env_reset(task_id: str) -> dict:
    resp = httpx.post(f"{ENV_BASE_URL}/reset", json={"task_id": task_id}, timeout=30)
    resp.raise_for_status()
    return resp.json()


def env_step(sql_query: str) -> dict:
    resp = httpx.post(f"{ENV_BASE_URL}/step", json={"sql_query": sql_query}, timeout=30)
    resp.raise_for_status()
    return resp.json()


def get_sql_action(client: OpenAI, obs: dict, history: List[str]) -> str:
    schema = obs.get("schema_info", "")
    task_desc = obs.get("task_description", "")
    last_result = obs.get("last_result", "None")
    last_error = obs.get("last_error", "")
    hint = obs.get("hint", "")
    hist_str = "\n".join(history[-3:])

    prompt = f"""You are an expert SQL analyst using SQLite.
DATABASE SCHEMA:
{schema}
TASK: {task_desc}
PREVIOUS ATTEMPTS:
{hist_str if hist_str else "None yet."}
LAST RESULT: {last_result}
LAST ERROR: {last_error if last_error else "None"}
{f"HINT: {hint}" if hint else ""}
Write ONLY a valid SQLite SELECT query. No explanation. No markdown. Just SQL.
"""
    try:
        completion = client.chat.completions.create(
            model=MODEL_NAME,
            messages=[{"role": "user", "content": prompt}],
            temperature=TEMPERATURE,
            max_tokens=MAX_TOKENS,
        )
        sql = (completion.choices[0].message.content or "").strip()
        sql = sql.replace("```sql", "").replace("```", "").strip()
        return sql if sql else "SELECT 1"
    except Exception as exc:
        print(f"[DEBUG] LLM call failed: {exc}", flush=True)
        return "SELECT 1"


def run_task(client: OpenAI, task_id: str) -> float:
    log_start(task=task_id, env="SQLAnalyst-Env", model=MODEL_NAME)
    rewards: List[float] = []
    history: List[str] = []
    steps_taken = 0
    score = 0.0
    success = False

    try:
        obs = env_reset(task_id)
        max_steps = MAX_STEPS.get(task_id, 10)

        for step_num in range(1, max_steps + 1):
            if obs.get("done", False):
                break

            sql = get_sql_action(client, obs, history)
            result = env_step(sql)
            obs = result["observation"]
            reward = float(result.get("reward", 0.0))
            done = bool(result.get("done", False))
            error = obs.get("last_error")

            rewards.append(reward)
            history.append(f"Step {step_num}: {sql[:100]} -> reward {reward:.4f}")
            steps_taken = step_num
            log_step(step=step_num, action=sql, reward=reward, done=done, error=error)

            if done:
                break

        best_reward = max(rewards) if rewards else 0.0
        score = min(max(best_reward, 0.0), 1.0)
        success = score >= SUCCESS_THRESHOLD
    except Exception as exc:
        print(f"[DEBUG] Task {task_id} failed: {exc}", flush=True)

    log_end(success=success, steps=steps_taken, score=score, rewards=rewards)
    return score


def main() -> None:
    client = OpenAI(base_url=API_BASE_URL, api_key=API_KEY)
    all_scores: dict = {}

    for task_id in TASKS:
        print(f"\n--- Running task: {task_id} ---", flush=True)
        score = run_task(client, task_id)
        all_scores[task_id] = score
        time.sleep(1)

    print(f"\n=== FINAL SCORES: {all_scores} ===", flush=True)
    avg = sum(all_scores.values()) / len(all_scores)
    print(f"=== AVERAGE SCORE: {avg:.4f} ===", flush=True)


if __name__ == "__main__":
    main()
