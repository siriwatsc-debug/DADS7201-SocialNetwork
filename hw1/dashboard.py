import streamlit as st
import pandas as pd
import cloudscraper
import yfinance as yf
import plotly.graph_objects as go
import networkx as nx
from datetime import datetime

st.set_page_config(page_title="SET50 Top 5 Shareholders", layout="wide")
st.title("SET50 Top 5 Shareholders")

SET50_SYMBOLS = [
    "ADVANC", "AOT", "AWC", "BANPU", "BBL", "BDMS", "BEM", "BH",
    "BJC", "BTS", "CBG", "CCET", "CENTEL", "COM7", "CPALL", "CPF",
    "CPN", "CRC", "DELTA", "EGCO", "GPSC", "GULF", "HMPRO", "IVL",
    "KBANK", "KKP", "KTB", "KTC", "LH", "MINT", "MTC", "OR", "OSP",
    "PTT", "PTTEP", "PTTGC", "RATCH", "SAWAD", "SCB", "SCC", "SCGP",
    "TCAP", "TIDLOR", "TISCO", "TLI", "TOP", "TRUE", "TTB", "TU",
    "WHA",
]

SET50_SYMBOLS.sort()


@st.cache_data(ttl=3600)
def get_shareholders(symbol):
    scraper = cloudscraper.create_scraper()
    scraper.headers.update({
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
        "Accept": "application/json, text/plain, */*",
        "Referer": "https://www.set.or.th/en/market/product/stock/quote/advanc/company-profile/holder",
        "Origin": "https://www.set.or.th",
    })
    try:
        scraper.get(
            "https://www.set.or.th/en/market/product/stock/quote/advanc/company-profile/holder",
            timeout=10,
        )
        r = scraper.get(
            f"https://www.set.or.th/api/set/stock/{symbol}/shareholder?language=en",
            timeout=10,
        )
        if r.status_code == 200:
            return r.json()
    except Exception:
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
                y=[f"#{i+1} {h['name'][:25]}" for i, h in enumerate(top5)],
                x=[h["percentOfShare"] for h in top5],
                text=[f"{h['percentOfShare']:.2f}%" for h in top5],
                textposition="outside",
                orientation="h",
                marker_color=["#1f77b4", "#ff7f0e", "#2ca02c", "#d62728", "#9467bd"],
            )
        ])
        fig.update_layout(
            title="Ownership % (Top 5)",
            xaxis_title="% of Shares",
            yaxis_title="",
            height=350,
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

st.divider()
st.header("Shareholder Network Across SET50")


def build_shareholder_network():
    scraper = cloudscraper.create_scraper()
    scraper.headers.update({
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
        "Accept": "application/json, text/plain, */*",
        "Referer": "https://www.set.or.th/en/market/product/stock/quote/advanc/company-profile/holder",
        "Origin": "https://www.set.or.th",
    })
    scraper.get(
        "https://www.set.or.th/en/market/product/stock/quote/advanc/company-profile/holder",
        timeout=10,
    )

    G = nx.Graph()
    progress = st.progress(0, text="Fetching shareholder data for all SET50 stocks...")
    success_count = 0

    for i, sym in enumerate(SET50_SYMBOLS):
        progress.progress((i + 1) / len(SET50_SYMBOLS), text=f"Fetching {sym}... ({i+1}/{len(SET50_SYMBOLS)})")
        try:
            r = scraper.get(
                f"https://www.set.or.th/api/set/stock/{sym}/shareholder?language=en",
                timeout=15,
            )
            if r.status_code == 200:
                data = r.json()
                top5 = sorted(data["majorShareholders"], key=lambda h: h["percentOfShare"], reverse=True)[:5]
                for h in top5:
                    name = h["name"][:40]
                    G.add_edge(sym, name, weight=h["percentOfShare"])
                success_count += 1
        except Exception:
            continue

    progress.empty()
    return G, success_count


if st.button("Build Network Graph", type="primary"):
    st.cache_data.clear()
    G, success_count = build_shareholder_network()
    if success_count == 0:
        st.error("Could not fetch any shareholder data from SET. The website may be blocking the request.")
    elif G.number_of_nodes() == 0:
        st.warning("No data available to build the network.")
    else:
        st.success(f"Fetched data for {success_count}/{len(SET50_SYMBOLS)} stocks — {G.number_of_nodes()} nodes, {G.number_of_edges()} edges")
        pos = nx.kamada_kawai_layout(G, scale=2)

        node_degrees = dict(G.degree())
        stock_nodes = [n for n in G.nodes() if n in SET50_SYMBOLS]
        holder_nodes = [n for n in G.nodes() if n not in SET50_SYMBOLS]
        max_holder_degree = max(node_degrees[n] for n in holder_nodes) if holder_nodes else 1

        min_w = min(d["weight"] for _, _, d in G.edges(data=True))
        max_w = max(d["weight"] for _, _, d in G.edges(data=True))

        edge_trace = []
        for u, v, d in G.edges(data=True):
            x0, y0 = pos[u]
            x1, y1 = pos[v]
            w = d["weight"]
            opacity = 0.2 + 0.6 * (w - min_w) / (max_w - min_w) if max_w > min_w else 0.5
            edge_trace.append(go.Scatter(
                x=[x0, x1, None], y=[y0, y1, None],
                mode="lines",
                line=dict(width=max(1, w / 3), color=f"rgba(100,100,100,{opacity})"),
                hoverinfo="text",
                hovertext=f"{u} ↔ {v}<br>Ownership: {w:.2f}%",
                showlegend=False,
            ))

        label_map = {}
        for n in holder_nodes:
            label_map[n] = ""
        for n in holder_nodes:
            if node_degrees[n] >= 3:
                label_map[n] = n[:20]
        for n in stock_nodes:
            label_map[n] = n

        stock_trace = go.Scatter(
            x=[pos[n][0] for n in stock_nodes],
            y=[pos[n][1] for n in stock_nodes],
            mode="markers+text",
            text=[label_map[n] for n in stock_nodes],
            textposition="top center",
            textfont=dict(size=9, color="#1f77b4"),
            marker=dict(
                size=18,
                color="#1f77b4",
                line=dict(width=1, color="white"),
            ),
            name="SET50 Stocks",
            hovertext=[f"<b>{n}</b><br>Top 5 holders: {node_degrees[n]}" for n in stock_nodes],
            hoverinfo="text",
        )

        holder_trace = go.Scatter(
            x=[pos[n][0] for n in holder_nodes],
            y=[pos[n][1] for n in holder_nodes],
            mode="markers+text",
            text=[label_map[n] for n in holder_nodes],
            textposition="top center",
            textfont=dict(size=8, color="#8B4513"),
            marker=dict(
                size=[8 + 12 * node_degrees[n] / max_holder_degree for n in holder_nodes],
                color="#ff7f0e",
                line=dict(width=1, color="white"),
            ),
            name="Shareholders",
            hovertext=[f"<b>{n}</b><br>Holds <b>{node_degrees[n]}</b> SET50 stocks" for n in holder_nodes],
            hoverinfo="text",
        )

        fig = go.Figure(data=[*edge_trace, stock_trace, holder_trace])
        fig.update_layout(
            title="SET50 Stock–Shareholder Network",
            showlegend=True,
            hovermode="closest",
            height=750,
            margin=dict(l=20, r=20, t=40, b=20),
            xaxis=dict(showgrid=False, zeroline=False, visible=False),
            yaxis=dict(showgrid=False, zeroline=False, visible=False),
            plot_bgcolor="rgba(0,0,0,0)",
            legend=dict(
                orientation="h",
                yanchor="bottom",
                y=1.02,
                xanchor="right",
                x=1,
            ),
        )
        st.plotly_chart(fig, use_container_width=True)

        st.subheader("Top Shareholders by Number of SET50 Stocks Held")
        top_holders = sorted(holder_nodes, key=lambda n: node_degrees[n], reverse=True)[:15]
        holders_df = pd.DataFrame([
            {"Rank": i + 1, "Shareholder": n, "SET50 Stocks Held": node_degrees[n]}
            for i, n in enumerate(top_holders)
        ])
        st.dataframe(holders_df, hide_index=True, use_container_width=True)
