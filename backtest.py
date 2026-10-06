"""
BTC core + USDC borrow + HLP carry backtest.

Strategy: hold BTC as collateral on Aave v3, borrow USDC against it,
deposit the USDC in Hyperliquid's HLP vault and pocket the spread
(HLP return - USDC borrow rate).

Data:
  data/btc_daily.csv        Binance BTCUSDT daily low/close
  data/aave_usdc_rates.csv  Aave v3 Ethereum USDC variable borrow APR (Dune, query 8907946)
  data/hlp_vault.json       Hyperliquid vaultDetails for HLP (0xdfc2...f303)
"""
import json
import numpy as np
import pandas as pd

LIQ_THRESHOLD = 0.78   # Aave v3 WBTC / cbBTC liquidation threshold
LIQ_PENALTY = 0.05     # liquidation bonus paid to the liquidator
BTC_FEE = 0.001        # 10 bp per BTC trade (swap + slippage)
INITIAL = 100_000.0


# ---------------------------------------------------------------- data
def load_hlp_daily():
    """HLP daily returns from the vault's PnL and account value history.

    The API only exposes ~100 snapshots (7-14 days apart). Each interval's
    return uses the Modified Dietz method so deposits/withdrawals during
    the interval do not show up as performance, then the interval return
    is spread evenly (geometrically) across its days.
    """
    d = dict(json.load(open("data/hlp_vault.json"))["portfolio"])["allTime"]
    av = pd.DataFrame(d["accountValueHistory"], columns=["ts", "av"])
    pnl = pd.DataFrame(d["pnlHistory"], columns=["ts", "pnl"])
    df = av.merge(pnl, on="ts").astype(float)
    df["day"] = pd.to_datetime(df.ts, unit="ms").dt.normalize()
    df = df.groupby("day").last().reset_index()

    rows = []
    for prev, cur in zip(df.iloc[:-1].itertuples(), df.iloc[1:].itertuples()):
        if prev.av <= 0:
            continue
        d_pnl = cur.pnl - prev.pnl
        flow = (cur.av - prev.av) - d_pnl
        r = d_pnl / (prev.av + 0.5 * flow)
        days = pd.date_range(prev.day + pd.Timedelta(days=1), cur.day)
        daily = (1 + r) ** (1 / len(days)) - 1
        rows += [(day, daily) for day in days]
    return pd.Series(dict(rows), name="hlp_r")


def load_data():
    btc = pd.read_csv("data/btc_daily.csv", parse_dates=["day"]).set_index("day")
    aave = pd.read_csv("data/aave_usdc_rates.csv", parse_dates=["day"]).set_index("day")
    df = btc.join(aave, how="left").join(load_hlp_daily(), how="left")
    df[["borrow_apr", "supply_apr"]] = df[["borrow_apr", "supply_apr"]].ffill()
    return df.dropna()


# ---------------------------------------------------------------- engine
def simulate(df, ltv=0.4, mode="carry", rebalance="ME", hlp_shock=None):
    """Run one strategy path.

    mode:
      "hodl"     100% BTC, no borrowing
      "carry"    BTC collateral, borrow ltv * BTC value, deposit in HLP
      "levered"  BTC collateral, borrow ltv * BTC value, buy more BTC
    rebalance:
      None       set up once on day 0, never touched (static)
      "ME"/"W"   pandas offset: reset debt to ltv * BTC value on those dates;
                 in carry mode the HLP surplus over debt is swept into BTC
                 (or BTC is sold to cover a deficit)
    hlp_shock:   optional (date, pct) one-off HLP loss to stress the path
    """
    dates = df.index
    rebal_days = set()
    if rebalance:
        rebal_days = set(df.groupby(pd.Grouper(freq=rebalance)).tail(1).index)

    p0 = df.close.iloc[0]
    if mode == "hodl":
        btc, debt, hlp = INITIAL / p0 * (1 - BTC_FEE), 0.0, 0.0
    elif mode == "carry":
        btc = INITIAL / p0 * (1 - BTC_FEE)
        debt = ltv * btc * p0
        hlp = debt
    elif mode == "levered":
        # borrow so that debt / collateral = ltv after buying more BTC
        gross = INITIAL / (1 - ltv)
        btc = gross / p0 * (1 - BTC_FEE)
        debt, hlp = gross - INITIAL, 0.0

    out, liquidations = [], []
    interest_paid = hlp_earned = 0.0
    for i, day in enumerate(dates):
        row = df.loc[day]
        if i > 0:
            interest = debt * row.borrow_apr / 365
            debt += interest
            interest_paid += interest
            gain = hlp * row.hlp_r
            hlp += gain
            hlp_earned += gain
            if hlp_shock and day == hlp_shock[0]:
                loss = hlp * hlp_shock[1]
                hlp -= loss
                hlp_earned -= loss

        # liquidation check on the intraday low (Aave only counts BTC as collateral)
        if debt > 0 and debt / (btc * row.low) >= LIQ_THRESHOLD:
            # liquidator repays 50% of debt and seizes BTC worth that + 5%
            repay = 0.5 * debt
            btc -= repay * (1 + LIQ_PENALTY) / row.low
            debt -= repay
            liquidations.append((day.date(), round(row.low)))

        price = row.close
        if day in rebal_days and mode != "hodl":
            equity = btc * price + hlp - debt
            if mode == "carry":
                target_btc = equity            # 1.0x net BTC exposure
                target_debt = ltv * target_btc
                trade = target_btc / price - btc
                btc += trade - abs(trade) * BTC_FEE
                debt, hlp = target_debt, target_debt
            else:
                gross = equity / (1 - ltv)
                trade = gross / price - btc
                btc += trade - abs(trade) * BTC_FEE
                debt = gross - equity

        equity = btc * price + hlp - debt
        out.append((day, equity, btc * price, hlp, debt, debt / (btc * price) if btc else np.nan))

    res = pd.DataFrame(out, columns=["day", "equity", "btc_val", "hlp", "debt", "ltv"]).set_index("day")
    res.attrs.update(liquidations=liquidations, interest_paid=interest_paid, hlp_earned=hlp_earned)
    return res


# ---------------------------------------------------------------- metrics
def metrics(res, rf=None):
    eq = res.equity
    years = (eq.index[-1] - eq.index[0]).days / 365.25
    r = eq.pct_change().dropna()
    dd = eq / eq.cummax() - 1
    vol = r.std() * np.sqrt(365)
    cagr = (eq.iloc[-1] / eq.iloc[0]) ** (1 / years) - 1
    excess = r - (rf.reindex(r.index) / 365 if rf is not None else 0)
    return {
        "final": eq.iloc[-1],
        "total_return": eq.iloc[-1] / INITIAL - 1,
        "cagr": cagr,
        "vol": vol,
        "sharpe": excess.mean() / r.std() * np.sqrt(365),
        "max_dd": dd.min(),
        "max_ltv": res.ltv.max(),
        "liquidations": len(res.attrs["liquidations"]),
        "interest_paid": res.attrs["interest_paid"],
        "hlp_earned": res.attrs["hlp_earned"],
    }


def yearly_spread(df):
    g = df.groupby(df.index.year)
    return pd.DataFrame({
        "hlp_return": g.hlp_r.apply(lambda s: (1 + s).prod() - 1),
        "avg_borrow_apr": g.borrow_apr.mean(),
        "btc_return": g.close.apply(lambda s: s.iloc[-1] / s.iloc[0] - 1),
        "days": g.size(),
    })
