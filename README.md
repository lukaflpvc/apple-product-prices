# Apple Product Prices

Compare Apple product prices worldwide in your terminal.

This script fetches live pricing from Apple regional storefronts, then presents it in a comparison table.  
You can filter by product, convert to your preferred currency, estimate tourist-adjusted pricing, and optionally view full SKU details.

## Why I Built This

My sister, who lives in Europe, is looking to upgrade her Intel-based MacBook Air. The European prices are much higher than the rest of the world. I wanted to make a tool to help me find where it is the cheapest to buy a Mac computer.

The script helped me:
- Find the cheapest Apple product by region
- Compare prices in my currency of choice
- See the changes when tourist tax/refund assumptions are applied

## What The Script Does

- Fetches pricing data from Apple website by region.
- Converts prices to a target currency (`--currency`).
- Shows `% variance` relative to the selected base currency market.
- Supports estimated tourist tax/refund adjustments (`--tourist`).
- Offers two views:
  - default: compact summary table
  - `--details`: full SKU-level breakdown

## Requirements

- [uv](https://docs.astral.sh/uv/) installed
- Internet connection
- Python 3.11+ (handled by `uv` from inline metadata)

## Run

```bash
uv run apple_product_prices.py
```

## Common Examples

### Compare one product in USD

```bash
uv run apple_product_prices.py --product neo --currency usd
```

### Add tourist-adjusted estimates

```bash
uv run apple_product_prices.py --product neo --currency usd --tourist
```

### Show full SKU breakdown

```bash
uv run apple_product_prices.py --product neo --currency usd --details
```

### Combine everything

```bash
uv run apple_product_prices.py --product neo --currency usd --tourist --details
```

## Flags

- `-p, --product`  
  Repeatable product filter (substring match on product name/path).

- `-c, --currency`  
  Convert numeric prices into a target currency code (for example: `usd`, `aud`, `eur`).

- `--tourist`  
  Apply estimated tourist tax/refund logic by region and show tourist-adjusted pricing.

- `--details`  
  Show full SKU-level tables instead of only the compact summary.

## Notes on Tourist Pricing

Tourist output is an estimate.  
Tax policy and refund eligibility can vary by:
- store and country rules
- purchase amount thresholds
- paperwork and departure method
- timing and policy updates

## License
This is made and distributed under MIT License.
