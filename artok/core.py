"""Core tokenizer loading and counting logic."""

from __future__ import annotations

import importlib
import logging
import os
from dataclasses import dataclass

# Suppress noisy warnings from transformers/tokenizers
os.environ.setdefault("TOKENIZERS_PARALLELISM", "false")
logging.getLogger("transformers").setLevel(logging.ERROR)
logging.getLogger("transformers.utils.hub").setLevel(logging.ERROR)

import sys
import warnings
warnings.filterwarnings("ignore", message=".*PyTorch.*")
warnings.filterwarnings("ignore", message=".*fix_mistral_regex.*")


@dataclass
class TokenizerResult:
    name: str
    tokens: int
    token_ids: list[int]
    vocab_size: int | None = None


@dataclass
class TokenizerInfo:
    name: str
    display_name: str
    backend: str  # "tiktoken" or "transformers"
    model_id: str  # tiktoken encoding name or HF model ID
    cost_input: float | None = None  # $/1M tokens
    cost_output: float | None = None  # $/1M tokens


TOKENIZERS: list[TokenizerInfo] = [
    # --- OpenAI ---
    TokenizerInfo(
        name="gpt4.1",
        display_name="GPT-4.1",
        backend="tiktoken",
        model_id="o200k_base",
        cost_input=2.00,
        cost_output=8.00,
    ),
    TokenizerInfo(
        name="gpt4o",
        display_name="GPT-4o",
        backend="tiktoken",
        model_id="o200k_base",
        cost_input=2.50,
        cost_output=10.00,
    ),
    TokenizerInfo(
        name="gpt4o-mini",
        display_name="GPT-4o mini",
        backend="tiktoken",
        model_id="o200k_base",
        cost_input=0.15,
        cost_output=0.60,
    ),
    TokenizerInfo(
        name="gpt4",
        display_name="GPT-4",
        backend="tiktoken",
        model_id="cl100k_base",
        cost_input=2.50,
        cost_output=10.00,
    ),
    # --- Anthropic ---
    TokenizerInfo(
        name="claude-opus",
        display_name="Claude Opus",
        backend="transformers",
        model_id="Xenova/claude-tokenizer",
        cost_input=5.00,
        cost_output=25.00,
    ),
    TokenizerInfo(
        name="claude-sonnet",
        display_name="Claude Sonnet",
        backend="transformers",
        model_id="Xenova/claude-tokenizer",
        cost_input=3.00,
        cost_output=15.00,
    ),
    TokenizerInfo(
        name="claude-haiku",
        display_name="Claude Haiku",
        backend="transformers",
        model_id="Xenova/claude-tokenizer",
        cost_input=0.80,
        cost_output=4.00,
    ),
    # --- Meta ---
    TokenizerInfo(
        name="llama3",
        display_name="Llama 3",
        backend="transformers",
        model_id="Xenova/llama-3-tokenizer",
        cost_input=0.18,
        cost_output=0.18,
    ),
    # --- Alibaba ---
    TokenizerInfo(
        name="qwen",
        display_name="Qwen 2.5",
        backend="transformers",
        model_id="Qwen/Qwen2.5-7B-Instruct",
        cost_input=0.10,
        cost_output=0.15,
    ),
    # --- Mistral ---
    TokenizerInfo(
        name="mistral",
        display_name="Mistral",
        backend="transformers",
        model_id="mistralai/Mistral-7B-Instruct-v0.3",
        cost_input=0.10,
        cost_output=0.30,
    ),
]

# Cache loaded tokenizers
_cache: dict[str, object] = {}


def _has_package(name: str) -> bool:
    try:
        importlib.import_module(name)
        return True
    except ImportError:
        return False


def _load_tiktoken(encoding_name: str):
    import tiktoken
    key = f"tiktoken:{encoding_name}"
    if key not in _cache:
        _cache[key] = tiktoken.get_encoding(encoding_name)
    return _cache[key]


def _load_hf_tokenizer(model_id: str):
    import io
    # Suppress stderr noise from transformers (PyTorch warnings etc.)
    _stderr = sys.stderr
    sys.stderr = io.StringIO()
    try:
        from transformers import AutoTokenizer
        key = f"hf:{model_id}"
        if key not in _cache:
            _cache[key] = AutoTokenizer.from_pretrained(model_id, trust_remote_code=True)
        return _cache[key]
    finally:
        sys.stderr = _stderr


def count_tokens(text: str, info: TokenizerInfo) -> TokenizerResult | None:
    """Count tokens for text using the specified tokenizer."""
    try:
        if info.backend == "tiktoken":
            if not _has_package("tiktoken"):
                return None
            enc = _load_tiktoken(info.model_id)
            ids = enc.encode(text)
            return TokenizerResult(
                name=info.display_name,
                tokens=len(ids),
                token_ids=ids,
                vocab_size=enc.n_vocab,
            )

        elif info.backend == "transformers":
            if not _has_package("transformers"):
                return None
            tok = _load_hf_tokenizer(info.model_id)
            ids = tok.encode(text, add_special_tokens=False)
            return TokenizerResult(
                name=info.display_name,
                tokens=len(ids),
                token_ids=ids,
                vocab_size=tok.vocab_size,
            )

    except Exception as e:
        return TokenizerResult(
            name=info.display_name,
            tokens=-1,
            token_ids=[],
        )

    return None


def count_all(text: str, only: list[str] | None = None) -> list[tuple[TokenizerInfo, TokenizerResult]]:
    """Count tokens across all available tokenizers."""
    results = []
    for info in TOKENIZERS:
        if only and info.name not in only:
            continue
        # Skip duplicate encoding (gpt4o and gpt4o-mini share o200k_base)
        result = count_tokens(text, info)
        if result and result.tokens > 0:
            results.append((info, result))
    return results


def count_words(text: str) -> int:
    """Count words in text (splits on whitespace)."""
    return len(text.split())
