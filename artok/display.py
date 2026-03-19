"""Rich terminal display for artok results."""

from __future__ import annotations

from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.text import Text

from artok.core import TokenizerInfo, TokenizerResult, count_words

console = Console()


def _display_cost_estimate(
    results: list[tuple[TokenizerInfo, TokenizerResult]],
    english_results: list[tuple[TokenizerInfo, TokenizerResult]] | None,
    en_lookup: dict[str, int],
    volume_m: float,
):
    """Show cost estimate table for a given volume of tokens."""
    # Calculate the token expansion ratio from sample text for each tokenizer
    # Then project costs at volume scale
    best_tokens = min(r.tokens for _, r in results)

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

        # Scale: the sample text ratio tells us how many "real" tokens
        # the Arabic text expands to vs the best tokenizer.
        # For cost estimation, we use the raw per-1M-token pricing
        # applied to the volume the user specified.
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
                # Arabic uses X times more tokens than English
                # So for the same content, English would need volume_m / ratio
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
        # Calculate total extra cost across cheapest option
        cheapest_info, cheapest_result = min(
            ((i, r) for i, r in results if i.cost_input),
            key=lambda x: x[0].cost_input * volume_m,
        )
        en_count = en_lookup.get(cheapest_info.name)
        if en_count and cheapest_result.tokens > 0:
            ratio = cheapest_result.tokens / en_count
            console.print(
                f"\n[dim]Note: \"Extra Cost\" = how much more you pay for Arabic vs "
                f"English for the same semantic content at {volume_m:g}M tokens.[/dim]"
            )

def display_results(
    text: str,
    results: list[tuple[TokenizerInfo, TokenizerResult]],
    english_text: str | None = None,
    english_results: list[tuple[TokenizerInfo, TokenizerResult]] | None = None,
    show_tokens: bool = False,
    cost_volume: float | None = None,
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
    header.append(f"\nWords: {words}", style="dim")
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

    # Show actual tokens if requested
    if show_tokens:
        console.print()
        for info, result in results:
            console.print(f"[bold]{result.name}[/bold] token IDs: {result.token_ids}")

    console.print()
