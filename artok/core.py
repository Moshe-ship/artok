"""Core tokenizer loading and counting logic."""

from __future__ import annotations

import importlib
import json
import logging
import os
import time
from dataclasses import dataclass
from pathlib import Path

# Suppress noisy warnings from transformers/tokenizers
os.environ.setdefault("TOKENIZERS_PARALLELISM", "false")
logging.getLogger("transformers").setLevel(logging.ERROR)
logging.getLogger("transformers.utils.hub").setLevel(logging.ERROR)

import sys
import warnings
warnings.filterwarnings("ignore", message=".*PyTorch.*")
warnings.filterwarnings("ignore", message=".*fix_mistral_regex.*")


# ---------------------------------------------------------------------------
# Remote config: fetch tokenizer pricing from GitHub, cache locally 24h
# ---------------------------------------------------------------------------

_REMOTE_URL = "https://raw.githubusercontent.com/Moshe-ship/artok/main/tokenizers.json"
_CACHE_DIR = Path.home() / ".cache" / "artok"
_CACHE_FILE = _CACHE_DIR / "tokenizers.json"
_CACHE_TTL = 86400  # 24 hours


def _fetch_remote_config() -> list[dict] | None:
    """Fetch tokenizers.json from GitHub. Returns list of dicts or None."""
    import urllib.request
    try:
        req = urllib.request.Request(_REMOTE_URL, headers={"User-Agent": "artok"})
        with urllib.request.urlopen(req, timeout=5) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        return data.get("tokenizers")
    except Exception:
        return None


def _read_cache() -> list[dict] | None:
    """Read cached config if fresh (< 24h old)."""
    try:
        if _CACHE_FILE.exists():
            age = time.time() - _CACHE_FILE.stat().st_mtime
            if age < _CACHE_TTL:
                data = json.loads(_CACHE_FILE.read_text("utf-8"))
                return data.get("tokenizers")
    except Exception:
        pass
    return None


def _write_cache(tokenizers: list[dict]):
    """Write fetched config to local cache."""
    try:
        _CACHE_DIR.mkdir(parents=True, exist_ok=True)
        data = {"tokenizers": tokenizers, "cached_at": time.time()}
        _CACHE_FILE.write_text(json.dumps(data, indent=2), "utf-8")
    except Exception:
        pass


def _load_remote_tokenizers() -> list[TokenizerInfo] | None:
    """Try cache first, then remote. Returns list of TokenizerInfo or None."""
    # 1. Try local cache
    cached = _read_cache()
    if cached:
        return _dicts_to_infos(cached)

    # 2. Try remote
    remote = _fetch_remote_config()
    if remote:
        _write_cache(remote)
        return _dicts_to_infos(remote)

    return None


def _dicts_to_infos(dicts: list[dict]) -> list[TokenizerInfo]:
    """Convert list of dicts to list of TokenizerInfo."""
    result = []
    for d in dicts:
        result.append(TokenizerInfo(
            name=d["name"],
            display_name=d["display_name"],
            backend=d["backend"],
            model_id=d["model_id"],
            cost_input=d.get("cost_input"),
            cost_output=d.get("cost_output"),
        ))
    return result


def force_update() -> tuple[bool, str]:
    """Force-fetch latest tokenizer config from GitHub, bypassing cache.
    Returns (success, message)."""
    global TOKENIZERS
    remote = _fetch_remote_config()
    if remote:
        _write_cache(remote)
        TOKENIZERS = _dicts_to_infos(remote)
        return True, f"Updated {len(TOKENIZERS)} tokenizers from remote config."
    return False, "Failed to fetch remote config. Using local defaults."


def get_config_info() -> dict:
    """Return info about current config source."""
    info = {"tokenizers": len(TOKENIZERS), "source": "built-in"}
    try:
        if _CACHE_FILE.exists():
            age = time.time() - _CACHE_FILE.stat().st_mtime
            info["source"] = "cached"
            info["cache_age_hours"] = round(age / 3600, 1)
            data = json.loads(_CACHE_FILE.read_text("utf-8"))
            if "tokenizers" in data:
                info["cached_count"] = len(data["tokenizers"])
    except Exception:
        pass
    return info


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
        name="gpt4.1-mini",
        display_name="GPT-4.1 mini",
        backend="tiktoken",
        model_id="o200k_base",
        cost_input=0.40,
        cost_output=1.60,
    ),
    TokenizerInfo(
        name="gpt4.1-nano",
        display_name="GPT-4.1 nano",
        backend="tiktoken",
        model_id="o200k_base",
        cost_input=0.10,
        cost_output=0.40,
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
    # --- Anthropic ---
    TokenizerInfo(
        name="claude-opus",
        display_name="Claude Opus 4.6",
        backend="transformers",
        model_id="Xenova/claude-tokenizer",
        cost_input=5.00,
        cost_output=25.00,
    ),
    TokenizerInfo(
        name="claude-sonnet",
        display_name="Claude Sonnet 4.6",
        backend="transformers",
        model_id="Xenova/claude-tokenizer",
        cost_input=3.00,
        cost_output=15.00,
    ),
    TokenizerInfo(
        name="claude-haiku",
        display_name="Claude Haiku 4.5",
        backend="transformers",
        model_id="Xenova/claude-tokenizer",
        cost_input=1.00,
        cost_output=5.00,
    ),
    # --- Meta ---
    TokenizerInfo(
        name="llama4",
        display_name="Llama 4",
        backend="transformers",
        model_id="unsloth/Llama-4-Scout-17B-16E-Instruct",
        cost_input=0.18,
        cost_output=0.18,
    ),
    # --- Alibaba ---
    TokenizerInfo(
        name="qwen3.5",
        display_name="Qwen 3.5",
        backend="transformers",
        model_id="Qwen/Qwen3.5-4B",
        cost_input=0.10,
        cost_output=0.40,
    ),
    # --- Mistral ---
    TokenizerInfo(
        name="mistral-large",
        display_name="Mistral Large 3",
        backend="transformers",
        model_id="mistralai/Mistral-Small-3.1-24B-Instruct-2503",
        cost_input=0.50,
        cost_output=1.50,
    ),
    TokenizerInfo(
        name="mistral-small",
        display_name="Mistral Small",
        backend="transformers",
        model_id="mistralai/Mistral-Small-3.1-24B-Instruct-2503",
        cost_input=0.10,
        cost_output=0.30,
    ),
    # --- Google ---
    TokenizerInfo(
        name="gemini-pro",
        display_name="Gemini 2.5 Pro",
        backend="transformers",
        model_id="unsloth/gemma-3-1b-it",
        cost_input=1.25,
        cost_output=10.00,
    ),
    TokenizerInfo(
        name="gemini-flash",
        display_name="Gemini 3 Flash",
        backend="transformers",
        model_id="unsloth/gemma-3-1b-it",
        cost_input=0.50,
        cost_output=3.00,
    ),
    # --- DeepSeek ---
    TokenizerInfo(
        name="deepseek",
        display_name="DeepSeek V3.2",
        backend="tokenizer_fast",
        model_id="deepseek-ai/DeepSeek-V3.2",
        cost_input=0.27,
        cost_output=1.10,
    ),
    # --- xAI ---
    TokenizerInfo(
        name="grok",
        display_name="Grok 2",
        backend="transformers",
        model_id="alvarobartt/grok-2-tokenizer",
        cost_input=2.00,
        cost_output=10.00,
    ),
    # --- Cohere ---
    TokenizerInfo(
        name="command-r",
        display_name="Command R+",
        backend="transformers",
        model_id="Xenova/c4ai-command-r-v01-tokenizer",
        cost_input=2.50,
        cost_output=10.00,
    ),
    # --- AI21 ---
    TokenizerInfo(
        name="jamba",
        display_name="Jamba 1.5",
        backend="transformers",
        model_id="ai21labs/Jamba-v0.1",
        cost_input=0.20,
        cost_output=0.40,
    ),
]

# Try loading remote/cached config (overrides hardcoded list with fresh pricing)
_remote = _load_remote_tokenizers()
if _remote:
    TOKENIZERS = _remote

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


def _load_tokenizer_fast(model_id: str):
    """Load tokenizer directly from tokenizer.json (for models with broken AutoTokenizer)."""
    import io
    _stderr = sys.stderr
    sys.stderr = io.StringIO()
    try:
        from transformers import PreTrainedTokenizerFast
        from huggingface_hub import hf_hub_download
        key = f"fast:{model_id}"
        if key not in _cache:
            path = hf_hub_download(model_id, "tokenizer.json")
            _cache[key] = PreTrainedTokenizerFast(tokenizer_file=path)
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

        elif info.backend == "tokenizer_fast":
            if not _has_package("transformers"):
                return None
            tok = _load_tokenizer_fast(info.model_id)
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


def decode_tokens(info: TokenizerInfo, token_ids: list[int]) -> list[str]:
    """Decode individual token IDs back to text pieces."""
    try:
        if info.backend == "tiktoken":
            enc = _load_tiktoken(info.model_id)
            return [enc.decode([tid]) for tid in token_ids]
        elif info.backend == "transformers":
            tok = _load_hf_tokenizer(info.model_id)
            return [tok.decode([tid]) for tid in token_ids]
        elif info.backend == "tokenizer_fast":
            tok = _load_tokenizer_fast(info.model_id)
            return [tok.decode([tid]) for tid in token_ids]
    except Exception:
        return [f"[{tid}]" for tid in token_ids]
    return []


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


# ---------------------------------------------------------------------------
# Built-in benchmark corpus
# ---------------------------------------------------------------------------

BENCHMARK_CORPUS = {
    "News (MSA)": "أعلن رئيس الوزراء عن خطة اقتصادية جديدة تهدف إلى تعزيز النمو وخفض معدلات البطالة في البلاد خلال السنوات الخمس المقبلة",
    "Poetry": "قف على الأطلال واسأل هل يجيبك رسم دار محاها القدم والأمطار",
    "Quran": "بسم الله الرحمن الرحيم الحمد لله رب العالمين الرحمن الرحيم مالك يوم الدين",
    "Technical": "يعتمد التعلم العميق على الشبكات العصبية الاصطناعية متعددة الطبقات لمعالجة البيانات واستخراج الأنماط المعقدة",
    "Conversational": "كيف حالك اليوم؟ إن شاء الله بخير. أريد أن أسألك عن موعد الاجتماع القادم",
    "Dialect (Egyptian)": "إيه الأخبار؟ عامل إيه النهاردة؟ تعالى نتغدى مع بعض في المطعم اللي جنب البيت",
    "Dialect (Gulf)": "شلونك؟ شخبارك اليوم؟ يلا نروح السوق ونشتري شي حق العشاء",
    "Social Media": "الذكاء الاصطناعي هيغير كل حاجة في حياتنا 🚀 مين موافق؟ #تقنية #مستقبل",
}


# ---------------------------------------------------------------------------
# Built-in dialect samples
# ---------------------------------------------------------------------------

DIALECT_SAMPLES = {
    "MSA": "أريد أن أذهب إلى المطعم لتناول طعام الغداء مع أصدقائي",
    "Egyptian": "عايز أروح المطعم أتغدى مع صحابي",
    "Gulf": "أبي أروح المطعم أتغدى مع ربعي",
    "Levantine": "بدي روح عالمطعم تغدى مع رفقاتي",
    "Moroccan": "بغيت نمشي للريسطو نتغداو مع صحابي",
}
