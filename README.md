# artok

**Arabic Token Tax Calculator** - See how much more Arabic costs across LLM tokenizers.

Arabic text uses **2-5x more tokens** than equivalent English text depending on the tokenizer. This means Arabic users pay significantly more for the same AI capabilities. `artok` makes this visible.

## Install

```bash
# Clone and install
git clone https://github.com/Moshe-ship/artok.git
cd artok
python3 -m venv .venv && source .venv/bin/activate
pip install -e ".[all]"
```

## Quick Start

```bash
# Basic: see token counts across all tokenizers
artok "الذكاء الاصطناعي يغير العالم"

# Compare Arabic vs English
artok "الذكاء الاصطناعي" -e "Artificial intelligence"

# Estimate costs at scale (10M tokens)
artok "نص عربي" -e "Arabic text" --cost 10

# JSON output for scripting
artok "مرحبا" --json

# Pipe from stdin
echo "أي نص عربي" | artok

# Read from file
artok -f article.txt

# Filter specific tokenizers
artok "نص" -t gpt4o,claude-sonnet,qwen

# See how tokenizers split the text
artok --show-tokens "عامل"

# List all available tokenizers
artok --list
```

## Supported Tokenizers

| Tokenizer | Model | Input $/1M |
|-----------|-------|-----------|
| GPT-4.1 | o200k_base | $2.00 |
| GPT-4o | o200k_base | $2.50 |
| GPT-4o mini | o200k_base | $0.15 |
| GPT-4 | cl100k_base | $2.50 |
| Claude Opus | claude-tokenizer | $5.00 |
| Claude Sonnet | claude-tokenizer | $3.00 |
| Claude Haiku | claude-tokenizer | $0.80 |
| Llama 3 | llama-3-tokenizer | $0.18 |
| Qwen 2.5 | Qwen2.5-7B | $0.10 |
| Mistral | Mistral-7B-v0.3 | $0.10 |

## Example Output

```
artok "الذكاء الاصطناعي يغير العالم" -e "AI is changing the world"

┏━━━━━━━━━━━━━━━━┳━━━━━━━━┳━━━━━━━━━━┳━━━━━━━━━━━━┳━━━━━━━━━━━━┳━━━━━━━━━━━┳━━━━━━┓
┃ Tokenizer      ┃ Tokens ┃ Tok/Word ┃        Tax ┃ Cost/1M in ┃ EN Tokens ┃ AR/EN┃
┡━━━━━━━━━━━━━━━━╇━━━━━━━━╇━━━━━━━━━━╇━━━━━━━━━━━━╇━━━━━━━━━━━━╇━━━━━━━━━━━╇━━━━━━┩
│ GPT-4o         │     10 │     2.50 │ 1.0x (best)│      $2.50 │         5 │ 2.00x│
│ Qwen 2.5       │     12 │     3.00 │      1.20x │      $0.10 │         5 │ 2.40x│
│ Claude Sonnet  │     25 │     6.25 │      2.50x │      $3.00 │         5 │ 5.00x│
└────────────────┴────────┴──────────┴────────────┴────────────┴───────────┴──────┘

Arabic tax: on average 3.1x more tokens than English for the same meaning
```

## The Arabic Token Tax

Why does this happen? Most LLM tokenizers are trained primarily on English/Latin text. Arabic characters get split into individual bytes or small fragments instead of being recognized as whole words or subwords.

- **GPT-4o** (o200k_base): Best for Arabic at ~1.5-2x vs English
- **Qwen 2.5**: Good Arabic support at ~1.7-2.5x
- **Claude**: Worst for Arabic at ~3.5-5x vs English
- **GPT-4** (cl100k_base): Poor at ~2.7-4x vs English

## License

MIT
