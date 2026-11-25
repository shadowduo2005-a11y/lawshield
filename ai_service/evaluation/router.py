"""
router.py – exposes FastAPI endpoints for running benchmark quality evaluations.
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field

from .benchmark import BenchmarkEvaluator

router = APIRouter(prefix="/evaluation", tags=["Evaluation Engine"])

# Module-level evaluator — BenchmarkEvaluator is now safe to instantiate at
# module load because all sub-evaluators and LLM models are lazy-loaded.
evaluator = BenchmarkEvaluator()


# ── Request / Response Models ─────────────────────────────────────────────

class TestCaseModel(BaseModel):
    query: str
    ground_truth: str
    contexts: List[str] = Field(default_factory=list)
    expected_keywords: List[str] = Field(default_factory=list)


class EvaluationRunRequest(BaseModel):
    test_cases: List[TestCaseModel]


# ── Endpoints ─────────────────────────────────────────────────────────────

@router.post(
    "/run",
    status_code=status.HTTP_200_OK,
    summary="Run an evaluation benchmark on a legal QA dataset",
)
async def run_evaluation(request: EvaluationRunRequest) -> Dict[str, Any]:
    """
    Evaluates a dataset of legal QA test cases and returns aggregated metrics:

    - **hallucination_rate** – fraction of claims not grounded in context
    - **retrieval_recall**   – fraction of expected keywords present in context
    - **retrieval_f1**       – harmonic mean of retrieval precision and recall
    - **citation_accuracy**  – fraction of citations verified against source
    - **faithfulness**       – RAGAS faithfulness score
    - **context_recall**     – RAGAS context recall score
    - **response_quality**   – LLM-as-a-judge quality score (0–1)
    - **avg_latency_seconds** – mean wall-clock seconds per case
    - **agent_success_rate** – fraction of test cases that completed without error
    - **per_case_results**   – per-case breakdown for debugging
    """
    if not request.test_cases:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Test cases list cannot be empty.",
        )

    cases = [case.model_dump() for case in request.test_cases]
    try:
        report = evaluator.run_benchmark(cases)
        return report
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(exc),
        )
