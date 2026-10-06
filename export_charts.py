"""Export weekly-sampled series for the article charts + PNG versions."""
import json
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from backtest import load_data, simulate, yearly_spread

full = load_data()
main = full.loc["2024-01-01":]

hodl = simulate(main, mode="hodl")
carry = simulate(main, ltv=0.4, mode="carry")
static = simulate(main, ltv=0.4, mode="carry", rebalance=None)
eq = pd.DataFrame({"hodl": hodl.equity, "carry": carry.equity, "static": static.equity}).resample("W").last()

# HLP growth vs cost of borrowing, both as an index of $1
idx = pd.DataFrame({
    "hlp": (1 + main.hlp_r).cumprod(),
    "borrow": (1 + main.borrow_apr / 365).cumprod(),
    "btc": main.close,
}).resample("W").last()

peak = full.close.idxmax()
st = simulate(full.loc[peak:], ltv=0.4, mode="carry", rebalance=None)
ltv_path = pd.DataFrame({"ltv": st.debt / (full.loc[peak:].low * st.btc_val / full.loc[peak:].close),
                         "btc": full.loc[peak:].close})

ys = yearly_spread(full.loc["2024-01-01":])
ys["borrow_cost"] = ys.avg_borrow_apr * ys.days / 365

def rows(df):
    return [{"d": str(i.date()), **{k: round(float(v), 4) for k, v in r.items()}} for i, r in df.iterrows()]

json.dump({
    "equity": rows(eq),
    "index": rows(idx),
    "ltv_path": rows(ltv_path),
    "liquidation": [str(d) for d, _ in st.attrs["liquidations"]],
    "yearly": [{"year": int(y), "hlp": round(r.hlp_return, 4), "borrow": round(r.borrow_cost, 4), "days": int(r.days)}
               for y, r in ys.iterrows()],
}, open("chart_data.json", "w"))

# ---- PNGs for the markdown version
BLUE, ORANGE, AQUA, INK, MUTED, GRID = "#2a78d6", "#eb6834", "#1baf7a", "#0b0b0b", "#898781", "#e1e0d9"
plt.rcParams.update({"font.family": "sans-serif", "axes.edgecolor": "#c3c2b7", "axes.grid": True,
                     "grid.color": GRID, "grid.linewidth": 0.6, "axes.spines.top": False,
                     "axes.spines.right": False, "xtick.color": MUTED, "ytick.color": MUTED,
                     "figure.facecolor": "#fcfcfb", "axes.facecolor": "#fcfcfb"})

def save(fig, name):
    fig.tight_layout()
    fig.savefig(f"charts/{name}.png", dpi=180)
    plt.close(fig)

fig, ax = plt.subplots(figsize=(9, 4.6))
for col, c, lab in [("carry", BLUE, "BTC + HLP carry (40% LTV, monthly)"), ("static", AQUA, "BTC + HLP carry (40% LTV, static)"), ("hodl", ORANGE, "BTC buy & hold")]:
    ax.plot(eq.index, eq[col] / 1000, color=c, lw=2, label=lab)
ax.set_ylabel(r"Portfolio value (\$k)", color=MUTED)
ax.legend(frameon=False)
ax.set_title(r"\$100k invested on 1 Jan 2024", loc="left", color=INK)
save(fig, "equity")

fig, ax = plt.subplots(figsize=(9, 4.6))
ax.plot(idx.index, (idx.hlp - 1) * 100, color=BLUE, lw=2, label="HLP cumulative return")
ax.plot(idx.index, (idx.borrow - 1) * 100, color=ORANGE, lw=2, label="Cumulative USDC borrow cost (Aave v3)")
ax.set_ylabel("%", color=MUTED)
ax.legend(frameon=False)
ax.set_title(r"What \$1 in HLP earned vs what \$1 of debt cost", loc="left", color=INK)
save(fig, "hlp_vs_borrow")

fig, ax = plt.subplots(figsize=(9, 4.2))
x = range(len(ys))
ax.bar([i - 0.2 for i in x], ys.hlp_return * 100, 0.38, color=BLUE, label="HLP return")
ax.bar([i + 0.2 for i in x], ys.borrow_cost * 100, 0.38, color=ORANGE, label="USDC borrow cost")
ax.set_xticks(list(x), [f"{y}{' YTD' if y == 2026 else ''}" for y in ys.index])
ax.set_ylabel("%", color=MUTED)
ax.legend(frameon=False)
ax.set_title("The spread is shrinking", loc="left", color=INK)
save(fig, "yearly")

fig, ax = plt.subplots(figsize=(9, 4.2))
ax.plot(ltv_path.index, ltv_path.ltv * 100, color=BLUE, lw=2, label="Loan-to-value (on daily low)")
ax.axhline(78, color="#d03b3b", lw=1.2, ls="--", label="Aave liquidation threshold (78%)")
ax.set_ylabel("LTV %", color=MUTED)
ax.legend(frameon=False, loc="upper left")
ax.set_title("Static 40% LTV opened at the Oct 2025 top", loc="left", color=INK)
save(fig, "ltv_peak")
print("ok", len(eq), len(idx), len(ltv_path))
