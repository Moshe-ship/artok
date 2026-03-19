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

from artok.core import count_all, count_tokens, count_words, decode_tokens, TOKENIZERS, BENCHMARK_CORPUS, DIALECT_SAMPLES, force_update, get_config_info
from artok.display import (
    display_results,
    display_json,
    display_chart,
    display_recommend,
    display_viz,
    display_switch_from,
    display_compare_langs,
    display_tashkeel,
    display_heatmap,
    display_leaderboard,
    display_benchmark,
    display_dialects,
    enable_recording,
    export_svg,
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
    parser.add_argument(
        "--switch-from",
        type=str,
        default=None,
        metavar="TOKENIZER",
        help="Show savings from switching away from TOKENIZER (e.g., --switch-from claude-sonnet)",
    )
    parser.add_argument(
        "--compare-langs",
        type=str,
        default=None,
        metavar="LANGS",
        help="Compare Arabic against multiple languages. Provide as 'lang:text' pairs separated by | (e.g., --compare-langs 'fr:L\\'IA change le monde|zh:人工智能改变世界')",
    )
    parser.add_argument(
        "--url",
        type=str,
        default=None,
        help="Fetch Arabic text from a URL and analyze it",
    )
    parser.add_argument(
        "--tashkeel",
        action="store_true",
        help="Analyze how diacritics (tashkeel/\u062d\u0631\u0643\u0627\u062a) inflate token counts",
    )
    parser.add_argument(
        "--heatmap",
        type=str,
        default=None,
        nargs="?",
        const="auto",
        metavar="TOKENIZER",
        help="Show token cost heatmap - color each word by token count (optionally specify tokenizer)",
    )
    parser.add_argument(
        "--export",
        type=str,
        default=None,
        metavar="FILE",
        help="Export output to SVG image file for sharing (e.g., --export results.svg)",
    )
    parser.add_argument(
        "--leaderboard",
        action="store_true",
        help="Rank tokenizers by composite score (efficiency + cost + value)",
    )
    parser.add_argument(
        "--watch",
        action="store_true",
        help="Live mode - type Arabic text and see token counts update in real-time",
    )
    parser.add_argument(
        "--benchmark",
        action="store_true",
        help="Run built-in Arabic benchmark and score each tokenizer's Arabic friendliness (0-100)",
    )
    parser.add_argument(
        "--dialects",
        action="store_true",
        help="Compare tokenization efficiency across Arabic dialects",
    )
    parser.add_argument(
        "--update",
        action="store_true",
        help="Force-fetch latest tokenizer pricing from GitHub",
    )

    args = parser.parse_args()

    # --- Update mode ---
    if args.update:
        console.print("[bold cyan]Fetching latest tokenizer config...[/bold cyan]")
        success, msg = force_update()
        if success:
            console.print(f"[green]{msg}[/green]")
        else:
            console.print(f"[red]{msg}[/red]")
        return

    if args.export:
        enable_recording()

    if args.list:
        info = get_config_info()
        console.print("\n[bold]Available tokenizers:[/bold]\n")
        for t in TOKENIZERS:
            cost = f"${t.cost_input:.2f}/1M" if t.cost_input else "N/A"
            console.print(f"  [cyan]{t.name:14s}[/cyan]  {t.display_name:16s}  {t.backend:14s}  {cost}")
        console.print()
        src = info["source"]
        if src == "cached":
            console.print(f"[dim]  Source: remote (cached {info.get('cache_age_hours', '?')}h ago) | Run --update to refresh[/dim]")
        else:
            console.print(f"[dim]  Source: built-in defaults | Run --update to fetch latest pricing[/dim]")
        console.print()
        return

    # --- Benchmark mode (standalone) ---
    if args.benchmark:
        only = None
        if args.tokenizers:
            only = [t.strip() for t in args.tokenizers.split(",")]

        with console.status("[bold cyan]Running Arabic benchmark...", spinner="dots"):
            # Collect per-tokenizer scores
            tokenizer_scores: dict[str, dict[str, float]] = {}
            for category, sample_text in BENCHMARK_CORPUS.items():
                words = count_words(sample_text)
                cat_results = count_all(sample_text, only=only)
                for info, result in cat_results:
                    if info.display_name not in tokenizer_scores:
                        tokenizer_scores[info.display_name] = {}
                    fertility = result.tokens / words if words > 0 else 0
                    score = max(0, 100 - (fertility - 1.3) * 20)
                    tokenizer_scores[info.display_name][category] = score

        benchmark_results = []
        for name, categories in tokenizer_scores.items():
            overall = sum(categories.values()) / len(categories) if categories else 0
            benchmark_results.append({
                "name": name,
                "categories": categories,
                "score": overall,
            })

        display_benchmark(benchmark_results)
        return

    # --- Dialects mode (standalone) ---
    if args.dialects:
        only = None
        if args.tokenizers:
            only = [t.strip() for t in args.tokenizers.split(",")]

        with console.status("[bold cyan]Tokenizing dialects...", spinner="dots"):
            dialect_results = {}
            for dialect, sample_text in DIALECT_SAMPLES.items():
                dialect_results[dialect] = (sample_text, count_all(sample_text, only=only))

        display_dialects(dialect_results)
        return

    # --- Watch (live) mode ---
    if args.watch:
        only_watch = None
        if args.tokenizers:
            only_watch = [t.strip() for t in args.tokenizers.split(",")]
        console.print("\n[bold magenta]artok live mode[/bold magenta] [dim](Ctrl+C to exit)[/dim]\n")
        try:
            while True:
                text = console.input("[bold cyan]Arabic > [/bold cyan]")
                if not text.strip():
                    continue
                with console.status("[bold cyan]Loading tokenizers...", spinner="dots"):
                    results = count_all(text.strip(), only=only_watch)
                display_results(text=text.strip(), results=results)
        except KeyboardInterrupt:
            console.print("\n[dim]Goodbye![/dim]\n")
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

    # --- URL mode ---
    if args.url:
        import urllib.request
        try:
            import re as _re
            with console.status(f"[bold cyan]Fetching {args.url}...", spinner="dots"):
                req = urllib.request.Request(args.url, headers={"User-Agent": "artok/0.1"})
                with urllib.request.urlopen(req, timeout=15) as resp:
                    html = resp.read().decode("utf-8", errors="ignore")
                # Strip HTML tags, extract text
                clean = _re.sub(r"<script[^>]*>.*?</script>", "", html, flags=_re.DOTALL)
                clean = _re.sub(r"<style[^>]*>.*?</style>", "", clean, flags=_re.DOTALL)
                clean = _re.sub(r"<[^>]+>", " ", clean)
                clean = _re.sub(r"\s+", " ", clean).strip()
                # Filter to keep only Arabic segments
                arabic_parts = []
                for word in clean.split():
                    if any("\u0600" <= c <= "\u06FF" for c in word):
                        arabic_parts.append(word)
                if arabic_parts:
                    args.text = arabic_parts[:500]  # Cap at 500 words
                    console.print(f"[dim]Extracted {len(arabic_parts)} Arabic words (using first {min(500, len(arabic_parts))})[/dim]")
                else:
                    console.print("[red]No Arabic text found at this URL.[/red]")
                    sys.exit(1)
        except Exception as e:
            console.print(f"[red]Failed to fetch URL: {e}[/red]")
            sys.exit(1)

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

    # --- Switch-from ---
    if args.switch_from:
        display_switch_from(results, args.switch_from, args.cost or 10)

    # --- Compare languages ---
    if args.compare_langs:
        lang_pairs = {}
        for pair in args.compare_langs.split("|"):
            pair = pair.strip()
            if ":" in pair:
                lang, lang_text = pair.split(":", 1)
                lang_pairs[lang.strip()] = lang_text.strip()
        if lang_pairs:
            with console.status("[bold cyan]Tokenizing languages...", spinner="dots"):
                lang_results = {}
                for lang, lang_text in lang_pairs.items():
                    lang_results[lang] = (lang_text, count_all(lang_text, only=only))
            display_compare_langs(text, results, lang_results)

    # --- Tashkeel (diacritics) analysis ---
    if args.tashkeel:
        import re
        stripped = re.sub(
            "[\u0610-\u061A\u064B-\u065F\u0670\u06D6-\u06DC\u06DF-\u06E4"
            "\u06E7-\u06E8\u06EA-\u06ED\u08D3-\u08FF]",
            "",
            text,
        )
        if stripped != text:
            with console.status("[bold cyan]Tokenizing stripped text...", spinner="dots"):
                results_without = count_all(stripped, only=only)
            display_tashkeel(text, results, results_without)
        else:
            console.print("\n[dim]No diacritics found in text — nothing to compare.[/dim]\n")

    # --- Heatmap ---
    if args.heatmap is not None:
        # Pick the tokenizer
        hm_info = None
        if args.heatmap == "auto":
            hm_info = results[0][0]
        else:
            matched = [(info, result) for info, result in results if info.name == args.heatmap]
            if not matched:
                console.print(f"[red]Tokenizer '{args.heatmap}' not found in results.[/red]")
            else:
                hm_info = matched[0][0]

        if hm_info is not None:
            words = text.split()
            words_tokens = []
            for word in words:
                wr = count_tokens(word, hm_info)
                words_tokens.append((word, wr.tokens if wr and wr.tokens > 0 else 1))
            display_heatmap(text, hm_info, words_tokens)

    # --- Leaderboard ---
    if args.leaderboard:
        display_leaderboard(results)

    # --- Export SVG ---
    if args.export:
        export_svg(args.export)
        print(f"Saved SVG to {args.export}", file=sys.stderr)


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
