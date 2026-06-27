"""Implements an answer relevance evaluation judge using Ragas.

Note: the Ragas SDK has no ``ragas.llms.LiteLLMWrapper`` class — Groq
access via LiteLLM is provided through LangChain's ``ChatLiteLLM``,
wrapped in Ragas's ``LangchainLLMWrapper``. The installed metric is
named ``answer_relevancy`` in the Ragas SDK; this judge reports it
under the "answer_relevance" label to match the project's reporting
schema.

Likewise, there is no ``ragas.embeddings.FastEmbedEmbeddings`` class.
FastEmbed access is provided through LangChain's
``FastEmbedEmbeddings`` (local ONNX models, no API key required),
wrapped in Ragas's ``LangchainEmbeddingsWrapper``.
"""

from __future__ import annotations

import warnings
from typing import Any, cast

from datasets import Dataset
from langchain_community.chat_models import ChatLiteLLM
from langchain_community.embeddings import FastEmbedEmbeddings
from ragas import evaluate
from ragas.dataset_schema import EvaluationResult
from ragas.embeddings import LangchainEmbeddingsWrapper
from ragas.llms import LangchainLLMWrapper
from ragas.metrics import answer_relevancy

from src.core.config import get_settings
from src.core.logging_setup import get_logger

logger = get_logger(__name__)


class AnswerRelevanceJudge:
    """Evaluates agent output relevance using Ragas.

    Answer Relevance measures whether the agent's output actually
    addresses what was asked. A faithful but off-topic answer scores
    low here. Score range: 0.0 to 1.0.

    Note: answer relevance does NOT require ground_truth — it
    evaluates question-to-answer alignment only. The underlying Ragas
    metric also requires an embeddings model; since Groq has no
    embeddings API and the project's frozen tech stack has no other
    embeddings provider, embeddings are computed locally via FastEmbed
    (ONNX, no API key required). If FastEmbed initialization fails for
    any reason, evaluation falls back to Ragas's default embeddings
    and a non-fatal error is reported via evaluate_dataset's error key
    if that also fails.
    """

    THRESHOLD: float = 0.75

    def __init__(self) -> None:
        """Initialize the judge with Groq LLM via LiteLLM and FastEmbed embeddings."""
        settings = get_settings()
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            chat_model = ChatLiteLLM(model=settings.litellm_model)
            self.llm = LangchainLLMWrapper(chat_model)
        self.metric = answer_relevancy
        self.metric.llm = self.llm

        try:
            with warnings.catch_warnings():
                warnings.simplefilter("ignore")
                fastembed_model = FastEmbedEmbeddings(model_name="BAAI/bge-small-en-v1.5")
                self.embeddings = LangchainEmbeddingsWrapper(fastembed_model)
            self.metric.embeddings = self.embeddings
            logger.info(
                "FastEmbed embeddings initialized", extra={"model": "BAAI/bge-small-en-v1.5"}
            )
        except Exception as exc:
            logger.warning(
                "FastEmbed unavailable — answer_relevance metric will use "
                "fallback embeddings",
                extra={"error": str(exc)},
            )

        logger.info(
            "AnswerRelevanceJudge initialized", extra={"model": settings.litellm_model}
        )

    def evaluate_dataset(
        self, records: list[dict[str, Any]], dataset_name: str
    ) -> dict[str, Any]:
        """Run answer relevance evaluation on a list of records.

        Records need: question, contexts, answer. ground_truth is not
        used by this metric.

        Args:
            records: List of eval record dicts from a JSON dataset.
            dataset_name: Name for logging and reporting.

        Returns:
            Dict with the same structure as
            FaithfulnessJudge.evaluate_dataset, with metric set to
            "answer_relevance". Never raises — evaluation failure is
            reported via the error key.
        """
        try:
            hf_dataset = Dataset.from_list(
                [
                    {
                        "question": record["question"],
                        "contexts": record["contexts"],
                        "answer": record["answer"],
                    }
                    for record in records
                ]
            )
            result = cast(
                EvaluationResult, evaluate(dataset=hf_dataset, metrics=[self.metric])
            )
            score_df = result.to_pandas()
            mean_score = float(score_df["answer_relevancy"].mean())
            record_scores = score_df["answer_relevancy"].tolist()
            passed = mean_score >= self.THRESHOLD

            logger.info(
                "Answer relevance evaluation complete",
                extra={
                    "dataset_name": dataset_name,
                    "score": mean_score,
                    "passed": passed,
                },
            )
            return {
                "dataset_name": dataset_name,
                "metric": "answer_relevance",
                "score": mean_score,
                "passed": passed,
                "threshold": self.THRESHOLD,
                "record_count": len(records),
                "record_level_scores": record_scores,
                "error": None,
            }
        except Exception as exc:
            logger.error(
                "Answer relevance evaluation failed",
                exc_info=True,
                extra={"dataset_name": dataset_name},
            )
            return {
                "dataset_name": dataset_name,
                "metric": "answer_relevance",
                "score": 0.0,
                "passed": False,
                "threshold": self.THRESHOLD,
                "record_count": len(records),
                "record_level_scores": [],
                "error": str(exc),
            }
