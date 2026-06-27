"""Implements a faithfulness evaluation judge using Ragas.

Note: the Ragas SDK has no ``ragas.llms.LiteLLMWrapper`` class — Groq
access via LiteLLM is provided through LangChain's ``ChatLiteLLM``,
wrapped in Ragas's ``LangchainLLMWrapper`` to satisfy the BaseRagasLLM
interface that the faithfulness metric expects.
"""

from __future__ import annotations

import warnings
from typing import Any, cast

from datasets import Dataset
from langchain_community.chat_models import ChatLiteLLM
from ragas import evaluate
from ragas.dataset_schema import EvaluationResult
from ragas.llms import LangchainLLMWrapper
from ragas.metrics import faithfulness

from src.core.config import get_settings
from src.core.logging_setup import get_logger

logger = get_logger(__name__)


class FaithfulnessJudge:
    """Evaluates agent output faithfulness using Ragas.

    Faithfulness measures whether every claim in the agent's answer is
    grounded in the provided context (source data or tool call
    results). Score range: 0.0 to 1.0. Higher is better.
    """

    THRESHOLD: float = 0.75

    def __init__(self) -> None:
        """Initialize the judge with Groq LLM via LiteLLM."""
        settings = get_settings()
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            chat_model = ChatLiteLLM(model=settings.litellm_model)
            self.llm = LangchainLLMWrapper(chat_model)
        self.metric = faithfulness
        self.metric.llm = self.llm
        logger.info(
            "FaithfulnessJudge initialized", extra={"model": settings.litellm_model}
        )

    def evaluate_dataset(
        self, records: list[dict[str, Any]], dataset_name: str
    ) -> dict[str, Any]:
        """Run faithfulness evaluation on a list of records.

        Each record must have: question, contexts (list[str]), answer,
        ground_truth fields.

        Args:
            records: List of eval record dicts from a JSON dataset.
            dataset_name: Name for logging and reporting.

        Returns:
            Dict with dataset_name, metric, score, passed, threshold,
            record_count, record_level_scores, and error keys. Never
            raises — evaluation failure is reported via the error key.
        """
        try:
            hf_dataset = Dataset.from_list(
                [
                    {
                        "question": record["question"],
                        "contexts": record["contexts"],
                        "answer": record["answer"],
                        "ground_truth": record["ground_truth"],
                    }
                    for record in records
                ]
            )
            result = cast(
                EvaluationResult, evaluate(dataset=hf_dataset, metrics=[self.metric])
            )
            score_df = result.to_pandas()
            mean_score = float(score_df["faithfulness"].mean())
            record_scores = score_df["faithfulness"].tolist()
            passed = mean_score >= self.THRESHOLD

            logger.info(
                "Faithfulness evaluation complete",
                extra={
                    "dataset_name": dataset_name,
                    "score": mean_score,
                    "passed": passed,
                },
            )
            return {
                "dataset_name": dataset_name,
                "metric": "faithfulness",
                "score": mean_score,
                "passed": passed,
                "threshold": self.THRESHOLD,
                "record_count": len(records),
                "record_level_scores": record_scores,
                "error": None,
            }
        except Exception as exc:
            logger.error(
                "Faithfulness evaluation failed",
                exc_info=True,
                extra={"dataset_name": dataset_name},
            )
            return {
                "dataset_name": dataset_name,
                "metric": "faithfulness",
                "score": 0.0,
                "passed": False,
                "threshold": self.THRESHOLD,
                "record_count": len(records),
                "record_level_scores": [],
                "error": str(exc),
            }
