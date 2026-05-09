# Apple Product Prices

Compare global Apple product prices in your terminal.

Fetche live pricing from Apple regional storefronts, then presents it in a comparison table.  
Filter by product, convert to your preferred currency, estimate tourist-adjusted pricing, and optionally view full SKU details.

My sister, who lives in Europe, is looking to upgrade her Intel-based MacBook Air. The European prices are much higher than the rest of the world, so I wanted to make a tool to help me find the cheapest region to buy a MacBook.

## Installation
```bash
uv tool install git+https://git@github.com/lukaflpvc/apple-product-prices.git
```

## Usage
```bash
apple-prices -p <product> -c <currency> --tourist
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
Distributed under MIT License.
