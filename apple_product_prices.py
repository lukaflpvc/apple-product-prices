#!/usr/bin/env -S uv run
# /// script
# requires-python = ">=3.11"
# dependencies = [
#   "requests",
#   "rich",
# ]
# ///
"""
Fetches Apple product pricing from Apple Store regional storefronts.
Parses the embedded "prices" JSON object from the shop page HTML.

Usage: uv run apple_store_prices.py
"""

import re
import json
import argparse
import sys
import requests
from concurrent.futures import ThreadPoolExecutor, as_completed

from rich.console import Console
from rich.table import Table
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, TaskProgressColumn
from rich import box

console = Console()
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

# Mac products: shop path -> display name
PRODUCTS = {
    "buy-mac/macbook-neo": "MacBook Neo",
    "buy-mac/macbook-air": "MacBook Air",
    "buy-mac/macbook-pro": "MacBook Pro",
    "buy-mac/mac-mini": "Mac Mini",
    "buy-mac/mac-studio": "Mac Studio",   
}

# Apple Store regional storefronts: code -> (display name, currency)
REGIONS = {
    # ── Africa, Middle East & India ───────────────────────────────────────
    "ae": ("United Arab Emirates", "AED"),
    "in": ("India", "INR"),
    "sa": ("Saudi Arabia", "SAR"),

    # ── Asia Pacific ──────────────────────────────────────────────────────
    "au": ("Australia", "AUD"),
    "au-edu": ("Australia (Education)", "AUD"),
    "au_edu_5000447": ("Australia (Education Union)", "AUD"),
    "hk": ("Hong Kong", "HKD"),
    "jp": ("Japan", "JPY"),
    "kr": ("South Korea", "KRW"),
    "my": ("Malaysia", "MYR"),
    "nz": ("New Zealand", "NZD"),
    "ph": ("Philippines", "PHP"),
    "sg": ("Singapore", "SGD"),
    "th": ("Thailand", "THB"),
    "tw": ("Taiwan", "TWD"),
    "vn": ("Vietnam", "VND"),

    # ── Europe ────────────────────────────────────────────────────────────
    "at": ("Austria", "EUR"),
    "be-fr": ("Belgium (FR)", "EUR"),
    "be-nl": ("Belgium (NL)", "EUR"),
    "ch-de": ("Switzerland (DE)", "CHF"),
    "ch-fr": ("Switzerland (FR)", "CHF"),
    "cz": ("Czech Republic", "CZK"),
    "de": ("Germany", "EUR"),
    "dk": ("Denmark", "DKK"),
    "es": ("Spain", "EUR"),
    "fi": ("Finland", "EUR"),
    "fr": ("France", "EUR"),
    "hu": ("Hungary", "HUF"),
    "ie": ("Ireland", "EUR"),
    "it": ("Italy", "EUR"),
    "lu": ("Luxembourg", "EUR"),
    "nl": ("Netherlands", "EUR"),
    "no": ("Norway", "NOK"),
    "pl": ("Poland", "PLN"),
    "pt": ("Portugal", "EUR"),
    "se": ("Sweden", "SEK"),
    "tr": ("Turkey", "TRY"),
    "uk": ("United Kingdom", "GBP"),

    # ── Latin America & Caribbean ─────────────────────────────────────────
    "br": ("Brazil", "BRL"),
    "cl": ("Chile", "CLP"),
    "mx": ("Mexico", "MXN"),

    # ── United States & Canada ────────────────────────────────────────────
    "ca": ("Canada", "CAD"),
    "ca-edu": ("Canada (Education)", "CAD"),
    "us": ("United States", "USD"),
    "us-edu": ("United States (Education)", "USD"),
}

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
                  "Chrome/124.0.0.0 Safari/537.36",
    "Accept-Language": "en-US,en;q=0.9",
}

# Estimated tourist tax/refund model by base region code.
# tax_excluded_rate: tax added at checkout to listed price.
# tax_included_rate: tax already included in listed price.
# refund_share_of_tax: share of included tax typically recovered by tourists.
TOURIST_TAX_RULES = {
    "us": {"tax_excluded_rate": 0.085},
    "ca": {"tax_excluded_rate": 0.13},
    "au": {"tax_included_rate": 0.10, "refund_share_of_tax": 1.00},
    "ae": {"tax_included_rate": 0.05, "refund_share_of_tax": 0.85},
    "jp": {"tax_included_rate": 0.10, "refund_share_of_tax": 1.00},
    "kr": {"tax_included_rate": 0.10, "refund_share_of_tax": 0.90},
    "sg": {"tax_included_rate": 0.09, "refund_share_of_tax": 0.75},
    "th": {"tax_included_rate": 0.07, "refund_share_of_tax": 0.80},
    "tw": {"tax_included_rate": 0.05, "refund_share_of_tax": 0.80},
    "ch": {"tax_included_rate": 0.081, "refund_share_of_tax": 0.70},
    "uk": {"tax_included_rate": 0.20, "refund_share_of_tax": 0.00},
    "no": {"tax_included_rate": 0.25, "refund_share_of_tax": 0.00},
    "at": {"tax_included_rate": 0.20, "refund_share_of_tax": 0.75},
    "be": {"tax_included_rate": 0.21, "refund_share_of_tax": 0.75},
    "cz": {"tax_included_rate": 0.21, "refund_share_of_tax": 0.75},
    "de": {"tax_included_rate": 0.19, "refund_share_of_tax": 0.75},
    "dk": {"tax_included_rate": 0.25, "refund_share_of_tax": 0.75},
    "es": {"tax_included_rate": 0.21, "refund_share_of_tax": 0.75},
    "fi": {"tax_included_rate": 0.24, "refund_share_of_tax": 0.75},
    "fr": {"tax_included_rate": 0.20, "refund_share_of_tax": 0.75},
    "hu": {"tax_included_rate": 0.27, "refund_share_of_tax": 0.75},
    "ie": {"tax_included_rate": 0.23, "refund_share_of_tax": 0.75},
    "it": {"tax_included_rate": 0.22, "refund_share_of_tax": 0.75},
    "lu": {"tax_included_rate": 0.17, "refund_share_of_tax": 0.75},
    "nl": {"tax_included_rate": 0.21, "refund_share_of_tax": 0.75},
    "pl": {"tax_included_rate": 0.23, "refund_share_of_tax": 0.75},
    "pt": {"tax_included_rate": 0.23, "refund_share_of_tax": 0.75},
    "se": {"tax_included_rate": 0.25, "refund_share_of_tax": 0.75},
}


def extract_prices(html: str) -> dict | None:
    """Extract the 'prices' object embedded in Apple's shop page HTML."""
    match = re.search(r'"prices"\s*:\s*(\{)', html)
    if not match:
        return None

    start = match.start(1)
    depth = 0
    for i, ch in enumerate(html[start:], start):
        if ch == '{':
            depth += 1
        elif ch == '}':
            depth -= 1
            if depth == 0:
                try:
                    return json.loads(html[start:i + 1])
                except json.JSONDecodeError:
                    return None
    return None


def fetch_prices(region_code: str, region_name: str, currency: str, product_path: str, product_name: str):
    url = f"https://www.apple.com/{region_code}/shop/{product_path}"
    try:
        resp = requests.get(url, headers=HEADERS, timeout=15)
        resp.raise_for_status()
        prices = extract_prices(resp.text)

        if prices is None:
            return region_code, region_name, currency, product_name, {}, "No 'prices' block found in page"

        return region_code, region_name, currency, product_name, prices, None

    except requests.exceptions.RequestException as e:
        return region_code, region_name, currency, product_name, {}, str(e)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Fetch Apple Store regional pricing with optional product filtering and currency conversion."
    )
    parser.add_argument(
        "-p",
        "--product",
        action="append",
        default=[],
        help="Filter products by name/path substring (repeatable). Example: --product air --product mini",
    )
    parser.add_argument(
        "-c",
        "--currency",
        help="Convert all numeric prices to this target currency code (for example: USD, AUD, EUR).",
    )
    parser.add_argument(
        "--details",
        action="store_true",
        help="Show full SKU-level breakdown instead of the compact summary table.",
    )
    parser.add_argument(
        "--tourist",
        action="store_true",
        help="Estimate tourist net pricing with local tax rules and possible tax refunds.",
    )
    return parser.parse_args()


def filter_products(queries: list[str]) -> dict[str, str]:
    if not queries:
        return PRODUCTS

    normalized_queries = [q.strip().lower() for q in queries if q.strip()]
    if not normalized_queries:
        return PRODUCTS

    return {
        path: name
        for path, name in PRODUCTS.items()
        if all(query in f"{path} {name}".lower() for query in normalized_queries)
    }


def extract_price_display_and_numeric(info) -> tuple[str, float | None]:
    def parse_numeric(raw_price) -> float | None:
        if isinstance(raw_price, (int, float)):
            return float(raw_price)
        if not isinstance(raw_price, str):
            return None
        match = re.search(r"-?\d+(?:\.\d+)?", raw_price.replace(",", ""))
        return float(match.group(0)) if match else None

    candidates = []
    if isinstance(info, dict):
        candidates.extend(
            [
                info.get("currentPrice"),
                info.get("price"),
                info.get("fullPrice"),
                info.get("amount"),
                info,
            ]
        )
    else:
        candidates.append(info)

    for candidate in candidates:
        if isinstance(candidate, dict):
            display = candidate.get("amount") or candidate.get("raw_amount")
            if display is None:
                continue
            numeric = parse_numeric(candidate.get("raw_amount")) or parse_numeric(display)
            return str(display), numeric
        if candidate is not None:
            return str(candidate), parse_numeric(candidate)

    return str(info), None


def convert_amount(amount: float, source_currency: str, target_currency: str, usd_rates: dict) -> float | None:
    source = source_currency.lower()
    target = target_currency.lower()
    if source not in usd_rates or target not in usd_rates:
        return None
    # If 1 USD = X source and 1 USD = Y target, then source -> target is amount / X * Y.
    return (amount / usd_rates[source]) * usd_rates[target]


def get_region_tax_rule(region_code: str) -> dict | None:
    return TOURIST_TAX_RULES.get(re.split(r"[-_]", region_code, maxsplit=1)[0].lower())


def estimate_default_local_price(local_amount: float, region_code: str) -> float:
    rule = get_region_tax_rule(region_code)
    if not rule:
        return local_amount

    tax_excluded_rate = rule.get("tax_excluded_rate", 0.0)
    if tax_excluded_rate > 0:
        return local_amount * (1 + tax_excluded_rate)
    return local_amount


def estimate_tourist_local_price(default_local_amount: float, region_code: str) -> float:
    rule = get_region_tax_rule(region_code)
    if not rule:
        return default_local_amount

    gross_amount = default_local_amount

    tax_included_rate = rule.get("tax_included_rate", 0.0)
    refund_share_of_tax = rule.get("refund_share_of_tax", 0.0)
    if tax_included_rate > 0 and refund_share_of_tax > 0:
        tax_component = gross_amount * (tax_included_rate / (1 + tax_included_rate))
        gross_amount -= tax_component * refund_share_of_tax

    return gross_amount


def main():
    args = parse_args()
    selected_products = filter_products(args.product)
    if not selected_products:
        console.print("[bold red]No products matched your --product filter.[/bold red]")
        console.print(f"[dim]Available products:[/dim] {', '.join(PRODUCTS.values())}")
        return

    target_currency = args.currency.upper() if args.currency else None
    usd_rates = None
    if target_currency:
        try:
            response = requests.get(
                "https://latest.currency-api.pages.dev/v1/currencies/usd.json",
                timeout=15,
            )
            response.raise_for_status()
            usd_rates = response.json()["usd"]
            if target_currency.lower() not in usd_rates:
                console.print(f"[bold red]Unknown target currency:[/bold red] {target_currency}")
                return
        except requests.exceptions.RequestException as exc:
            console.print(f"[bold red]Failed to fetch exchange rates:[/bold red] {exc}")
            return

    total_tasks = len(REGIONS) * len(selected_products)

    results = []
    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        TaskProgressColumn(),
        console=console,
    ) as progress:
        task = progress.add_task("[cyan]Fetching Apple Store prices by region...", total=total_tasks)

        with ThreadPoolExecutor(max_workers=10) as executor:
            futures = {
                executor.submit(fetch_prices, code, name, curr, path, product_name): (code, path)
                for code, (name, curr) in REGIONS.items()
                for path, product_name in selected_products.items()
            }
            for future in as_completed(futures):
                results.append(future.result())
                progress.advance(task)

    summary_rows = []
    errors = []
    for region_code, region_name, currency, product_name, prices, error in results:
        if error:
            errors.append((region_name, product_name, error))
            continue
        if not prices:
            continue

        fallback_display = "-"
        best_candidate = None
        for info in prices.values():
            price_display, numeric_price = extract_price_display_and_numeric(info)
            if numeric_price is None:
                if fallback_display == "-":
                    fallback_display = str(price_display)
                continue

            default_local_value = estimate_default_local_price(numeric_price, region_code)
            tourist_local_value = (
                estimate_tourist_local_price(default_local_value, region_code)
                if args.tourist
                else None
            )
            converted_value = None
            if target_currency and usd_rates is not None:
                converted_value = convert_amount(default_local_value, currency, target_currency, usd_rates)
                if converted_value is None:
                    continue

            tourist_converted_value = None
            if args.tourist and target_currency and usd_rates is not None and tourist_local_value is not None:
                tourist_converted_value = convert_amount(tourist_local_value, currency, target_currency, usd_rates)
                if tourist_converted_value is None:
                    continue

            if args.tourist:
                comparison_value = (
                    tourist_converted_value
                    if tourist_converted_value is not None
                    else tourist_local_value
                )
            else:
                comparison_value = converted_value if converted_value is not None else numeric_price
            candidate = (
                comparison_value,
                str(price_display),
                default_local_value,
                converted_value,
                tourist_local_value,
                tourist_converted_value,
            )
            if best_candidate is None or candidate[0] < best_candidate[0]:
                best_candidate = candidate

        if best_candidate is None:
            cheapest_display = fallback_display
            cheapest_local_value = None
            cheapest_converted_value = None
            cheapest_tourist_local_value = None
            cheapest_tourist_converted_value = None
            cheapest_sort_value = None
        else:
            (
                cheapest_sort_value,
                cheapest_display,
                cheapest_local_value,
                cheapest_converted_value,
                cheapest_tourist_local_value,
                cheapest_tourist_converted_value,
            ) = best_candidate

        summary_rows.append(
            {
                "region_code": region_code,
                "region_name": region_name,
                "currency": currency,
                "product_name": product_name,
                "local_display": cheapest_display,
                "local_numeric": cheapest_local_value,
                "converted_numeric": cheapest_converted_value,
                "tourist_local_numeric": cheapest_tourist_local_value,
                "tourist_converted_numeric": cheapest_tourist_converted_value,
                "sort_numeric": cheapest_sort_value,
            }
        )

    if target_currency:
        region_cheapest_converted: dict[str, float] = {}
        for row in summary_rows:
            converted = row["sort_numeric"] if args.tourist else row["converted_numeric"]
            if converted is None:
                continue
            region_code = row["region_code"]
            current_cheapest = region_cheapest_converted.get(region_code)
            if current_cheapest is None or converted < current_cheapest:
                region_cheapest_converted[region_code] = converted

        summary_rows.sort(
            key=lambda row: (
                region_cheapest_converted.get(row["region_code"], float("inf")),
                row["region_name"],
                row["product_name"],
            )
        )
    else:
        summary_rows.sort(key=lambda row: (row["region_name"], row["product_name"]))

    if args.details:
        region_order: dict[str, int] = {}
        for index, row in enumerate(summary_rows):
            region_order.setdefault(row["region_code"], index)

        sorted_results = sorted(
            results,
            key=lambda item: (
                region_order.get(item[0], float("inf")),
                item[1],
                item[3],
            ),
        )

        current_region = None
        for region_code, region_name, currency, product_name, prices, error in sorted_results:
            if region_name != current_region:
                console.print()
                console.rule(
                    f"[bold blue]{region_name} [dim]({region_code.upper()})[/dim] — [green]{currency}[/green]",
                    style="blue",
                )
                current_region = region_name

            console.print(f"\n  [bold]{product_name}[/bold]")

            if error:
                console.print(f"  [bold red]ERROR:[/bold red] [red]{error}[/red]")
                continue

            if not prices:
                console.print("  [yellow]No pricing data found.[/yellow]")
                continue

            detail_table = Table(
                box=box.SIMPLE,
                show_header=True,
                header_style="bold magenta",
                padding=(0, 2),
            )
            detail_table.add_column("SKU / Name", style="dim", no_wrap=True)
            detail_table.add_column(f"Price ({currency})", justify="right", style="green", no_wrap=True)
            if target_currency:
                detail_table.add_column(f"In {target_currency}", justify="right", style="cyan", no_wrap=True)
            if args.tourist:
                tourist_col = f"Tourist {target_currency}" if target_currency else "Tourist Est."
                detail_table.add_column(tourist_col, justify="right", style="magenta", no_wrap=True)

            for sku, info in prices.items():
                if isinstance(info, dict):
                    name = info.get("name") or info.get("productName") or sku
                else:
                    name = sku
                price, numeric_price = extract_price_display_and_numeric(info)

                row = [str(name), str(price)]
                if target_currency:
                    converted_display = "-"
                    if numeric_price is not None and usd_rates is not None:
                        default_local = estimate_default_local_price(numeric_price, region_code)
                        converted = convert_amount(default_local, currency, target_currency, usd_rates)
                        if converted is not None:
                            converted_display = f"{converted:,.2f}"
                    row.append(converted_display)
                if args.tourist:
                    tourist_display = "-"
                    if numeric_price is not None:
                        default_local = estimate_default_local_price(numeric_price, region_code)
                        tourist_local = estimate_tourist_local_price(default_local, region_code)
                        if target_currency and usd_rates is not None:
                            tourist_converted = convert_amount(tourist_local, currency, target_currency, usd_rates)
                            if tourist_converted is not None:
                                tourist_display = f"{tourist_converted:,.2f}"
                        else:
                            tourist_display = f"{tourist_local:,.2f}"
                    row.append(tourist_display)
                detail_table.add_row(*row)

            console.print(detail_table)

        console.print("\n[bold green]✓ Done.[/bold green]")
        return

    table = Table(box=box.SIMPLE, show_header=True, header_style="bold magenta", padding=(0, 2))
    table.add_column("Country", style="bold blue", no_wrap=True, overflow="ellipsis")
    if len(selected_products) > 1:
        table.add_column("Product", style="dim", no_wrap=True, overflow="ellipsis")
    table.add_column("Price", justify="right", style="green", no_wrap=True, overflow="ellipsis")
    if target_currency:
        table.add_column(f"In {target_currency}", justify="right", style="cyan", no_wrap=True)
        table.add_column(f"Price Δ", justify="right", style="magenta", no_wrap=True, overflow="ellipsis")
    if args.tourist:
        tourist_col = f"Tourist {target_currency}" if target_currency else "Tourist Est."
        table.add_column(tourist_col, justify="right", style="yellow", no_wrap=True, overflow="ellipsis")
        if target_currency:
            table.add_column(f"Δ Tourist", justify="right", style="yellow", no_wrap=True, overflow="ellipsis")

    variance_baseline = None
    tourist_variance_baseline = None
    if target_currency:
        base_currency_values = [
            row["converted_numeric"]
            for row in summary_rows
            if row["converted_numeric"] is not None and row["currency"] == target_currency
        ]
        if base_currency_values:
            # Use the selected base currency market as the 0% anchor.
            variance_baseline = min(base_currency_values)
        else:
            # Fallback: if no rows are in target currency, use the cheapest converted row.
            converted_values = [row["converted_numeric"] for row in summary_rows if row["converted_numeric"] is not None]
            if converted_values:
                variance_baseline = min(converted_values)
        if args.tourist:
            tourist_base_currency_values = [
                row["tourist_converted_numeric"]
                for row in summary_rows
                if row["tourist_converted_numeric"] is not None and row["currency"] == target_currency
            ]
            if tourist_base_currency_values:
                tourist_variance_baseline = min(tourist_base_currency_values)
            else:
                tourist_converted_values = [
                    row["tourist_converted_numeric"]
                    for row in summary_rows
                    if row["tourist_converted_numeric"] is not None
                ]
                if tourist_converted_values:
                    tourist_variance_baseline = min(tourist_converted_values)

    for row in summary_rows:
        country_label = f"{row['region_name']} ({row['region_code'].upper()})"
        out = [country_label]
        if len(selected_products) > 1:
            out.append(row["product_name"])
        out.append(str(row["local_display"]))
        if target_currency:
            converted = row["converted_numeric"]
            out.append("-" if converted is None else f"{converted:,.2f}")
            variance_display = "-"
            if (
                converted is not None
                and variance_baseline is not None
                and variance_baseline > 0
            ):
                variance_pct = ((converted - variance_baseline) / variance_baseline) * 100
                variance_display = f"{variance_pct:+.1f}%"
            out.append(variance_display)
        if args.tourist:
            tourist_display = "-"
            if target_currency:
                tourist_value = row["tourist_converted_numeric"]
                tourist_display = "-" if tourist_value is None else f"{tourist_value:,.2f}"
                out.append(tourist_display)
                tourist_variance_display = "-"
                if (
                    tourist_value is not None
                    and tourist_variance_baseline is not None
                    and tourist_variance_baseline > 0
                ):
                    tourist_pct = ((tourist_value - tourist_variance_baseline) / tourist_variance_baseline) * 100
                    tourist_variance_display = f"{tourist_pct:+.1f}%"
                out.append(tourist_variance_display)
            else:
                tourist_value = row["tourist_local_numeric"]
                tourist_display = "-" if tourist_value is None else f"{tourist_value:,.2f}"
                out.append(tourist_display)
        table.add_row(*out)

    if target_currency:
        highlighted_row_indexes = [
            index for index, row in enumerate(summary_rows) if row["currency"] == target_currency
        ]
        for row_index in highlighted_row_indexes:
            table.rows[row_index].style = "bold white on rgb(40,40,40)"

    console.print()
    console.print(table)
    if args.tourist:
        console.print("[dim]Tourist values are modeled estimates (tax rates/refunds vary by store, product, and paperwork).[/dim]")
    if errors:
        console.print(f"\n[dim]Skipped {len(errors)} failed requests.[/dim]")

    console.print("\n[bold green]✓ Done.[/bold green]")


if __name__ == "__main__":
    main()