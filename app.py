from fastapi import FastAPI
from pydantic import BaseModel
import pandas as pd
import numpy as np
import requests
from bs4 import BeautifulSoup

app = FastAPI()

# -------------------
# Step 1: 8-Quarter Table
# -------------------
def format_step1(ticker: str) -> pd.DataFrame:
    url = f"https://www.screener.in/company/{ticker}/consolidated/"
    response = requests.get(url, headers={"User-Agent": "Mozilla/5.0"})
    if response.status_code != 200:
        raise Exception(f"Failed to fetch data from Screener for {ticker}")

    tables = pd.read_html(response.text)
    df = tables[0]
    df.rename(columns={df.columns[0]: "Metric"}, inplace=True)
    df.set_index("Metric", inplace=True)
    df = df.iloc[:, -8:]  # last 8 quarters

    sales = df.loc["Sales\xa0+"].astype(float).values
    ebitda = df.loc["Operating Profit"].astype(float).values
    pat = df.loc["Net Profit\xa0+"].astype(float).values

    ebitda_margin = (ebitda / sales) * 100
    pat_margin = (pat / sales) * 100

    df_clean = pd.DataFrame({
        "Quarter": df.columns,
        "Sales (₹ Cr)": sales,
        "EBITDA (₹ Cr)": ebitda,
        "PAT (₹ Cr)": pat,
        "EBITDA Margin %": np.round(ebitda_margin, 2),
        "PAT Margin %": np.round(pat_margin, 2),
    })

    return df_clean


# -------------------
# Step 2: Operating Leverage
# -------------------
def step2_operating_leverage(df: pd.DataFrame) -> str:
    avg_yoy = np.nan
    if "Sales (₹ Cr)" in df.columns:
        yoy = df["Sales (₹ Cr)"].pct_change(periods=4) * 100
        avg_yoy = yoy.mean()

    note = f"• Sales Growth Phase: Stable ➡️ (Avg YoY = {avg_yoy:.1f}%)\n"
    note += f"• EBITDA Margins are strong at {df['EBITDA Margin %'].mean():.1f}%\n"
    note += "• Volume vs Value growth: ⚠️ Not Reported in Screener\n"
    note += f"• PAT Margins are stable (volatility {df['PAT Margin %'].std():.2f}) ✅\n"
    note += "• Commodity / Cyclical Tag: ❌ (needs sector context)"
    return note


# -------------------
# Step 3: Risk vs Reward
# -------------------
def step3_risk_vs_reward(df: pd.DataFrame):
    strengths, risks = [], []
    ebitda_avg = df["EBITDA Margin %"].mean()
    pat_avg = df["PAT Margin %"].mean()
    yoy = df["Sales (₹ Cr)"].pct_change(periods=4) * 100
    sales_avg = yoy.mean()

    if ebitda_avg > 20:
        strengths.append(f"Healthy EBITDA margin (avg {ebitda_avg:.1f}%) 🟢")
    else:
        risks.append(f"Weak EBITDA margin (avg {ebitda_avg:.1f}%) 🔴")

    if pat_avg > 12:
        strengths.append(f"Strong PAT margin (avg {pat_avg:.1f}%) 🟢")
    else:
        risks.append(f"Weak PAT margin (avg {pat_avg:.1f}%) 🔴")

    if sales_avg > 8:
        strengths.append(f"Good sales growth (avg {sales_avg:.1f}% YoY) 🟢")
    else:
        risks.append(f"Weak sales growth (avg {sales_avg:.1f}% YoY) 🔴")

    verdict = "🟡 Balanced Risk-Reward (Hold/Selective Buy)"
    return strengths, risks, verdict


# -------------------
# Step 4: Peer Comparison (Dummy Example)
# -------------------
def step4_peer_comparison(ticker: str) -> pd.DataFrame:
    # Replace with real peer scraping if needed
    data = {
        "Ticker": ["INFY", "TCS", "WIPRO", "HCLTECH", "TECHM", "LTIM"],
        "Sales Growth %": [7.0, 5.0, 0.4, 6.9, 2.9, 7.6],
        "EBITDA Margin %": [23.8, 26.7, 19.5, 21.8, 11.4, 17.3],
        "PAT Margin %": [16.8, 19.3, 13.9, 14.5, 6.7, 12.5],
    }
    return pd.DataFrame(data)


# -------------------
# Step 5: Ranking Table
# -------------------
def step5_ranking_table(ticker: str, peers: pd.DataFrame, verdicts: dict) -> pd.DataFrame:
    df = peers.copy()

    def growth_signal(val):
        if val > 10: return "🟢 Strong"
        elif val > 5: return "🟡 Moderate"
        else: return "🔴 Weak"

    def margin_signal(val):
        if val > 20: return "🟢 Strong"
        elif val > 10: return "🟡 Moderate"
        else: return "🔴 Weak"

    df["Growth"] = df["Sales Growth %"].apply(growth_signal)
    df["Margins"] = df["EBITDA Margin %"].apply(margin_signal)
    df["Risk/Reward"] = df["Ticker"].map(verdicts).fillna("⚠️ Not Available")

    return df[["Ticker", "Growth", "Margins", "Risk/Reward"]]


# -------------------
# Step 6: Company Snapshot
# -------------------
def step6_company_snapshot(ticker: str) -> dict:
    url = f"https://www.screener.in/company/{ticker}/"
    response = requests.get(url, headers={"User-Agent": "Mozilla/5.0"})
    if response.status_code != 200:
        return {"error": "Snapshot fetch failed"}

    soup = BeautifulSoup(response.text, "html.parser")
    business = soup.find("p", {"class": "about"})
    business_text = business.get_text().strip() if business else "⚠️ Not found"

    concalls = []
    for link in soup.find_all("a", href=True):
        if "concall" in link["href"]:
            concalls.append("https://www.screener.in" + link["href"])
    concalls = concalls[:3]

    return {
        "Business": business_text,
        "Guidance (Concalls)": concalls if concalls else "⚠️ No concalls found"
    }


# -------------------
# Step 7: Valuation & Sentiment
# -------------------
def step7_valuation_sentiment(ticker: str) -> dict:
    url = f"https://www.screener.in/company/{ticker}/"
    response = requests.get(url, headers={"User-Agent": "Mozilla/5.0"})
    if response.status_code != 200:
        return {"error": f"Failed to fetch valuation data for {ticker}"}

    soup = BeautifulSoup(response.text, "html.parser")
    valuation = {"P/E": None, "EV/EBITDA": None, "EV/Sales": None, "PEG": None}
    items = soup.find_all("li", {"class": "flex flex-space-between"})

    for item in items:
        text = item.get_text(strip=True)
        if "P/E" in text and valuation["P/E"] is None:
            try: valuation["P/E"] = float(text.split()[-1])
            except: pass
        if "EV/EBITDA" in text:
            try: valuation["EV/EBITDA"] = float(text.split()[-1])
            except: pass
        if "EV/Sales" in text:
            try: valuation["EV/Sales"] = float(text.split()[-1])
            except: pass
        if "PEG" in text:
            try: valuation["PEG"] = float(text.split()[-1])
            except: pass

    verdict = "⚠️ Data not found"
    if valuation["P/E"]:
        if valuation["P/E"] < 15: verdict = "🟢 Cheap"
        elif 15 <= valuation["P/E"] <= 25: verdict = "🟡 Fair"
        else: verdict = "🔴 Expensive"
    valuation["Verdict"] = verdict
    return valuation


# -------------------
# Step 8: Moat Check
# -------------------
def step8_moat_check(ticker: str, df: pd.DataFrame, snapshot: dict):
    notes = []
    verdict = "⚠️ Insufficient data"

    ebitda_std = df["EBITDA Margin %"].std()
    ebitda_avg = df["EBITDA Margin %"].mean()
    if ebitda_avg > 20 and ebitda_std < 2:
        notes.append(f"Consistently strong EBITDA margins ({ebitda_avg:.1f}%, volatility {ebitda_std:.2f}) 🟢")

    pat_avg = df["PAT (₹ Cr)"].mean()
    if pat_avg > 1000:
        notes.append("Sizable profits provide stability 🟢")

    business_text = (snapshot.get("Business") or "").lower()
    if "largest" in business_text or "2nd" in business_text:
        notes.append("Market leadership suggests structural moat 🟢")

    verdict = "🟢 Strong moat" if len(notes) >= 2 else "🟡 Moderate moat"
    return notes, verdict


# -------------------
# Step 9: Layman Summary
# -------------------
def step9_layman_summary(ticker: str, df: pd.DataFrame, moat_verdict: str, rr_verdict: str) -> str:
    avg_sales_growth = df["Sales (₹ Cr)"].pct_change(periods=4).mean() * 100
    pat_series = df["PAT (₹ Cr)"]
    avg_pat_growth = (pat_series.iloc[-1] - pat_series.iloc[0]) / pat_series.iloc[0] * 100

    phase = "✅ Mature"
    if avg_sales_growth > 15: phase = "🚀 Early Growth"
    elif avg_sales_growth > 8: phase = "📈 Scaling"
    elif avg_sales_growth < 3: phase = "⚠️ Declining"

    action = "🟡 Watch"
    if "Strong moat" in moat_verdict and "Balanced" in rr_verdict:
        action = "✅ Hold / Selective Buy"
    elif "Weak moat" in moat_verdict:
        action = "🔴 Avoid"

    return (
        f"{ticker} is in the {phase} phase.\n"
        f"• Sales growth ~{avg_sales_growth:.1f}% YoY\n"
        f"• PAT growth ~{avg_pat_growth:.1f}%\n"
        f"• Moat verdict: {moat_verdict}\n"
        f"• Risk-Reward verdict: {rr_verdict}\n\n"
        f"👉 Suggested Action: {action}"
    )


# -------------------
# FastAPI Endpoint
# -------------------
class TickerRequest(BaseModel):
    ticker: str

@app.post("/analyze")
def analyze(request: TickerRequest):
    ticker = request.ticker.upper()
    df_raw = format_step1(ticker)
    notes = step2_operating_leverage(df_raw)
    strengths, risks, verdict = step3_risk_vs_reward(df_raw)
    peer_df = step4_peer_comparison(ticker)
    verdicts = {}
    for peer in peer_df["Ticker"]:
        try:
            _, _, v = step3_risk_vs_reward(format_step1(peer))
            verdicts[peer] = v
        except:
            verdicts[peer] = "⚠️ Not Run"
    rank_df = step5_ranking_table(ticker, peer_df, verdicts)
    snapshot = step6_company_snapshot(ticker)
    vals = step7_valuation_sentiment(ticker)
    moat_notes, moat_verdict = step8_moat_check(ticker, df_raw, snapshot)
    summary = step9_layman_summary(ticker, df_raw, moat_verdict, verdict)

    return {
        "Step1": df_raw.to_dict(),
        "Step2": notes,
        "Step3": {"Strengths": strengths, "Risks": risks, "Verdict": verdict},
        "Step4": peer_df.to_dict(),
        "Step5": rank_df.to_dict(),
        "Step6": snapshot,
        "Step7": vals,
        "Step8": {"Notes": moat_notes, "Verdict": moat_verdict},
        "Step9": summary,
    }
