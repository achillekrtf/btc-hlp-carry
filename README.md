# BTC + HLP carry backtest

Hold BTC as collateral on Aave v3, borrow USDC against it, deposit the USDC in Hyperliquid's HLP vault and keep the spread. This repo backtests that overlay day by day from 2024 to October 2026.

Write-up: [Paid to HODL: borrowing against Bitcoin to farm HLP](https://achillekrtf.github.io/articles/btc-hlp-carry/)

## Headline results

$100k from 1 January 2024 to 6 October 2026:

| Strategy | Final value | CAGR | Max drawdown |
|---|---|---|---|
| BTC buy & hold | $193.6k | 27.1% | −53.0% |
| Carry, 40% LTV, monthly rebalance | $236.2k | 36.5% | −51.2% |
| 1.4x BTC (same loan buys BTC) | $198.5k | 28.2% | −67.2% |

Full output, including LTV sensitivity, yearly spread, rolling windows and stress tests, is in [`results.txt`](results.txt).

## Run it

```bash
python3 fetch_btc.py      # refresh BTC daily prices (Binance)
python3 run.py            # backtest: prints all results, writes results.json
python3 export_charts.py  # chart data + PNGs in charts/
```

Requires pandas, numpy and matplotlib.

## Data

| File | Source |
|---|---|
| `data/btc_daily.csv` | Binance BTC/USDT daily low and close |
| `data/aave_usdc_rates.csv` | Aave v3 Ethereum USDC variable borrow rate, daily average of `ReserveDataUpdated` events ([Dune query](https://dune.com/queries/8907946)) |
| `data/hlp_vault.json` | Hyperliquid `vaultDetails` API for HLP (`0xdfc24b077bc1425ad1dea75bcb6f8158e10df303`) |

To refresh the HLP history:

```bash
curl -s -X POST https://api.hyperliquid.xyz/info -H 'Content-Type: application/json' \
  -d '{"type":"vaultDetails","vaultAddress":"0xdfc24b077bc1425ad1dea75bcb6f8158e10df303"}' > data/hlp_vault.json
```

## Method

- **HLP returns:** the API exposes about 100 snapshots, 7 to 14 days apart. Each interval's return uses the Modified Dietz method so deposits and withdrawals do not count as performance, then is spread evenly over the interval's days.
- **Borrowing:** interest accrues daily on the outstanding loan at that day's Aave rate.
- **Liquidation:** checked on the daily low with Aave's 78% WBTC threshold; each event closes 50% of the debt with a 5% penalty. HLP does not count as collateral.
- **Rebalancing (monthly mode):** reset the loan to the target LTV and sweep the HLP surplus over the debt into BTC, keeping net BTC exposure at 1x.
- **Costs:** 10 bp per BTC trade. No gas, bridge fees or taxes.

## Limitations

Snapshot spacing smooths out short HLP drawdowns. HLP was picked knowing it survived. 2023 is excluded from the headline numbers because the vault was under $15M and its returns were extreme.

Personal research, not investment advice.
