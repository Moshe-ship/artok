"""Rich terminal display for artok results."""

from __future__ import annotations

from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.text import Text

from artok.core import TokenizerInfo, TokenizerResult, count_words

console = Console()


def display_results(
    text: str,
    results: list[tuple[TokenizerInfo, TokenizerResult]],
    english_text: str | None = None,
    english_results: list[tuple[TokenizerInfo, TokenizerResult]] | None = None,
    show_tokens: bool = False,
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

    # Show actual tokens if requested
    if show_tokens:
        console.print()
        for info, result in results:
            console.print(f"[bold]{result.name}[/bold] token IDs: {result.token_ids}")

    console.print()
