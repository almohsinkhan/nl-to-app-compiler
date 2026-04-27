from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path
from typing import Any, Dict, List

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from pipeline.compiler import PipelineCompiler


def _load_prompts(path: Path, limit: int) -> List[str]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    prompts = payload.get("normal_prompts", []) + payload.get("edge_prompts", [])
    return prompts[: max(1, limit)]


def run(limit: int, prompts_path: Path) -> Dict[str, Any]:
    compiler = PipelineCompiler()
    prompts = _load_prompts(prompts_path, limit)

    rows: List[Dict[str, Any]] = []
    latencies: List[int] = []
    retries: List[int] = []

    for prompt in prompts:
        started = time.perf_counter()
        response = compiler.compile(prompt)
        elapsed_ms = int((time.perf_counter() - started) * 1000)

        success = response.valid or bool(response.clarification_questions)
        rows.append(
            {
                "prompt": prompt,
                "success": success,
                "latency_ms": elapsed_ms,
                "retries": response.retries,
                "issues": response.issues,
                "repaired": response.repaired,
            }
        )
        latencies.append(elapsed_ms)
        retries.append(response.retries)

    total = len(rows)
    success_count = sum(1 for row in rows if row["success"])
    success_rate = (success_count / total) * 100 if total else 0.0
    avg_latency = (sum(latencies) / len(latencies)) if latencies else 0.0
    avg_retries = (sum(retries) / len(retries)) if retries else 0.0

    return {
        "success_rate": f"{success_rate:.1f}%",
        "avg_latency": f"{avg_latency:.1f}ms",
        "avg_retries": round(avg_retries, 2),
        "total_cases": total,
        "results": rows,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Run a quick NL App Compiler evaluation.")
    parser.add_argument(
        "--limit",
        type=int,
        default=10,
        help="Number of prompts to run (recommended: 5-10).",
    )
    parser.add_argument(
        "--prompts",
        type=Path,
        default=Path("data/eval_prompts.json"),
        help="Path to prompt dataset JSON.",
    )
    args = parser.parse_args()

    report = run(limit=args.limit, prompts_path=args.prompts)
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
