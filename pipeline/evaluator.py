from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any, Dict, List

from pipeline.compiler import PipelineCompiler


PROMPTS_PATH = Path("data/eval_prompts.json")


class PipelineEvaluator:
    def __init__(self, compiler: PipelineCompiler):
        self.compiler = compiler

    def run(self) -> Dict[str, Any]:
        payload = json.loads(PROMPTS_PATH.read_text(encoding="utf-8"))
        suites = {
            "normal": payload["normal_prompts"],
            "edge": payload["edge_prompts"],
        }

        results: Dict[str, List[Dict[str, Any]]] = {"normal": [], "edge": []}
        all_latencies: List[int] = []
        total_retries = 0
        failure_types: Dict[str, int] = {}

        for suite_name, prompts in suites.items():
            for prompt in prompts:
                started = time.perf_counter()
                response = self.compiler.compile(prompt)
                elapsed_ms = int((time.perf_counter() - started) * 1000)

                success = response.valid or bool(response.clarification_questions)
                issue_codes = [issue.code for issue in response.issue_details]
                for code in issue_codes:
                    failure_types[code] = failure_types.get(code, 0) + 1

                results[suite_name].append(
                    {
                        "prompt": prompt,
                        "success": success,
                        "valid": response.valid,
                        "clarification_questions": response.clarification_questions,
                        "issues": response.issues,
                        "issue_codes": issue_codes,
                        "repaired": response.repaired,
                        "retries": response.retries,
                        "latency_ms": elapsed_ms,
                    }
                )
                all_latencies.append(elapsed_ms)
                total_retries += response.retries

        total_cases = sum(len(v) for v in results.values())
        total_success = sum(1 for suite in results.values() for item in suite if item["success"])

        return {
            "summary": {
                "total_cases": total_cases,
                "success_rate": round((total_success / total_cases) * 100, 2) if total_cases else 0.0,
                "average_latency_ms": round(sum(all_latencies) / len(all_latencies), 2)
                if all_latencies
                else 0.0,
                "average_retries": round(total_retries / total_cases, 2) if total_cases else 0.0,
                "total_retries": total_retries,
                "failure_types": failure_types,
            },
            "details": results,
        }
