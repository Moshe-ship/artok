"""CLI entry point for artok."""

from __future__ import annotations

import argparse
import io
import os
import sys

# Suppress PyTorch/transformers stderr noise before any imports
os.environ["TRANSFORMERS_VERBOSITY"] = "error"
_real_stderr = sys.stderr

from artok.core import count_all, TOKENIZERS
from artok.display import display_results, console


def main():
    parser = argparse.ArgumentParser(
        prog="artok",
        description="Arabic Token Tax Calculator - compare token costs across LLM tokenizers",
    )
    parser.add_argument(
        "text",
        nargs="*",
        help="Arabic text to tokenize (or pipe via stdin)",
    )
    parser.add_argument(
        "-e", "--english",
        type=str,
        default=None,
        help="English equivalent text for direct comparison",
    )
    parser.add_argument(
        "-t", "--tokenizers",
        type=str,
        default=None,
        help="Comma-separated list of tokenizers to use (e.g., gpt4o,qwen,llama3)",
    )
    parser.add_argument(
        "--show-tokens",
        action="store_true",
        help="Show individual token IDs",
    )
    parser.add_argument(
        "--list",
        action="store_true",
        help="List available tokenizers",
    )
    parser.add_argument(
        "-f", "--file",
        type=str,
        default=None,
        help="Read text from file",
    )

    args = parser.parse_args()

    if args.list:
        console.print("\n[bold]Available tokenizers:[/bold]\n")
        for t in TOKENIZERS:
            cost = f"${t.cost_input:.2f}/1M" if t.cost_input else "N/A"
            console.print(f"  [cyan]{t.name:12s}[/cyan]  {t.display_name:16s}  {t.backend:14s}  {cost}")
        console.print()
        return

    # Get input text
    text = None
    if args.file:
        with open(args.file, "r", encoding="utf-8") as f:
            text = f.read().strip()
    elif args.text:
        text = " ".join(args.text)
    elif not sys.stdin.isatty():
        text = sys.stdin.read().strip()

    if not text:
        parser.print_help()
        sys.exit(1)

    # Parse tokenizer filter
    only = None
    if args.tokenizers:
        only = [t.strip() for t in args.tokenizers.split(",")]
        valid_names = {t.name for t in TOKENIZERS}
        for name in only:
            if name not in valid_names:
                console.print(f"[red]Unknown tokenizer: {name}[/red]")
                console.print(f"Available: {', '.join(sorted(valid_names))}")
                sys.exit(1)

    # Count tokens
    with console.status("[bold cyan]Loading tokenizers...", spinner="dots"):
        results = count_all(text, only=only)

        english_results = None
        if args.english:
            english_results = count_all(args.english, only=only)

    display_results(
        text=text,
        results=results,
        english_text=args.english,
        english_results=english_results,
        show_tokens=args.show_tokens,
    )


if __name__ == "__main__":
    main()
