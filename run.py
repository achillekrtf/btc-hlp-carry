import json
import numpy as np
import pandas as pd
from backtest import load_data, simulate, metrics, yearly_spread, LIQ_THRESHOLD

pd.set_option("display.width", 200)
full = load_data()
periods = {
    "main (2024-01 to now)": full.loc["2024-01-01":],
    "full (2023-06 to now)": full.loc["2023-06-01":],
    "last 12m": full.iloc[-365:],
}

results = {}
for name, df in periods.items():
    rf = df.supply_apr
    rows = {
        "BTC buy & hold": metrics(simulate(df, mode="hodl"), rf),
        "Carry 40%, static": metrics(simulate(df, ltv=0.4, mode="carry", rebalance=None), rf),
        "Carry 40%, monthly rebal": metrics(simulate(df, ltv=0.4, mode="carry"), rf),
        "1.4x BTC (borrow to buy BTC)": metrics(simulate(df, ltv=0.4 / 1.4, mode="levered"), rf),
    }
    t = pd.DataFrame(rows).T
    results[name] = t
    print(f"\n=== {name}: {df.index[0].date()} -> {df.index[-1].date()} ===")
    print(t.round(3).to_string())

print("\n=== Yearly HLP return vs Aave USDC borrow ===")
ys = yearly_spread(full.loc["2023-06-01":])
ys["spread"] = ys.hlp_return - ys.avg_borrow_apr * ys.days / 365
print(ys.round(4).to_string())

print("\n=== LTV sensitivity, monthly rebalanced carry, main period ===")
main = periods["main (2024-01 to now)"]
sens = {}
for ltv in [0.0, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7]:
    m = metrics(simulate(main, ltv=ltv, mode="carry"), main.supply_apr)
    m["crash_to_liquidate"] = 1 - ltv / LIQ_THRESHOLD
    sens[ltv] = m
sens = pd.DataFrame(sens).T
print(sens[["cagr", "vol", "sharpe", "max_dd", "max_ltv", "liquidations", "crash_to_liquidate"]].round(3).to_string())

print("\n=== Rolling 12m start dates: carry (monthly) minus HODL ===")
starts = full.loc["2023-06-01":].index[::14]
roll = []
for s in starts:
    window = full.loc[s: s + pd.Timedelta(days=365)]
    if len(window) < 360:
        break
    h = simulate(window, mode="hodl").equity.iloc[-1]
    c = simulate(window, ltv=0.4, mode="carry").equity.iloc[-1]
    roll.append((s, (c - h) / 100_000))
roll = pd.Series(dict(roll))
print(roll.describe().round(4).to_string())
print("share of windows where carry beat HODL:", round((roll > 0).mean(), 3))

print("\n=== Stress: BTC crash needed to liquidate a static 40% LTV entered at the top ===")
peak_day = full.close.idxmax()
print("BTC peak", peak_day.date(), full.close.max())
stress_static = simulate(full.loc[peak_day:], ltv=0.4, mode="carry", rebalance=None)
print("static from peak: max LTV", round(stress_static.ltv.max(), 3), "liqs", stress_static.attrs["liquidations"])
for ltv in [0.5, 0.6]:
    s = simulate(full.loc[peak_day:], ltv=ltv, mode="carry", rebalance=None)
    print(f"static {ltv:.0%} from peak: max LTV {s.ltv.max():.3f}, liquidations {s.attrs['liquidations']}, "
          f"final {s.equity.iloc[-1]:,.0f}")

print("\n=== Stress: HLP loses 20% in a single day (worst-case vault event) ===")
shock_day = main.index[len(main) // 2]
base = simulate(main, ltv=0.4, mode="carry")
shock = simulate(main, ltv=0.4, mode="carry", hlp_shock=(shock_day, 0.20))
print("shock on", shock_day.date(), "final equity", round(base.equity.iloc[-1]), "->", round(shock.equity.iloc[-1]),
      f"({shock.equity.iloc[-1] / base.equity.iloc[-1] - 1:.2%})")

# persist for charts / article
out = {k: v.round(5).to_dict(orient="index") for k, v in results.items()}
out["yearly"] = ys.round(5).to_dict(orient="index")
out["sensitivity"] = sens.round(5).to_dict(orient="index")
out["rolling"] = {"mean": roll.mean(), "median": roll.median(), "min": roll.min(), "max": roll.max(),
                  "win_rate": (roll > 0).mean()}
out["hlp_shock"] = {"day": str(shock_day.date()), "base": base.equity.iloc[-1], "shock": shock.equity.iloc[-1]}
json.dump(out, open("results.json", "w"), indent=1, default=float)
roll.to_csv("data/rolling_12m_excess.csv")
