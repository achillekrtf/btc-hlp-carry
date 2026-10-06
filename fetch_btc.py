import json, subprocess, pandas as pd

def get(url):
    return json.loads(subprocess.check_output(["curl", "-s", url]))

start = int(pd.Timestamp("2023-05-01").timestamp() * 1000)
rows = []
while True:
    batch = get(f"https://api.binance.com/api/v3/klines?symbol=BTCUSDT&interval=1d&startTime={start}&limit=1000")
    if not batch:
        break
    rows += batch
    start = batch[-1][0] + 86_400_000
    if len(batch) < 1000:
        break
df = pd.DataFrame(rows).iloc[:, [0, 3, 4]]
df.columns = ["ts", "low", "close"]
df["day"] = pd.to_datetime(df.ts, unit="ms").dt.date
df = df[["day", "low", "close"]].astype({"low": float, "close": float})
df.to_csv("data/btc_daily.csv", index=False)
print(len(df), df.iloc[0].tolist(), df.iloc[-1].tolist())
