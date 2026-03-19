"""CLI entry point for artok."""

from __future__ import annotations

import argparse
import io
import json
import os
import sys

# Suppress PyTorch/transformers stderr noise before any imports
os.environ["TRANSFORMERS_VERBOSITY"] = "error"
_real_stderr = sys.stderr

from artok.core import count_all, count_words, decode_tokens, TOKENIZERS
from artok.display import (
    display_results,
    display_json,
    display_chart,
    display_recommend,
    display_viz,
    console,
)


def _read_batch_file(path: str) -> list[dict]:
    """Read a JSONL or CSV batch file. Returns list of {text, english?} dicts."""
    items = []
    if path.endswith(".jsonl") or path.endswith(".ndjson"):
        with open(path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    obj = json.loads(line)
                    items.append({
                        "text": obj.get("text", obj.get("arabic", "")),
                        "english": obj.get("english", obj.get("en", None)),
                    })
    elif path.endswith(".csv"):
        import csv
        with open(path, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                items.append({
                    "text": row.get("text", row.get("arabic", "")),
                    "english": row.get("english", row.get("en", None)),
                })
    else:
        # Plain text file — each line is a separate text
        with open(path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    items.append({"text": line, "english": None})
    return items


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
    parser.add_argument(
        "-c", "--cost",
        type=float,
        default=None,
        metavar="VOLUME",
        help="Estimate costs for VOLUME million tokens of Arabic text",
    )
    parser.add_argument(
        "-w", "--words",
        type=float,
        default=None,
        metavar="WORD_COUNT",
        help="Estimate tokens and costs for WORD_COUNT million words of Arabic (accounts for token expansion)",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Output results as JSON (for scripting/piping)",
    )
    parser.add_argument(
        "--chart",
        action="store_true",
        help="Show a visual bar chart of token counts",
    )
    parser.add_argument(
        "--viz",
        type=str,
        default=None,
        metavar="TOKENIZER",
        help="Visualize how a tokenizer splits the text (e.g., --viz gpt4o)",
    )
    parser.add_argument(
        "--batch",
        type=str,
        default=None,
        metavar="FILE",
        help="Batch mode: process multiple texts from JSONL/CSV file and show aggregate stats",
    )
    parser.add_argument(
        "--recommend",
        type=float,
        default=None,
        metavar="BUDGET",
        help="Recommend the best tokenizer for a monthly budget of $BUDGET",
    )

    args = parser.parse_args()

    if args.list:
        console.print("\n[bold]Available tokenizers:[/bold]\n")
        for t in TOKENIZERS:
            cost = f"${t.cost_input:.2f}/1M" if t.cost_input else "N/A"
            console.print(f"  [cyan]{t.name:14s}[/cyan]  {t.display_name:16s}  {t.backend:14s}  {cost}")
        console.print()
        return

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

    # --- Batch mode ---
    if args.batch:
        items = _read_batch_file(args.batch)
        if not items:
            console.print("[red]No items found in batch file.[/red]")
            sys.exit(1)

        with console.status(f"[bold cyan]Processing {len(items)} items...", spinner="dots"):
            all_results = []
            for item in items:
                results = count_all(item["text"], only=only)
                en_results = None
                if item.get("english"):
                    en_results = count_all(item["english"], only=only)
                all_results.append((item, results, en_results))

        _display_batch(all_results, args.json)
        return

    # --- Get input text ---
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

    # Count tokens
    with console.status("[bold cyan]Loading tokenizers...", spinner="dots"):
        results = count_all(text, only=only)

        english_results = None
        if args.english:
            english_results = count_all(args.english, only=only)

    # --- Recommend mode ---
    if args.recommend is not None:
        display_recommend(
            text=text,
            results=results,
            english_results=english_results,
            budget=args.recommend,
            word_volume=args.words,
        )
        return

    # --- JSON output ---
    if args.json:
        display_json(
            text=text,
            results=results,
            english_text=args.english,
            english_results=english_results,
            cost_volume=args.cost,
            word_volume=args.words,
        )
        return

    # --- Standard display ---
    display_results(
        text=text,
        results=results,
        english_text=args.english,
        english_results=english_results,
        show_tokens=args.show_tokens,
        cost_volume=args.cost,
        word_volume=args.words,
    )

    # --- Chart ---
    if args.chart:
        en_lookup = {}
        if english_results:
            for info, result in english_results:
                en_lookup[info.name] = result.tokens
        display_chart(results, en_lookup)

    # --- Viz ---
    if args.viz:
        viz_names = [v.strip() for v in args.viz.split(",")]
        for viz_name in viz_names:
            matched = [(info, result) for info, result in results if info.name == viz_name]
            if not matched:
                console.print(f"[red]Tokenizer '{viz_name}' not found in results.[/red]")
                continue
            info, result = matched[0]
            pieces = decode_tokens(info, result.token_ids)
            display_viz(text, info, result, pieces)


def _display_batch(
    all_results: list[tuple[dict, list, list | None]],
    as_json: bool = False,
):
    """Display aggregate stats from batch processing."""
    from collections import defaultdict

    totals: dict[str, list[int]] = defaultdict(list)
    en_totals: dict[str, list[int]] = defaultdict(list)

    for item, results, en_results in all_results:
        for info, result in results:
            totals[info.name].append(result.tokens)
        if en_results:
            for info, result in en_results:
                en_totals[info.name].append(result.tokens)

    num_items = len(all_results)
    total_words = sum(count_words(item["text"]) for item, _, _ in all_results)

    if as_json:
        output = {
            "items_processed": num_items,
            "total_words": total_words,
            "tokenizers": {},
        }
        for name, token_counts in sorted(totals.items(), key=lambda x: sum(x[1])):
            entry = {
                "total_tokens": sum(token_counts),
                "avg_tokens_per_item": round(sum(token_counts) / len(token_counts), 1),
                "avg_tokens_per_word": round(sum(token_counts) / total_words, 2) if total_words else 0,
            }
            if name in en_totals:
                en_total = sum(en_totals[name])
                if en_total > 0:
                    entry["ar_en_ratio"] = round(sum(token_counts) / en_total, 2)
            output["tokenizers"][name] = entry
        print(json.dumps(output, ensure_ascii=False, indent=2))
        return

    from rich.table import Table

    table = Table(
        title=f"\n[bold]Batch Results: {num_items} items, {total_words:,} words[/bold]",
        show_header=True,
        header_style="bold cyan",
        border_style="dim",
        padding=(0, 1),
    )

    table.add_column("Tokenizer", style="bold white", min_width=14)
    table.add_column("Total Tokens", justify="right", style="yellow")
    table.add_column("Avg/Item", justify="right", style="dim white")
    table.add_column("Avg Tok/Word", justify="right", style="dim white")

    if en_totals:
        table.add_column("AR/EN Ratio", justify="right")

    sorted_totals = sorted(totals.items(), key=lambda x: sum(x[1]))
    best_total = sum(sorted_totals[0][1]) if sorted_totals else 0

    for name, token_counts in sorted_totals:
        total = sum(token_counts)
        avg_item = total / len(token_counts)
        avg_word = total / total_words if total_words else 0

        row = [
            name,
            f"{total:,}",
            f"{avg_item:.1f}",
            f"{avg_word:.2f}",
        ]

        if en_totals:
            if name in en_totals:
                en_total = sum(en_totals[name])
                if en_total > 0:
                    ratio = total / en_total
                    color = "green" if ratio <= 1.5 else ("yellow" if ratio <= 2.5 else "red")
                    row.append(f"[{color}]{ratio:.2f}x[/{color}]")
                else:
                    row.append("-")
            else:
                row.append("-")

        table.add_row(*row)

    console.print()
    console.print(table)
    console.print()


if __name__ == "__main__":
    main()
