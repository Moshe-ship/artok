"""Rich terminal display for artok results."""

from __future__ import annotations

import json

from rich.console import Console
from rich.table import Table
from rich.bar import Bar
from rich.text import Text

from artok.core import TokenizerInfo, TokenizerResult, count_words

console = Console()


def enable_recording():
    """Enable recording mode for SVG export."""
    global console
    console = Console(record=True, width=90, force_terminal=True)


def export_svg(path: str):
    """Export recorded output as SVG."""
    svg = console.export_svg(title="artok \u2014 Arabic Token Tax Calculator")
    with open(path, "w") as f:
        f.write(svg)


# ---------------------------------------------------------------------------
# JSON output
# ---------------------------------------------------------------------------

def display_json(
    text: str,
    results: list[tuple[TokenizerInfo, TokenizerResult]],
    english_text: str | None = None,
    english_results: list[tuple[TokenizerInfo, TokenizerResult]] | None = None,
    cost_volume: float | None = None,
    word_volume: float | None = None,
):
    """Output results as JSON."""
    words = count_words(text)
    chars = len(text)
    best_count = min(r.tokens for _, r in results) if results else 0

    en_lookup: dict[str, int] = {}
    if english_results:
        for info, result in english_results:
            en_lookup[info.name] = result.tokens

    results.sort(key=lambda x: x[1].tokens)

    tokenizers = []
    for info, result in results:
        fertility = result.tokens / words if words > 0 else 0
        entry = {
            "name": info.name,
            "display_name": result.name,
            "tokens": result.tokens,
            "tokens_per_word": round(fertility, 2),
            "tax_vs_best": round(result.tokens / best_count, 2) if best_count > 0 else 0,
            "cost_per_1m_input": info.cost_input,
            "cost_per_1m_output": info.cost_output,
        }
        en_count = en_lookup.get(info.name)
        if en_count:
            entry["en_tokens"] = en_count
            entry["ar_en_ratio"] = round(result.tokens / en_count, 2) if en_count > 0 else 0

        # Word volume estimation
        if word_volume and info.cost_input:
            est_tokens_m = word_volume * fertility
            entry["word_estimate"] = {
                "word_volume_millions": word_volume,
                "estimated_tokens_millions": round(est_tokens_m, 2),
                "input_cost": round(est_tokens_m * info.cost_input, 2),
                "output_cost": round(est_tokens_m * (info.cost_output or 0), 2),
                "total": round(est_tokens_m * info.cost_input + est_tokens_m * (info.cost_output or 0), 2),
            }

        # Token volume cost
        if cost_volume and info.cost_input:
            entry["cost_estimate"] = {
                "volume_millions": cost_volume,
                "input_cost": round(cost_volume * info.cost_input, 2),
                "output_cost": round(cost_volume * (info.cost_output or 0), 2),
                "total": round(cost_volume * info.cost_input + cost_volume * (info.cost_output or 0), 2),
            }
            if en_count and result.tokens > 0:
                ratio = result.tokens / en_count
                en_vol = cost_volume / ratio
                en_total = en_vol * info.cost_input + en_vol * (info.cost_output or 0)
                entry["cost_estimate"]["en_equivalent_total"] = round(en_total, 2)
                entry["cost_estimate"]["extra_cost"] = round(entry["cost_estimate"]["total"] - en_total, 2)

        tokenizers.append(entry)

    output = {
        "text": text,
        "words": words,
        "characters": chars,
        "tokenizers": tokenizers,
    }

    if english_text:
        output["english_text"] = english_text

    if results:
        avg_ar = sum(r.tokens for _, r in results) / len(results)
        if en_lookup:
            avg_en = sum(en_lookup.values()) / len(en_lookup)
            if avg_en > 0:
                output["average_ar_en_ratio"] = round(avg_ar / avg_en, 2)

    print(json.dumps(output, ensure_ascii=False, indent=2))


# ---------------------------------------------------------------------------
# Cost estimate sub-table
# ---------------------------------------------------------------------------

def _display_cost_estimate(
    results: list[tuple[TokenizerInfo, TokenizerResult]],
    english_results: list[tuple[TokenizerInfo, TokenizerResult]] | None,
    en_lookup: dict[str, int],
    volume_m: float,
):
    """Show cost estimate table for a given token volume."""
    cost_table = Table(
        title=f"\n[bold]Cost Estimate for {volume_m:g}M tokens of Arabic text[/bold]",
        show_header=True,
        header_style="bold cyan",
        border_style="dim",
        padding=(0, 1),
    )

    cost_table.add_column("Tokenizer", style="bold white", min_width=14)
    cost_table.add_column("Input Cost", justify="right", style="yellow")
    cost_table.add_column("Output Cost", justify="right", style="yellow")
    cost_table.add_column("Total (I+O)", justify="right", style="bold green")

    if english_results and en_lookup:
        cost_table.add_column("EN Equivalent", justify="right", style="blue")
        cost_table.add_column("Extra Cost", justify="right")

    for info, result in results:
        if not info.cost_input:
            continue

        input_cost = volume_m * info.cost_input
        output_cost = volume_m * (info.cost_output or 0)
        total = input_cost + output_cost

        row = [
            result.name,
            f"${input_cost:,.2f}",
            f"${output_cost:,.2f}",
            f"${total:,.2f}",
        ]

        if english_results and en_lookup:
            en_count = en_lookup.get(info.name)
            if en_count and result.tokens > 0:
                ratio = result.tokens / en_count
                en_volume = volume_m / ratio
                en_total = en_volume * info.cost_input + en_volume * (info.cost_output or 0)
                extra = total - en_total
                row.append(f"${en_total:,.2f}")
                if extra > 0:
                    row.append(f"[red]+${extra:,.2f}[/red]")
                else:
                    row.append(f"[green]${extra:,.2f}[/green]")
            else:
                row.extend(["-", "-"])

        cost_table.add_row(*row)

    console.print()
    console.print(cost_table)

    if english_results and en_lookup:
        console.print(
            f"\n[dim]Note: \"Extra Cost\" = how much more you pay for Arabic vs "
            f"English for the same semantic content at {volume_m:g}M tokens.[/dim]"
        )


# ---------------------------------------------------------------------------
# Word volume estimate sub-table
# ---------------------------------------------------------------------------

def _display_word_estimate(
    results: list[tuple[TokenizerInfo, TokenizerResult]],
    en_lookup: dict[str, int],
    word_volume: float,
    words: int,
):
    """Show cost estimate based on word count (accounts for token expansion)."""
    word_table = Table(
        title=f"\n[bold]Cost Estimate for {word_volume:g}M words of Arabic content[/bold]",
        show_header=True,
        header_style="bold cyan",
        border_style="dim",
        padding=(0, 1),
    )

    word_table.add_column("Tokenizer", style="bold white", min_width=14)
    word_table.add_column("Est. Tokens", justify="right", style="yellow")
    word_table.add_column("Input Cost", justify="right", style="yellow")
    word_table.add_column("Output Cost", justify="right", style="yellow")
    word_table.add_column("Total (I+O)", justify="right", style="bold green")

    if en_lookup:
        word_table.add_column("EN Total", justify="right", style="blue")
        word_table.add_column("Extra Cost", justify="right")

    for info, result in results:
        if not info.cost_input:
            continue

        fertility = result.tokens / words if words > 0 else 0
        est_tokens_m = word_volume * fertility
        input_cost = est_tokens_m * info.cost_input
        output_cost = est_tokens_m * (info.cost_output or 0)
        total = input_cost + output_cost

        row = [
            result.name,
            f"{est_tokens_m:.1f}M",
            f"${input_cost:,.2f}",
            f"${output_cost:,.2f}",
            f"${total:,.2f}",
        ]

        if en_lookup:
            en_count = en_lookup.get(info.name)
            if en_count and words > 0:
                en_fertility = en_count / words if words > 0 else 1
                # Assume English has similar word count for same content
                # but each word maps to fewer tokens
                en_est_m = word_volume * en_fertility
                en_total = en_est_m * info.cost_input + en_est_m * (info.cost_output or 0)
                extra = total - en_total
                row.append(f"${en_total:,.2f}")
                if extra > 0:
                    row.append(f"[red]+${extra:,.2f}[/red]")
                else:
                    row.append(f"[green]${extra:,.2f}[/green]")
            else:
                row.extend(["-", "-"])

        word_table.add_row(*row)

    console.print()
    console.print(word_table)
    console.print(
        f"\n[dim]Token estimates based on the sample text's tokens-per-word ratio.[/dim]"
    )


# ---------------------------------------------------------------------------
# Token visualization
# ---------------------------------------------------------------------------

_VIZ_COLORS = [
    "bright_red", "bright_green", "bright_yellow", "bright_blue",
    "bright_magenta", "bright_cyan", "red", "green", "yellow", "blue",
    "magenta", "cyan", "bright_white", "dark_orange", "purple",
]


def display_viz(
    text: str,
    info: TokenizerInfo,
    result: TokenizerResult,
    pieces: list[str],
):
    """Visualize how a tokenizer splits text into tokens with colors."""
    console.print()
    console.print(f"[bold]{result.name}[/bold] tokenization ({result.tokens} tokens):")
    console.print()

    # Color each token piece differently
    viz = Text()
    for i, piece in enumerate(pieces):
        color = _VIZ_COLORS[i % len(_VIZ_COLORS)]
        display_piece = piece if piece.strip() else repr(piece)
        viz.append(f"[{display_piece}]", style=f"bold {color}")

    console.print(f"  {viz}")
    console.print()

    # Also show as a numbered list
    table = Table(
        show_header=True,
        header_style="bold cyan",
        border_style="dim",
        padding=(0, 1),
    )
    table.add_column("#", justify="right", style="dim", width=4)
    table.add_column("Token", style="bold")
    table.add_column("ID", justify="right", style="dim")
    table.add_column("Bytes", justify="right", style="dim")

    for i, (piece, tid) in enumerate(zip(pieces, result.token_ids)):
        color = _VIZ_COLORS[i % len(_VIZ_COLORS)]
        byte_count = len(piece.encode("utf-8"))
        table.add_row(
            str(i + 1),
            f"[{color}]{repr(piece)}[/{color}]",
            str(tid),
            str(byte_count),
        )

    console.print(table)
    console.print()


# ---------------------------------------------------------------------------
# Switch-from savings
# ---------------------------------------------------------------------------

def display_switch_from(
    results: list[tuple[TokenizerInfo, TokenizerResult]],
    from_name: str,
    volume_m: float,
):
    """Show savings from switching away from a specific tokenizer."""
    # Find the source tokenizer
    source = None
    for info, result in results:
        if info.name == from_name:
            source = (info, result)
            break

    if not source:
        console.print(f"[red]Tokenizer '{from_name}' not found.[/red]")
        return

    src_info, src_result = source

    console.print()
    console.print(f"[bold magenta]artok[/bold magenta] [dim]- Switching from[/dim] [bold red]{src_result.name}[/bold red]")
    console.print(f"[dim]At {volume_m:g}M tokens/month[/dim]")
    console.print()

    src_total_rate = (src_info.cost_input or 0) + (src_info.cost_output or 0)
    src_monthly = volume_m * src_total_rate

    table = Table(
        show_header=True,
        header_style="bold cyan",
        border_style="dim",
        padding=(0, 1),
    )

    table.add_column("Switch to", style="bold white", min_width=14)
    table.add_column("Tokens", justify="right", style="dim")
    table.add_column("Monthly Cost", justify="right", style="yellow")
    table.add_column("Savings", justify="right")
    table.add_column("Savings %", justify="right")

    results_sorted = sorted(results, key=lambda x: (x[0].cost_input or 0) + (x[0].cost_output or 0))

    for info, result in results_sorted:
        if info.name == from_name:
            continue

        total_rate = (info.cost_input or 0) + (info.cost_output or 0)
        # Account for token ratio — same content costs different tokens
        if src_result.tokens > 0:
            ratio = result.tokens / src_result.tokens
            adjusted_volume = volume_m * ratio
        else:
            adjusted_volume = volume_m

        monthly = adjusted_volume * total_rate
        savings = src_monthly - monthly
        pct = (savings / src_monthly * 100) if src_monthly > 0 else 0

        if savings > 0:
            sav_str = f"[green]-${savings:,.2f}[/green]"
            pct_str = f"[green]{pct:.0f}%[/green]"
        elif savings < 0:
            sav_str = f"[red]+${abs(savings):,.2f}[/red]"
            pct_str = f"[red]+{abs(pct):.0f}%[/red]"
        else:
            sav_str = "$0.00"
            pct_str = "0%"

        table.add_row(
            result.name,
            str(result.tokens),
            f"${monthly:,.2f}",
            sav_str,
            pct_str,
        )

    console.print(f"  [dim]Current:[/dim] [bold]{src_result.name}[/bold] = [red]${src_monthly:,.2f}/month[/red]")
    console.print()
    console.print(table)
    console.print()


# ---------------------------------------------------------------------------
# Multi-language comparison
# ---------------------------------------------------------------------------

def display_compare_langs(
    arabic_text: str,
    arabic_results: list[tuple[TokenizerInfo, TokenizerResult]],
    lang_results: dict[str, tuple[str, list[tuple[TokenizerInfo, TokenizerResult]]]],
):
    """Compare Arabic token costs against multiple languages."""
    console.print()
    console.print("[bold magenta]artok[/bold magenta] [dim]- Multi-Language Comparison[/dim]")
    console.print()

    # Pick a representative tokenizer set (use all that have results)
    tokenizer_names = []
    for info, _ in arabic_results:
        if info.name not in tokenizer_names:
            tokenizer_names.append(info.name)

    table = Table(
        show_header=True,
        header_style="bold cyan",
        border_style="dim",
        padding=(0, 1),
    )

    table.add_column("Tokenizer", style="bold white", min_width=14)
    table.add_column("Arabic", justify="right", style="yellow")

    lang_order = list(lang_results.keys())
    for lang in lang_order:
        table.add_column(lang.upper(), justify="right", style="blue")
    table.add_column("AR vs Best", justify="right")

    # Build lookups
    ar_lookup = {info.name: result.tokens for info, result in arabic_results}
    lang_lookups = {}
    for lang, (_, lr) in lang_results.items():
        lang_lookups[lang] = {info.name: result.tokens for info, result in lr}

    # Build display name lookup
    display_names = {info.name: result.name for info, result in arabic_results}

    for tname in tokenizer_names:
        ar_count = ar_lookup.get(tname)
        if not ar_count:
            continue

        row = [display_names.get(tname, tname), str(ar_count)]

        best_other = float("inf")
        for lang in lang_order:
            count = lang_lookups.get(lang, {}).get(tname)
            if count:
                row.append(str(count))
                best_other = min(best_other, count)
            else:
                row.append("-")

        if best_other < float("inf") and best_other > 0:
            ratio = ar_count / best_other
            color = "green" if ratio <= 1.5 else ("yellow" if ratio <= 2.5 else "red")
            row.append(f"[{color}]{ratio:.1f}x[/{color}]")
        else:
            row.append("-")

        table.add_row(*row)

    # Print texts
    ar_display = arabic_text if len(arabic_text) <= 40 else arabic_text[:37] + "..."
    console.print(f"  [bold]AR:[/bold] {ar_display}")
    for lang, (text, _) in lang_results.items():
        t_display = text if len(text) <= 40 else text[:37] + "..."
        console.print(f"  [bold]{lang.upper()}:[/bold] {t_display}")

    console.print()
    console.print(table)
    console.print()


# ---------------------------------------------------------------------------
# Tashkeel (diacritics) comparison
# ---------------------------------------------------------------------------

def display_tashkeel(
    text: str,
    results_with: list[tuple[TokenizerInfo, TokenizerResult]],
    results_without: list[tuple[TokenizerInfo, TokenizerResult]],
):
    """Show a comparison table of token counts with/without Arabic diacritics."""
    console.print()
    console.print("[bold magenta]artok[/bold magenta] [dim]- Tashkeel (Diacritics) Analysis[/dim]")
    console.print()

    # Build lookup for without-diacritics results
    without_lookup: dict[str, int] = {}
    for info, result in results_without:
        without_lookup[info.name] = result.tokens

    table = Table(
        show_header=True,
        header_style="bold cyan",
        border_style="dim",
        padding=(0, 1),
    )

    table.add_column("Tokenizer", style="bold white", min_width=14)
    table.add_column("With Tashkeel", justify="right", style="yellow")
    table.add_column("Without", justify="right", style="green")
    table.add_column("Inflation %", justify="right")

    results_with.sort(key=lambda x: x[1].tokens)

    for info, result in results_with:
        without_count = without_lookup.get(info.name)
        if without_count is None:
            continue

        if without_count > 0:
            inflation = ((result.tokens - without_count) / without_count) * 100
        else:
            inflation = 0.0

        if inflation <= 0:
            inf_str = f"[green]{inflation:+.1f}%[/green]"
        elif inflation <= 10:
            inf_str = f"[yellow]+{inflation:.1f}%[/yellow]"
        else:
            inf_str = f"[red]+{inflation:.1f}%[/red]"

        table.add_row(
            result.name,
            str(result.tokens),
            str(without_count),
            inf_str,
        )

    console.print(table)
    console.print()


# ---------------------------------------------------------------------------
# Token cost heatmap
# ---------------------------------------------------------------------------

_HEATMAP_STYLES = {
    1: "green",
    2: "yellow",
    3: "dark_orange",
    4: "red",
    5: "bold red",
}


def display_heatmap(
    text: str,
    info: TokenizerInfo,
    words_tokens: list[tuple[str, int]],
):
    """Show text with each word colored by its token cost."""
    console.print()
    console.print(
        f"[bold magenta]artok[/bold magenta] [dim]- Token Cost Heatmap[/dim] "
        f"([bold]{info.display_name}[/bold])"
    )
    console.print()

    # Build colored text
    colored = Text()
    for i, (word, count) in enumerate(words_tokens):
        if count >= 5:
            style = _HEATMAP_STYLES[5]
        else:
            style = _HEATMAP_STYLES.get(count, "green")
        colored.append(word, style=style)
        if i < len(words_tokens) - 1:
            colored.append(" ")

    console.print(f"  {colored}")
    console.print()

    # Legend
    legend = Text("  Legend: ")
    legend.append("1 tok ", style="green")
    legend.append("2 tok ", style="yellow")
    legend.append("3 tok ", style="dark_orange")
    legend.append("4 tok ", style="red")
    legend.append("5+ tok", style="bold red")
    console.print(legend)
    console.print()


# ---------------------------------------------------------------------------
# Leaderboard (composite score ranking)
# ---------------------------------------------------------------------------

def display_leaderboard(
    results: list[tuple[TokenizerInfo, TokenizerResult]],
):
    """Rank all tokenizers by composite score (efficiency + cost + value)."""
    if not results:
        console.print("[red]No tokenizers available.[/red]")
        return

    # Filter to tokenizers with pricing info
    scored = []
    for info, result in results:
        if info.cost_input is None:
            continue
        total_rate = (info.cost_input or 0) + (info.cost_output or 0)
        scored.append((info, result, total_rate))

    if not scored:
        console.print("[red]No tokenizers with pricing data.[/red]")
        return

    best_tokens = min(r.tokens for _, r, _ in scored)
    cheapest_rate = min(tr for _, _, tr in scored)

    # Calculate scores
    entries = []
    for info, result, total_rate in scored:
        efficiency = (best_tokens / result.tokens) * 50 if result.tokens > 0 else 0
        cost = (cheapest_rate / total_rate) * 30 if total_rate > 0 else 0
        value_raw = efficiency / (total_rate + 0.01)
        entries.append((info, result, total_rate, efficiency, cost, value_raw))

    # Normalize value scores to max 20
    max_value_raw = max(e[5] for e in entries) if entries else 1
    final = []
    for info, result, total_rate, efficiency, cost, value_raw in entries:
        value = (value_raw / max_value_raw) * 20 if max_value_raw > 0 else 0
        total = efficiency + cost + value
        final.append((info, result, total_rate, efficiency, cost, value, total))

    # Sort by total descending
    final.sort(key=lambda x: x[6], reverse=True)

    # Determine verdicts
    best_overall_idx = 0
    best_value_idx = max(range(len(final)), key=lambda i: final[i][5])
    most_efficient_idx = max(range(len(final)), key=lambda i: final[i][3])

    console.print()
    console.print("[bold magenta]artok[/bold magenta] [dim]- Tokenizer Leaderboard[/dim]")
    console.print()

    table = Table(
        show_header=True,
        header_style="bold cyan",
        border_style="dim",
        padding=(0, 1),
    )

    table.add_column("Rank", justify="right", style="bold", width=4)
    table.add_column("Tokenizer", style="bold white", min_width=14)
    table.add_column("Tokens", justify="right", style="yellow")
    table.add_column("$/1M (I+O)", justify="right", style="dim")
    table.add_column("Efficiency", justify="right")
    table.add_column("Cost", justify="right")
    table.add_column("Value", justify="right")
    table.add_column("Total", justify="right")
    table.add_column("Verdict", min_width=14)

    medals = {0: "\U0001f947 ", 1: "\U0001f948 ", 2: "\U0001f949 "}

    for rank, (info, result, total_rate, efficiency, cost, value, total) in enumerate(final):
        # Medal prefix for top 3
        medal = medals.get(rank, "")
        name_str = f"{medal}{result.name}"

        # Color total score
        if total >= 70:
            total_str = f"[green]{total:.1f}[/green]"
        elif total >= 40:
            total_str = f"[yellow]{total:.1f}[/yellow]"
        else:
            total_str = f"[red]{total:.1f}[/red]"

        # Verdict
        verdict = ""
        if rank == best_overall_idx:
            verdict = "[bold green]Best overall[/bold green]"
        elif rank == best_value_idx:
            verdict = "[green]Best value[/green]"
        elif rank == most_efficient_idx:
            verdict = "[cyan]Most efficient[/cyan]"

        table.add_row(
            str(rank + 1),
            name_str,
            str(result.tokens),
            f"${total_rate:.2f}",
            f"{efficiency:.1f}",
            f"{cost:.1f}",
            f"{value:.1f}",
            total_str,
            verdict,
        )

    console.print(table)
    console.print()
    console.print("[dim]  Score = Efficiency (max 50) + Cost (max 30) + Value (max 20)[/dim]")
    console.print()


# ---------------------------------------------------------------------------
# Benchmark (Arabic Friendliness Score)
# ---------------------------------------------------------------------------

def display_benchmark(benchmark_results: list[dict]):
    """Display Arabic friendliness benchmark scores for each tokenizer."""
    console.print()
    console.print("[bold magenta]artok[/bold magenta] [dim]- Arabic Friendliness Benchmark[/dim]")
    console.print()

    # Short column names for categories
    col_map = {
        "News (MSA)": "News",
        "Poetry": "Poetry",
        "Quran": "Quran",
        "Technical": "Tech",
        "Conversational": "Conv",
        "Dialect (Egyptian)": "Egy",
        "Dialect (Gulf)": "Gulf",
        "Social Media": "Social",
    }

    table = Table(
        show_header=True,
        header_style="bold cyan",
        border_style="dim",
        padding=(0, 1),
    )

    table.add_column("Tokenizer", style="bold white", min_width=14)
    for full_name, short in col_map.items():
        table.add_column(short, justify="right", style="dim white")
    table.add_column("SCORE", justify="right", style="bold")

    # Sort by overall score (highest first)
    benchmark_results.sort(key=lambda x: x["score"], reverse=True)

    for entry in benchmark_results:
        row = [entry["name"]]
        for cat in col_map:
            cat_score = entry["categories"].get(cat, 0)
            row.append(f"{cat_score:.0f}")

        score = entry["score"]
        if score >= 70:
            score_str = f"[green]{score:.1f}[/green]"
        elif score >= 40:
            score_str = f"[yellow]{score:.1f}[/yellow]"
        else:
            score_str = f"[red]{score:.1f}[/red]"
        row.append(score_str)

        table.add_row(*row)

    # Winner line
    if benchmark_results:
        console.print(table)
        console.print(
            f"\n[bold]Winner:[/bold] [green]{benchmark_results[0]['name']}[/green] "
            f"with a score of [bold green]{benchmark_results[0]['score']:.1f}/100[/bold green]"
        )

    console.print()


# ---------------------------------------------------------------------------
# Dialect comparison
# ---------------------------------------------------------------------------

def display_dialects(dialect_results: dict[str, tuple[str, list[tuple[TokenizerInfo, TokenizerResult]]]]):
    """Display dialect tokenization comparison."""
    console.print()
    console.print("[bold magenta]artok[/bold magenta] [dim]- Arabic Dialect Comparison[/dim]")
    console.print()

    # Show sample texts
    for dialect, (text, _) in dialect_results.items():
        console.print(f"  [bold]{dialect}:[/bold] {text}")
    console.print()

    dialect_names = list(dialect_results.keys())

    table = Table(
        show_header=True,
        header_style="bold cyan",
        border_style="dim",
        padding=(0, 1),
    )

    table.add_column("Tokenizer", style="bold white", min_width=14)
    for dialect in dialect_names:
        table.add_column(dialect, justify="right", style="dim white")
    table.add_column("Best dialect", justify="right")

    # Build lookup: tokenizer_name -> {dialect -> tokens}
    tok_lookup: dict[str, dict[str, int]] = {}
    tok_display: dict[str, str] = {}
    for dialect, (_, results) in dialect_results.items():
        for info, result in results:
            if info.name not in tok_lookup:
                tok_lookup[info.name] = {}
                tok_display[info.name] = result.name
            tok_lookup[info.name][dialect] = result.tokens

    for tok_name in tok_lookup:
        row = [tok_display[tok_name]]
        counts = tok_lookup[tok_name]

        best_dialect = None
        best_count = float("inf")
        for dialect in dialect_names:
            count = counts.get(dialect)
            if count is not None:
                row.append(str(count))
                if count < best_count:
                    best_count = count
                    best_dialect = dialect
            else:
                row.append("-")

        if best_dialect:
            row.append(f"[green]{best_dialect}[/green]")
        else:
            row.append("-")

        table.add_row(*row)

    console.print(table)
    console.print()


# ---------------------------------------------------------------------------
# Bar chart
# ---------------------------------------------------------------------------

def display_chart(
    results: list[tuple[TokenizerInfo, TokenizerResult]],
    en_lookup: dict[str, int] | None = None,
):
    """Show a visual bar chart of token counts."""
    if not results:
        return

    results.sort(key=lambda x: x[1].tokens)
    max_tokens = max(r.tokens for _, r in results)

    console.print()
    console.print("[bold]Token Count Comparison[/bold]")
    console.print()

    bar_width = min(50, console.width - 30)

    for info, result in results:
        name = f"{result.name:14s}"
        count = result.tokens
        bar_len = int((count / max_tokens) * bar_width) if max_tokens > 0 else 0

        # Color based on position
        if count == min(r.tokens for _, r in results):
            color = "green"
        elif count == max_tokens:
            color = "red"
        else:
            color = "yellow"

        bar = f"[{color}]{'█' * bar_len}[/{color}]"
        en_str = ""
        if en_lookup:
            en_count = en_lookup.get(info.name)
            if en_count:
                en_bar_len = int((en_count / max_tokens) * bar_width) if max_tokens > 0 else 0
                en_str = f"  [blue]{'░' * en_bar_len}[/blue] [dim]{en_count} EN[/dim]"

        console.print(f"  {name} {bar} {count}")
        if en_str:
            console.print(f"  {'':14s}{en_str}")

    console.print()
    console.print("[dim]  █ = Arabic tokens    ░ = English tokens[/dim]")
    console.print()


# ---------------------------------------------------------------------------
# Recommend
# ---------------------------------------------------------------------------

def display_recommend(
    text: str,
    results: list[tuple[TokenizerInfo, TokenizerResult]],
    english_results: list[tuple[TokenizerInfo, TokenizerResult]] | None = None,
    budget: float = 100.0,
    word_volume: float | None = None,
):
    """Recommend the best tokenizer for a given budget."""
    if not results:
        console.print("[red]No tokenizers available.[/red]")
        return

    words = count_words(text)
    console.print()
    console.print(f"[bold magenta]artok[/bold magenta] [dim]- Budget Recommendation[/dim]")
    console.print(f"\n[bold]Monthly budget:[/bold] ${budget:,.2f}")

    if word_volume:
        console.print(f"[bold]Content volume:[/bold] {word_volume:g}M words/month")
    console.print()

    rec_table = Table(
        show_header=True,
        header_style="bold cyan",
        border_style="dim",
        padding=(0, 1),
    )

    rec_table.add_column("Tokenizer", style="bold white", min_width=14)
    rec_table.add_column("$/1M tok", justify="right", style="dim")
    rec_table.add_column("Tok/Word", justify="right", style="dim white")

    if word_volume:
        rec_table.add_column("Monthly Cost", justify="right", style="yellow")
        rec_table.add_column("Fits Budget?", justify="center")
    else:
        rec_table.add_column("Tokens/month", justify="right", style="yellow")
        rec_table.add_column("Words/month", justify="right", style="dim")

    rec_table.add_column("Verdict", min_width=12)

    best_pick = None

    # Sort by cost-effectiveness: most words per dollar
    def _sort_key(item):
        info, result = item
        if not info.cost_input:
            return float('inf')
        fertility = result.tokens / words if words > 0 else 1
        total_per_m = info.cost_input + (info.cost_output or 0)
        if word_volume:
            # Sort by monthly cost (lowest first that fits budget)
            return fertility * total_per_m
        else:
            # Sort by words per dollar (highest first = lowest cost per word)
            return fertility * total_per_m

    results.sort(key=_sort_key)

    for info, result in results:
        if not info.cost_input:
            continue

        fertility = result.tokens / words if words > 0 else 1
        total_per_m = info.cost_input + (info.cost_output or 0)

        if word_volume:
            # Calculate monthly cost for given word volume
            est_tokens_m = word_volume * fertility
            monthly_cost = est_tokens_m * total_per_m
            fits = monthly_cost <= budget

            if fits and best_pick is None:
                best_pick = info.display_name

            row = [
                result.name,
                f"${info.cost_input:.2f}",
                f"{fertility:.2f}",
                f"${monthly_cost:,.2f}",
                "[green]YES[/green]" if fits else "[red]NO[/red]",
            ]

            if fits and result.name == best_pick:
                row.append("[bold green]BEST PICK[/bold green]")
            elif fits:
                row.append("[green]Good option[/green]")
            else:
                row.append(f"[red]Need ${monthly_cost:,.0f}[/red]")
        else:
            # Calculate how many tokens you can afford
            tokens_per_month_m = budget / total_per_m if total_per_m > 0 else 0
            words_per_month_m = tokens_per_month_m / fertility if fertility > 0 else 0

            if best_pick is None:
                best_pick = info.display_name

            row = [
                result.name,
                f"${info.cost_input:.2f}",
                f"{fertility:.2f}",
                f"{tokens_per_month_m:.1f}M",
                f"{words_per_month_m:.1f}M",
            ]

            # The one that gives most words per dollar is best
            # But we sort by token count, so cheapest + fewest tokens wins
            if result.name == best_pick:
                row.append("[bold green]BEST VALUE[/bold green]")
            else:
                row.append("")

        rec_table.add_row(*row)

    console.print(rec_table)

    if best_pick:
        console.print(f"\n[bold]Recommendation:[/bold] [green]{best_pick}[/green]")
        if word_volume:
            console.print(f"[dim]Best option that fits your ${budget:,.0f}/month budget for {word_volume:g}M words.[/dim]")
        else:
            console.print(f"[dim]Gives you the most Arabic words per dollar at ${budget:,.0f}/month.[/dim]")

    console.print()


# ---------------------------------------------------------------------------
# Main results display
# ---------------------------------------------------------------------------

def display_results(
    text: str,
    results: list[tuple[TokenizerInfo, TokenizerResult]],
    english_text: str | None = None,
    english_results: list[tuple[TokenizerInfo, TokenizerResult]] | None = None,
    show_tokens: bool = False,
    cost_volume: float | None = None,
    word_volume: float | None = None,
):
    """Display token comparison table."""
    if not results:
        console.print("[red]No tokenizers available. Install tiktoken or transformers.[/red]")
        return

    words = count_words(text)
    best_count = min(r.tokens for _, r in results)

    # Build main table
    table = Table(
        title="",
        show_header=True,
        header_style="bold cyan",
        border_style="dim",
        padding=(0, 1),
    )

    table.add_column("Tokenizer", style="bold white", min_width=14)
    table.add_column("Tokens", justify="right", style="yellow")
    table.add_column("Tok/Word", justify="right", style="dim white")
    table.add_column("Tax", justify="right")
    table.add_column("Cost/1M in", justify="right", style="dim")

    if english_results:
        table.add_column("EN Tokens", justify="right", style="blue")
        table.add_column("AR/EN", justify="right")

    # Sort by token count
    results.sort(key=lambda x: x[1].tokens)

    # Build english lookup
    en_lookup: dict[str, int] = {}
    if english_results:
        for info, result in english_results:
            en_lookup[info.name] = result.tokens

    for info, result in results:
        tax_ratio = result.tokens / best_count if best_count > 0 else 0
        fertility = result.tokens / words if words > 0 else 0

        # Color the tax ratio
        if tax_ratio <= 1.0:
            tax_str = "[green]1.0x (best)[/green]"
        elif tax_ratio <= 1.5:
            tax_str = f"[yellow]{tax_ratio:.2f}x[/yellow]"
        else:
            tax_str = f"[red]{tax_ratio:.2f}x[/red]"

        cost_str = f"${info.cost_input:.2f}" if info.cost_input else "-"

        row = [
            result.name,
            str(result.tokens),
            f"{fertility:.2f}",
            tax_str,
            cost_str,
        ]

        if english_results:
            en_count = en_lookup.get(info.name)
            if en_count:
                ar_en_ratio = result.tokens / en_count if en_count > 0 else 0
                if ar_en_ratio <= 1.2:
                    ratio_str = f"[green]{ar_en_ratio:.2f}x[/green]"
                elif ar_en_ratio <= 2.0:
                    ratio_str = f"[yellow]{ar_en_ratio:.2f}x[/yellow]"
                else:
                    ratio_str = f"[red]{ar_en_ratio:.2f}x[/red]"
                row.extend([str(en_count), ratio_str])
            else:
                row.extend(["-", "-"])

        table.add_row(*row)

    # Header info
    display_text = text if len(text) <= 60 else text[:57] + "..."
    header = Text()
    header.append("artok", style="bold magenta")
    header.append(" - Arabic Token Tax Calculator\n\n", style="dim")
    header.append("Input: ", style="bold")
    header.append(f'"{display_text}"', style="italic")
    header.append(f"\nWords: {words}  |  Chars: {len(text)}", style="dim")
    if english_text:
        en_display = english_text if len(english_text) <= 60 else english_text[:57] + "..."
        header.append(f'\nEnglish: "{en_display}"', style="dim blue")

    console.print()
    console.print(header)
    console.print()
    console.print(table)

    # Summary
    worst = max(r.tokens for _, r in results)
    if english_results and en_lookup:
        avg_ar = sum(r.tokens for _, r in results) / len(results)
        avg_en = sum(en_lookup.values()) / len(en_lookup)
        if avg_en > 0:
            overall_tax = avg_ar / avg_en
            console.print(
                f"\n[bold]Arabic tax:[/bold] on average [red]{overall_tax:.1f}x[/red] "
                f"more tokens than English for the same meaning"
            )

    if best_count != worst:
        savings = ((worst - best_count) / worst) * 100
        best_name = next(r.name for _, r in results if r.tokens == best_count)
        worst_name = next(r.name for _, r in results if r.tokens == worst)
        console.print(
            f"[bold]Best tokenizer:[/bold] [green]{best_name}[/green] "
            f"({savings:.0f}% fewer tokens than {worst_name})"
        )

    # Cost estimate mode
    if cost_volume is not None and cost_volume > 0:
        _display_cost_estimate(results, english_results, en_lookup, cost_volume)

    # Word volume estimate mode
    if word_volume is not None and word_volume > 0:
        _display_word_estimate(results, en_lookup, word_volume, words)

    # Show actual tokens if requested
    if show_tokens:
        console.print()
        for info, result in results:
            console.print(f"[bold]{result.name}[/bold] token IDs: {result.token_ids}")

    console.print()
