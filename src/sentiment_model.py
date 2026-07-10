"""可选 FinBERT 情绪模型与词典 fallback。

FinBERT 作为主引擎时按句子批量推理；依赖、模型或设备不可用时平稳回退到
本地词典模型。文章级聚合仍由本模块末尾的 `analyze_article_sentiment()` 完成。
"""

from __future__ import annotations

import json
import math
import re
from contextlib import nullcontext
from dataclasses import dataclass
from functools import lru_cache
from typing import Any

from src.config import (
    DICTIONARY_DIR,
    FINBERT_MAX_LENGTH,
    FINBERT_MODEL_NAME,
    FINBERT_REVISION,
    SENTIMENT_DEVICE,
    SENTIMENT_ENGINE,
    get_finbert_batch_size,
    get_finbert_loading_mode,
    get_hf_token,
)
from src.topic_risk_tagger import split_sentences


EXPECTED_FINBERT_LABELS = {"positive", "negative", "neutral"}


@dataclass
class SentenceSentiment:
    sentence: str
    p_positive: float
    p_neutral: float
    p_negative: float
    sentiment_score: float
    model_confidence: float


@dataclass
class ArticleSentiment:
    p_positive: float
    p_neutral: float
    p_negative: float
    sentiment_score: float
    model_confidence: float
    evidence_sentence: str
    sentence_results: list[SentenceSentiment]


@dataclass
class FinbertResources:
    tokenizer: Any | None
    model: Any | None
    torch_module: Any | None
    device: str
    label_to_index: dict[str, int]
    status_message: str

    @property
    def available(self) -> bool:
        return self.tokenizer is not None and self.model is not None and self.torch_module is not None


_FALLBACK_NOTICE_SHOWN = False
FINBERT_DOWNLOAD_MESSAGE = "首次启动正在下载 FinBERT 模型（约 440MB），请稍候…"


@lru_cache(maxsize=1)
def load_sentiment_lexicon() -> dict[str, list[str]]:
    path = DICTIONARY_DIR / "sentiment_lexicon.json"
    try:
        with path.open("r", encoding="utf-8") as file:
            return json.load(file)
    except (OSError, json.JSONDecodeError):
        return {"positive": [], "negative": [], "uncertainty": []}


def normalize_finbert_label(label: str) -> str:
    lowered = str(label or "").lower()
    if "pos" in lowered:
        return "positive"
    if "neg" in lowered:
        return "negative"
    if "neu" in lowered:
        return "neutral"
    return lowered


def build_label_to_index(id2label: dict[Any, Any]) -> dict[str, int]:
    """动态解析 FinBERT 标签顺序，避免把 negative/neutral 静默互换。"""
    label_to_index: dict[str, int] = {}
    for index, label in id2label.items():
        normalized_label = normalize_finbert_label(str(label))
        if normalized_label in EXPECTED_FINBERT_LABELS:
            label_to_index[normalized_label] = int(index)

    missing_labels = EXPECTED_FINBERT_LABELS - set(label_to_index)
    if missing_labels:
        raise ValueError(f"FinBERT 标签映射缺失: {sorted(missing_labels)}; id2label={id2label}")
    if len(set(label_to_index.values())) != len(EXPECTED_FINBERT_LABELS):
        raise ValueError(f"FinBERT 标签映射索引重复: {label_to_index}")
    return label_to_index


def validate_label_mapping(label_to_index: dict[str, int], id2label: dict[Any, Any]) -> None:
    """启动时做一次映射测试；ProsusAI/finbert 常见顺序为 0 positive, 1 negative, 2 neutral。"""
    test_probabilities = [0.0] * (max(label_to_index.values()) + 1)
    test_probabilities[label_to_index["positive"]] = 0.7
    test_probabilities[label_to_index["negative"]] = 0.2
    test_probabilities[label_to_index["neutral"]] = 0.1
    p_positive, p_neutral, p_negative = probabilities_from_finbert(label_to_index, test_probabilities)
    if (p_positive, p_neutral, p_negative) != (0.7, 0.1, 0.2):
        raise ValueError(f"FinBERT 标签映射测试失败: id2label={id2label}; map={label_to_index}")


def resolve_device(torch_module: Any) -> str:
    configured_device = SENTIMENT_DEVICE.lower().strip()
    if configured_device == "auto":
        return "cuda" if torch_module.cuda.is_available() else "cpu"
    if configured_device == "cuda":
        if not torch_module.cuda.is_available():
            raise RuntimeError("配置 SENTIMENT_DEVICE=cuda，但当前 torch.cuda.is_available() 为 False")
        return "cuda"
    if configured_device == "cpu":
        return "cpu"
    raise ValueError("SENTIMENT_DEVICE 只能是 auto/cuda/cpu")


def pretrained_kwargs(local_files_only: bool) -> dict[str, Any]:
    kwargs: dict[str, Any] = {
        "revision": FINBERT_REVISION,
        "local_files_only": local_files_only,
    }
    token = get_hf_token()
    if token:
        kwargs["token"] = token
    return kwargs


def load_pretrained_pair(auto_tokenizer: Any, auto_model: Any, local_files_only: bool) -> tuple[Any, Any]:
    kwargs = pretrained_kwargs(local_files_only)
    tokenizer = auto_tokenizer.from_pretrained(FINBERT_MODEL_NAME, **kwargs)
    model = auto_model.from_pretrained(FINBERT_MODEL_NAME, **kwargs)
    return tokenizer, model


def is_cache_miss_error(exc: Exception) -> bool:
    current: BaseException | None = exc
    visited: set[int] = set()
    while current is not None and id(current) not in visited:
        visited.add(id(current))
        if isinstance(current, OSError) or current.__class__.__name__ == "LocalEntryNotFoundError":
            return True
        current = current.__cause__ or current.__context__
    return False


def finbert_download_context() -> Any:
    print(FINBERT_DOWNLOAD_MESSAGE)
    try:
        import streamlit as st
        from streamlit.runtime.scriptrunner import get_script_run_ctx

        if get_script_run_ctx(suppress_warning=True) is not None:
            return st.spinner(FINBERT_DOWNLOAD_MESSAGE)
    except Exception:  # noqa: BLE001 - spinner is optional outside Streamlit runtime
        pass
    return nullcontext()


def load_cached_or_download(auto_tokenizer: Any, auto_model: Any) -> tuple[Any, Any]:
    try:
        return load_pretrained_pair(auto_tokenizer, auto_model, local_files_only=True)
    except Exception as cache_exc:  # noqa: BLE001 - only cache-miss errors enter the network retry
        if not is_cache_miss_error(cache_exc):
            raise
        if get_finbert_loading_mode() == "offline":
            raise RuntimeError("FinBERT 缓存未命中，且 FINBERT_LOCAL_FILES_ONLY=1 已启用严格离线模式。") from cache_exc
        with finbert_download_context():
            return load_pretrained_pair(auto_tokenizer, auto_model, local_files_only=False)


@lru_cache(maxsize=1)
def load_finbert_resources() -> FinbertResources:
    if SENTIMENT_ENGINE.lower() not in {"finbert", "auto"}:
        return FinbertResources(
            tokenizer=None,
            model=None,
            torch_module=None,
            device="lexicon",
            label_to_index={},
            status_message="当前情绪引擎：词典 fallback。FinBERT 未在配置中启用。",
        )

    try:
        import torch
        from transformers import AutoModelForSequenceClassification, AutoTokenizer
    except ImportError as exc:
        return FinbertResources(
            tokenizer=None,
            model=None,
            torch_module=None,
            device="lexicon",
            label_to_index={},
            status_message=f"当前情绪引擎：词典 fallback。FinBERT 依赖不可用（{exc}）。",
        )

    try:
        device = resolve_device(torch)
        tokenizer, model = load_cached_or_download(AutoTokenizer, AutoModelForSequenceClassification)
        label_to_index = build_label_to_index(model.config.id2label)
        validate_label_mapping(label_to_index, model.config.id2label)
        model.to(torch.device(device))
        model.eval()
    except Exception as exc:  # noqa: BLE001 - 模型不可用时必须平稳回退
        return FinbertResources(
            tokenizer=None,
            model=None,
            torch_module=None,
            device="lexicon",
            label_to_index={},
            status_message=f"当前情绪引擎：词典 fallback。FinBERT 不可用（{exc}）。",
        )

    return FinbertResources(
        tokenizer=tokenizer,
        model=model,
        torch_module=torch,
        device=device,
        label_to_index=label_to_index,
        status_message=f"当前情绪引擎：FinBERT ({device})",
    )


def sentiment_backend_status() -> str:
    return load_finbert_resources().status_message


def count_terms(text: str, terms: list[str]) -> int:
    lowered = text.lower()
    total = 0
    for term in terms:
        pattern = re.escape(term.lower())
        total += len(re.findall(pattern, lowered))
    return total


def softmax(values: list[float]) -> list[float]:
    max_value = max(values)
    exp_values = [math.exp(value - max_value) for value in values]
    total = sum(exp_values)
    return [value / total for value in exp_values]


def notice_finbert_fallback_once(message: str) -> None:
    global _FALLBACK_NOTICE_SHOWN
    if _FALLBACK_NOTICE_SHOWN:
        return
    _FALLBACK_NOTICE_SHOWN = True
    print(f"提示：{message}")


def probabilities_from_finbert(label_to_index: dict[str, int], probabilities: list[float]) -> tuple[float, float, float]:
    p_positive = float(probabilities[label_to_index["positive"]])
    p_neutral = float(probabilities[label_to_index["neutral"]])
    p_negative = float(probabilities[label_to_index["negative"]])
    return p_positive, p_neutral, p_negative


def sentence_sentiment_from_probabilities(sentence: str, probabilities: list[float], label_to_index: dict[str, int]) -> SentenceSentiment:
    p_positive, p_neutral, p_negative = probabilities_from_finbert(label_to_index, probabilities)
    sentiment_score = p_positive - p_negative
    confidence = max(p_positive, p_neutral, p_negative)
    return SentenceSentiment(
        sentence=sentence,
        p_positive=p_positive,
        p_neutral=p_neutral,
        p_negative=p_negative,
        sentiment_score=sentiment_score,
        model_confidence=confidence,
    )


def score_sentences_finbert(sentences: list[str]) -> list[SentenceSentiment] | None:
    resources = load_finbert_resources()
    if not resources.available:
        notice_finbert_fallback_once(resources.status_message)
        return None

    results: list[SentenceSentiment] = []
    try:
        batch_size = get_finbert_batch_size()
        for start in range(0, len(sentences), batch_size):
            batch_sentences = [str(sentence or "") for sentence in sentences[start : start + batch_size]]
            inputs = resources.tokenizer(
                batch_sentences,
                return_tensors="pt",
                padding=True,
                truncation=True,
                max_length=FINBERT_MAX_LENGTH,
            )
            inputs = {key: value.to(resources.device) for key, value in inputs.items()}
            with resources.torch_module.no_grad():
                outputs = resources.model(**inputs)
                batch_probabilities = resources.torch_module.softmax(outputs.logits, dim=1).detach().cpu().tolist()
            results.extend(
                sentence_sentiment_from_probabilities(sentence, probabilities, resources.label_to_index)
                for sentence, probabilities in zip(batch_sentences, batch_probabilities, strict=True)
            )
    except Exception as exc:  # noqa: BLE001 - 批量推理失败时整批回退词典模型
        notice_finbert_fallback_once(f"FinBERT 推理失败（{exc}），已回退到词典情绪模型。")
        return None

    return results


def score_sentence_lexicon(sentence: str) -> SentenceSentiment:
    lexicon = load_sentiment_lexicon()
    positive_hits = count_terms(sentence, lexicon.get("positive", []))
    negative_hits = count_terms(sentence, lexicon.get("negative", []))
    uncertainty_hits = count_terms(sentence, lexicon.get("uncertainty", []))

    raw_positive = 0.4 + positive_hits * 1.2
    raw_negative = 0.4 + negative_hits * 1.2
    raw_neutral = 0.8 + uncertainty_hits * 0.5
    p_positive, p_neutral, p_negative = softmax([raw_positive, raw_neutral, raw_negative])
    sentiment_score = p_positive - p_negative
    confidence = max(p_positive, p_neutral, p_negative)

    return SentenceSentiment(
        sentence=sentence,
        p_positive=p_positive,
        p_neutral=p_neutral,
        p_negative=p_negative,
        sentiment_score=sentiment_score,
        model_confidence=confidence,
    )


def score_sentences_lexicon(sentences: list[str]) -> list[SentenceSentiment]:
    return [score_sentence_lexicon(sentence) for sentence in sentences]


def score_sentences(sentences: list[str]) -> list[SentenceSentiment]:
    finbert_results = score_sentences_finbert(sentences)
    if finbert_results is not None:
        return finbert_results
    return score_sentences_lexicon(sentences)


def score_sentence(sentence: str) -> SentenceSentiment:
    return score_sentences([sentence])[0]


def weighted_average(values: list[float], weights: list[float]) -> float:
    total_weight = sum(weights)
    if total_weight <= 0:
        return sum(values) / len(values)
    return sum(value * weight for value, weight in zip(values, weights, strict=True)) / total_weight


def article_sentences(title: str, summary: str, content: str) -> list[str]:
    text = " ".join([str(title or ""), str(summary or ""), str(content or "")]).strip()
    return split_sentences(text) or [str(title or "")]


def aggregate_article_sentiment(title: str, sentence_results: list[SentenceSentiment]) -> ArticleSentiment:
    weights = [max(result.model_confidence, 0.1) for result in sentence_results]

    p_positive = weighted_average([result.p_positive for result in sentence_results], weights)
    p_neutral = weighted_average([result.p_neutral for result in sentence_results], weights)
    p_negative = weighted_average([result.p_negative for result in sentence_results], weights)
    total = p_positive + p_neutral + p_negative
    p_positive, p_neutral, p_negative = p_positive / total, p_neutral / total, p_negative / total

    sentiment_score = p_positive - p_negative
    confidence = max(p_positive, p_neutral, p_negative)

    evidence_candidates = [
        result
        for result in sentence_results
        if result.model_confidence >= 0.6
    ]
    if evidence_candidates:
        evidence = max(evidence_candidates, key=lambda item: abs(item.sentiment_score)).sentence
    else:
        evidence = str(title or "")

    return ArticleSentiment(
        p_positive=p_positive,
        p_neutral=p_neutral,
        p_negative=p_negative,
        sentiment_score=sentiment_score,
        model_confidence=confidence,
        evidence_sentence=evidence,
        sentence_results=sentence_results,
    )


def analyze_articles_sentiment(articles: list[tuple[str, str, str]]) -> list[ArticleSentiment]:
    """跨文章收集句子后按当前 FINBERT_BATCH_SIZE 环境配置批量推理。"""
    sentence_groups = [
        article_sentences(title, summary, content)
        for title, summary, content in articles
    ]
    flat_sentences = [sentence for sentences in sentence_groups for sentence in sentences]
    flat_results = score_sentences(flat_sentences)

    article_results: list[ArticleSentiment] = []
    cursor = 0
    for (title, _summary, _content), sentences in zip(articles, sentence_groups, strict=True):
        next_cursor = cursor + len(sentences)
        article_results.append(aggregate_article_sentiment(title, flat_results[cursor:next_cursor]))
        cursor = next_cursor
    return article_results


def analyze_article_sentiment(title: str, summary: str, content: str) -> ArticleSentiment:
    """单篇文章入口；保留兼容性，内部复用批量接口。"""
    return analyze_articles_sentiment([(title, summary, content)])[0]
