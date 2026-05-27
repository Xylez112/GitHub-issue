"""Evaluation script: call local API, compare results against ground truth, compute metrics."""
import json
import sys
from pathlib import Path

import httpx

from .metrics import evaluate_one

TEST_CASES_FILE = Path(__file__).parent / "test_cases.json"
API_URL = "http://localhost:8000/api/analyze"


def _make_id(file_path: str, name: str) -> str:
    """Normalize file_path + name into a canonical identifier.

    Backslashes on Windows are converted to forward slashes for cross-platform matching.
    """
    normalized = file_path.replace("\\", "/")
    return f"{normalized}:{name}"


def load_test_cases() -> list[dict]:
    if not TEST_CASES_FILE.exists():
        print(f"Test cases file not found: {TEST_CASES_FILE}")
        sys.exit(1)
    with open(TEST_CASES_FILE, encoding="utf-8") as f:
        data = json.load(f)
    return data["test_cases"]


async def evaluate_all(timeout: int = 600):
    test_cases = load_test_cases()
    all_results = []

    async with httpx.AsyncClient(timeout=timeout) as client:
        for i, tc in enumerate(test_cases, 1):
            print(f"\n[{i}/{len(test_cases)}] Test: {tc['name']}")
            print(f"  Issue: {tc['issue_url']}")

            resp = await client.post(API_URL, json={
                "issue_url": tc["issue_url"],
                "repo_url": tc["repo_url"],
            })

            if resp.status_code != 200:
                print(f"  [FAIL] API returned {resp.status_code}: {resp.text[:300]}")
                all_results.append({
                    "name": tc["name"],
                    "error": f"HTTP {resp.status_code}",
                })
                continue

            data = resp.json()
            predicted_snippets = data["relevant_snippets"]

            predicted_ids = [
                _make_id(s["file_path"], s["name"])
                for s in predicted_snippets
            ]

            relevant_ids = tc["relevant_snippets"]

            metrics = evaluate_one(predicted_ids, relevant_ids, k_values=[5, 10, 20])

            print(f"  Retrieved: {len(predicted_ids)} snippets")
            print(f"  Relevant (annotated): {len(relevant_ids)}")
            print(f"  MRR: {metrics['mrr']}")
            print(f"  Recall@5:  {metrics['recall@5']}")
            print(f"  Recall@10: {metrics['recall@10']}")
            print(f"  Recall@20: {metrics['recall@20']}")

            for rid in relevant_ids:
                if rid in predicted_ids:
                    rank = predicted_ids.index(rid) + 1
                    print(f"    [HIT] {rid} -> rank {rank}")
                else:
                    print(f"    [MISS] {rid}")

            all_results.append({
                "name": tc["name"],
                **metrics,
            })

    # Summary
    print("\n" + "=" * 60)
    print(f"Summary: {len(all_results)} test case(s)")
    if all_results:
        avg_mrr = sum(r.get("mrr", 0) for r in all_results) / len(all_results)
        print(f"Avg MRR: {avg_mrr:.4f}")
        for k in [5, 10, 20]:
            avg = sum(r.get(f"recall@{k}", 0) for r in all_results) / len(all_results)
            print(f"Avg Recall@{k}: {avg:.4f}")

    return all_results


if __name__ == "__main__":
    import asyncio
    asyncio.run(evaluate_all())
