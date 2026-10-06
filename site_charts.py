"""Charts for achillekrtf.github.io (dark theme, site palette)."""
import json
import os
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.dates as mdates

OUT = "site-article/public/images/btc-hlp"
os.makedirs(OUT, exist_ok=True)
BG, FG, MUTED, GRID, AXIS = "#191c1f", "#ececec", "#8b9098", "#2a2e33", "#3a3f45"
BLUE, ORANGE, AQUA, RED = "#3987e5", "#d95926", "#199e70", "#e66767"
plt.rcParams.update({
    "font.family": "sans-serif", "font.size": 11, "text.color": FG,
    "figure.facecolor": BG, "axes.facecolor": BG, "savefig.facecolor": BG,
    "axes.edgecolor": AXIS, "axes.grid": True, "axes.axisbelow": True, "grid.color": GRID, "grid.linewidth": 0.8,
    "axes.spines.top": False, "axes.spines.right": False, "axes.spines.left": False,
    "xtick.color": MUTED, "ytick.color": MUTED, "xtick.major.size": 0, "ytick.major.size": 0,
    "legend.frameon": False, "legend.labelcolor": FG,
})
d = json.load(open("chart_data.json"))

def frame(key):
    df = pd.DataFrame(d[key]); df["d"] = pd.to_datetime(df.d); return df.set_index("d")

def finish(fig, ax, name, title):
    ax.set_title(title, loc="left", color=FG, fontsize=13, pad=14)
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%b %Y"))
    fig.tight_layout()
    fig.savefig(f"{OUT}/{name}.png", dpi=200)
    plt.close(fig)

def end_labels(ax, x, items, fmt, gap):
    items = sorted(items, key=lambda t: t[1])
    ys = []
    for _, y, _ in items:
        ys.append(max(y, ys[-1] + gap) if ys else y)
    for (c, y, v), yl in zip(items, ys):
        ax.plot([x], [y], "o", color=c, ms=6, mec=BG, mew=1.5, zorder=5)
        ax.annotate(fmt(v), (x, yl), xytext=(8, 0), textcoords="offset points", va="center", color=FG, fontsize=10, fontweight="bold")

# 1. equity
eq = frame("equity"); eq.index = eq.index.where(eq.index <= "2026-10-06", pd.Timestamp("2026-10-06"))
fig, ax = plt.subplots(figsize=(10, 5.2))
series = [("carry", BLUE, "Carry, 40% LTV, monthly rebalance"), ("static", AQUA, "Carry, 40% LTV, static"), ("hodl", ORANGE, "BTC buy & hold")]
for col, c, lab in series:
    ax.plot(eq.index, eq[col] / 1000, color=c, lw=2, label=lab)
ax.yaxis.set_major_formatter(lambda v, _: f"${v:.0f}k")
end_labels(ax, eq.index[-1], [(c, eq[col].iloc[-1] / 1000, eq[col].iloc[-1]) for col, c, _ in series], lambda v: f"${v/1000:.0f}k", 9)
ax.legend(loc="upper left")
ax.margins(x=0.02); ax.set_xlim(right=eq.index[-1] + pd.Timedelta(days=75))
finish(fig, ax, "equity", "$100k invested on 1 Jan 2024".replace("$", r"\$"))

# 2. HLP vs borrow
ix = frame("index"); ix.index = ix.index.where(ix.index <= "2026-10-06", pd.Timestamp("2026-10-06"))
fig, ax = plt.subplots(figsize=(10, 5))
ax.plot(ix.index, (ix.hlp - 1) * 100, color=BLUE, lw=2, label="HLP cumulative return")
ax.plot(ix.index, (ix.borrow - 1) * 100, color=ORANGE, lw=2, label="Aave USDC borrow cost")
ax.yaxis.set_major_formatter(lambda v, _: f"{v:.0f}%")
end_labels(ax, ix.index[-1], [(BLUE, (ix.hlp.iloc[-1] - 1) * 100, ix.hlp.iloc[-1] - 1), (ORANGE, (ix.borrow.iloc[-1] - 1) * 100, ix.borrow.iloc[-1] - 1)], lambda v: f"+{v*100:.0f}%", 6)
for day, lab in [("2025-10-10", "Oct 2025\nflash crash"), ("2026-02-05", "Feb 2026\nBTC at $60k")]:
    ax.axvline(pd.Timestamp(day), color=MUTED, lw=0.8, ls=":")
    ax.annotate(lab.replace("$", r"\$"), (pd.Timestamp(day), 30), xytext=(-6, 0), textcoords="offset points", ha="right", color=MUTED, fontsize=9)
ax.legend(loc="upper left")
ax.set_xlim(right=ix.index[-1] + pd.Timedelta(days=60))
finish(fig, ax, "hlp-vs-borrow", r"What \$1 in HLP earned vs what \$1 of debt cost")

# 3. yearly
ys = pd.DataFrame(d["yearly"])
fig, ax = plt.subplots(figsize=(10, 4.6))
x = range(len(ys)); w = 0.36
for off, col, c, lab in [(-w / 2 - 0.01, "hlp", BLUE, "HLP return"), (w / 2 + 0.01, "borrow", ORANGE, "USDC borrow cost")]:
    bars = ax.bar([i + off for i in x], ys[col] * 100, w, color=c, label=lab)
    for b, v in zip(bars, ys[col]):
        ax.annotate(f"{v*100:.1f}%", (b.get_x() + b.get_width() / 2, v * 100), xytext=(0, 4), textcoords="offset points", ha="center", color=FG, fontsize=10, fontweight="bold")
ax.set_xticks(list(x), [f"{y}" + (" (to 6 Oct)" if y == 2026 else "") for y in ys.year])
ax.yaxis.set_major_formatter(lambda v, _: f"{v:.0f}%")
ax.grid(axis="x", visible=False)
ax.legend(loc="upper right")
ax.set_title("HLP return vs borrow cost, by calendar year", loc="left", color=FG, fontsize=13, pad=14)
fig.tight_layout(); fig.savefig(f"{OUT}/yearly.png", dpi=200); plt.close(fig)

# 4. LTV from the top
lt = frame("ltv_path")
fig, ax = plt.subplots(figsize=(10, 4.6))
ax.plot(lt.index, lt.ltv * 100, color=BLUE, lw=2, label="Loan-to-value on the daily low")
ax.axhline(78, color=RED, lw=1.4, ls="--", label="Aave liquidation threshold (78%)")
liq = pd.Timestamp(d["liquidation"][0])
ax.plot([liq], [78], "o", color=RED, ms=8, mec=BG, mew=2, zorder=5)
ax.annotate("Liquidated, 5 Feb 2026\nBTC low \\$62,345", (liq, 78), xytext=(-12, 6), textcoords="offset points", ha="right", va="bottom", color=FG, fontsize=10, fontweight="bold")
ax.yaxis.set_major_formatter(lambda v, _: f"{v:.0f}%")
ax.set_ylim(30, 90)
ax.legend(loc="lower right")
finish(fig, ax, "ltv-from-top", "Static 40% LTV opened at the Oct 2025 top ($124,659)".replace("$", r"\$"))
print("ok")
