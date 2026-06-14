import streamlit as st
import pandas as pd
import requests
import yfinance as yf
import plotly.graph_objects as go
from datetime import datetime

st.set_page_config(page_title="SET50 Top 5 Shareholders", layout="wide")
st.title("SET50 Top 5 Shareholders")

SET50_SYMBOLS = [
    "ADVANC", "AOT", "AWC", "BAM", "BANPU", "BBL", "BCH", "BDMS",
    "BEM", "BGRIM", "BH", "BJC", "BLA", "BTS", "CPALL", "CPF", "CPN",
    "CRC", "DELTA", "EA", "EGCO", "GLOBAL", "GPSC", "GULF", "HMPRO",
    "INTUCH", "IRPC", "IVL", "KBANK", "KCE", "KTB", "KTC", "LH",
    "MINT", "MTC", "OR", "OSP", "PLANB", "PTT", "PTTEP", "PTTGC",
    "SAWAD", "SCB", "SCC", "TISCO", "TOP", "TRUE", "TU", "WHA",
]

SET50_SYMBOLS.sort()


@st.cache_data(ttl=3600)
def get_shareholders(symbol):
    session = requests.Session()
    session.headers.update({
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
        "Accept": "application/json, text/plain, */*",
        "Referer": "https://www.set.or.th/en/market/product/stock/quote/advanc/company-profile/holder",
        "Origin": "https://www.set.or.th",
    })
    try:
        session.get(
            "https://www.set.or.th/en/market/product/stock/quote/advanc/company-profile/holder",
            timeout=10,
        )
        r = session.get(
            f"https://www.set.or.th/api/set/stock/{symbol}/shareholder?language=en",
            timeout=10,
        )
        if r.status_code == 200:
            return r.json()
    except requests.RequestException:
        pass
    return None


@st.cache_data(ttl=300)
def get_stock_info(symbol):
    try:
        ticker = yf.Ticker(f"{symbol}.BK")
        info = ticker.info
        hist = ticker.history(period="5d")
        price = hist["Close"].iloc[-1] if not hist.empty else None
        change = hist["Close"].diff().iloc[-1] if len(hist) > 1 else None
        change_pct = (hist["Close"].pct_change().iloc[-1] * 100) if len(hist) > 1 else None
        return {
            "price": price,
            "change": change,
            "change_pct": change_pct,
            "name": info.get("longName", info.get("shortName", symbol)),
            "market_cap": info.get("marketCap"),
            "pe_ratio": info.get("trailingPE"),
        }
    except Exception:
        return None


col1, col2, col3 = st.columns([1, 3, 1])

with col1:
    st.subheader("Select Stock")
    selected = st.selectbox("SET50 Symbol", SET50_SYMBOLS, label_visibility="collapsed")

with col3:
    st.subheader("")
    if st.button("Refresh"):
        st.cache_data.clear()
        st.rerun()

with col2:
    st.subheader("")
    if selected:
        st.markdown(f"### {selected}")

info = get_stock_info(selected)
sh_data = get_shareholders(selected)

if info:
    price = info["price"]
    change = info.get("change")
    pct = info.get("change_pct")
    delta_color = "normal" if change and change >= 0 else "inverse"
    m1, m2, m3, m4 = st.columns(4)
    if price:
        m1.metric("Price (THB)", f"{price:.2f}", f"{change:+.2f} ({pct:+.2f}%)" if change is not None else None,
                  delta_color=delta_color)
    m2.metric("Market Cap", f"{info['market_cap']/1e9:.2f}B" if info.get("market_cap") else "N/A")
    m3.metric("P/E", f"{info['pe_ratio']:.2f}" if info.get("pe_ratio") else "N/A")
    m4.metric("Company", info["name"][:30] if info.get("name") else "N/A")

st.divider()

if sh_data and sh_data.get("majorShareholders"):
    all_holders = sh_data["majorShareholders"]
    top5 = sorted(all_holders, key=lambda h: h["percentOfShare"], reverse=True)[:5]
    df = pd.DataFrame([
        {
            "Rank": i + 1,
            "Shareholder": h["name"],
            "Shares": f"{h['numberOfShare']:,.0f}",
            "% Ownership": h["percentOfShare"],
            "Thai NVDR": "Yes" if h.get("isThaiNVDR") else "No",
        }
        for i, h in enumerate(top5)
    ])

    c1, c2 = st.columns([2, 3])

    with c1:
        st.subheader("Top 5 Shareholders")
        st.dataframe(df, hide_index=True, use_container_width=True)

        total_sh = sh_data.get("totalShareholder", 0)
        free_float = sh_data.get("freeFloat", {})
        st.caption(
            f"Total shareholders: {total_sh:,}  |  "
            f"Free float: {free_float.get('percentFreeFloat', 'N/A')}%"
        )

    with c2:
        fig = go.Figure(data=[
            go.Bar(
                y=[h["name"][:30] for h in top5],
                x=[h["percentOfShare"] for h in top5],
                text=[f"{h['percentOfShare']:.2f}%" for h in top5],
                textposition="outside",
                orientation="h",
                marker_color=["#1f77b4", "#ff7f0e", "#2ca02c", "#d62728", "#9467bd"],
            )
        ])
        fig.update_layout(
            title="Ownership % (Descending)",
            xaxis_title="% of Shares",
            yaxis_title="",
            height=300,
            margin=dict(l=0, r=0, t=40, b=0),
        )
        st.plotly_chart(fig, use_container_width=True)

    st.divider()

    with st.expander("View all shareholders"):
        all_df = pd.DataFrame([
            {
                "Rank": h["sequence"],
                "Shareholder": h["name"],
                "Shares": f"{h['numberOfShare']:,.0f}",
                "% Ownership": h["percentOfShare"],
            }
            for h in sh_data["majorShareholders"]
        ])
        st.dataframe(all_df, hide_index=True, use_container_width=True)

else:
    st.info("Shareholder data not available at this time.")
