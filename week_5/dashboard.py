import streamlit as st
import requests
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime
from dotenv import load_dotenv
from pathlib import Path
import os

load_dotenv(dotenv_path=Path(__file__).parent / ".env")

DUNE_API_KEY      = os.getenv("DUNE_API_KEY")
COINGECKO_API_KEY = os.getenv("COINGECKO_API_KEY")

SIM_BASE_URL       = "https://api.sim.dune.com/v1"
COINGECKO_BASE_URL = "https://pro-api.coingecko.com/api/v3"

sim_headers = {"X-Sim-Api-Key": DUNE_API_KEY}
cg_headers  = {"x-cg-pro-api-key": COINGECKO_API_KEY, "accept": "application/json"}

# Page setup 
st.set_page_config(
    page_title="On-Chain Dashboard",
    page_icon="⛓️",
    layout="wide",
)

# Custom CSS 
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=IBM+Plex+Mono:wght@400;500&family=IBM+Plex+Sans:wght@300;400;500;600&display=swap');

html, body, [class*="css"] {
    font-family: 'IBM Plex Sans', sans-serif;
}

/* Dark background */
.stApp { background-color: #0d0f14; }

/* Top header bar */
.dash-header {
    background: linear-gradient(135deg, #0d0f14 0%, #131720 100%);
    border-bottom: 1px solid #1e2433;
    padding: 1.2rem 0 1rem;
    margin-bottom: 1.5rem;
}
.dash-title {
    font-family: 'IBM Plex Mono', monospace;
    font-size: 1.5rem;
    font-weight: 500;
    color: #e2e8f0;
    letter-spacing: -0.02em;
}
.dash-subtitle {
    font-size: 0.78rem;
    color: #4a5568;
    font-family: 'IBM Plex Mono', monospace;
    letter-spacing: 0.05em;
    text-transform: uppercase;
}

/* Metric cards */
.metric-card {
    background: #131720;
    border: 1px solid #1e2433;
    border-radius: 10px;
    padding: 1.1rem 1.3rem;
    transition: border-color .2s;
}
.metric-card:hover { border-color: #2d3a55; }
.metric-label {
    font-size: 0.72rem;
    color: #4a5568;
    font-family: 'IBM Plex Mono', monospace;
    text-transform: uppercase;
    letter-spacing: 0.08em;
    margin-bottom: 0.35rem;
}
.metric-value {
    font-family: 'IBM Plex Mono', monospace;
    font-size: 1.45rem;
    font-weight: 500;
    color: #e2e8f0;
}
.metric-delta-pos { color: #48bb78; font-size: 0.8rem; font-family: 'IBM Plex Mono', monospace; }
.metric-delta-neg { color: #fc8181; font-size: 0.8rem; font-family: 'IBM Plex Mono', monospace; }

/* Section headers */
.section-header {
    font-family: 'IBM Plex Mono', monospace;
    font-size: 0.72rem;
    color: #4a5568;
    text-transform: uppercase;
    letter-spacing: 0.12em;
    border-bottom: 1px solid #1e2433;
    padding-bottom: 0.5rem;
    margin: 1.5rem 0 1rem;
}

/* Sidebar */
[data-testid="stSidebar"] {
    background-color: #0d0f14;
    border-right: 1px solid #1e2433;
}
[data-testid="stSidebar"] label { color: #718096 !important; font-size: 0.8rem; }

/* Dataframe */
[data-testid="stDataFrame"] { border: 1px solid #1e2433; border-radius: 8px; overflow: hidden; }

/* Inputs */
.stTextInput input, .stSelectbox select {
    background: #131720 !important;
    border: 1px solid #1e2433 !important;
    color: #e2e8f0 !important;
    font-family: 'IBM Plex Mono', monospace !important;
    font-size: 0.85rem !important;
}

/* Tab styling */
.stTabs [data-baseweb="tab-list"] { background: transparent; border-bottom: 1px solid #1e2433; }
.stTabs [data-baseweb="tab"] {
    background: transparent;
    color: #4a5568;
    font-family: 'IBM Plex Mono', monospace;
    font-size: 0.78rem;
    letter-spacing: 0.05em;
    text-transform: uppercase;
}
.stTabs [aria-selected="true"] { color: #e2e8f0 !important; border-bottom: 2px solid #4299e1 !important; }

/* Hide streamlit branding */
#MainMenu, footer, header { visibility: hidden; }
</style>
""", unsafe_allow_html=True)

# Plotly dark theme 
PLOT_LAYOUT = dict(
    paper_bgcolor="#131720",
    plot_bgcolor="#131720",
    font=dict(family="IBM Plex Mono", color="#718096", size=11),
    xaxis=dict(gridcolor="#1e2433", linecolor="#1e2433", tickcolor="#4a5568"),
    yaxis=dict(gridcolor="#1e2433", linecolor="#1e2433", tickcolor="#4a5568"),
    margin=dict(l=0, r=0, t=10, b=0),
)

# Helper functions 
def fmt_usd(val):
    if val >= 1e12: return f"${val/1e12:.2f}T"
    if val >= 1e9:  return f"${val/1e9:.2f}B"
    if val >= 1e6:  return f"${val/1e6:.2f}M"
    return f"${val:,.2f}"

def fmt_price(val):
    if val >= 1000: return f"${val:,.0f}"
    if val >= 1:    return f"${val:.4f}"
    return f"${val:.6f}"

def parse_wei(val):
    try:
        if pd.isna(val): return 0.0
        s = str(val).strip()
        if s.startswith("0x") or s.startswith("0X"):
            return int(s, 16) / 1e18
        return float(s) / 1e18
    except:
        return 0.0

# API functions (cached) 
@st.cache_data(ttl=60)
def get_crypto_prices(coin_ids, vs_currency="usd"):
    url    = f"{COINGECKO_BASE_URL}/simple/price"
    params = {
        "ids":                     ",".join(coin_ids),
        "vs_currencies":           vs_currency,
        "include_market_cap":      "true",
        "include_24hr_vol":        "true",
        "include_24hr_change":     "true",
        "include_last_updated_at": "true",
    }
    r = requests.get(url, headers=cg_headers, params=params)
    if r.status_code != 200:
        st.error(f"CoinGecko error: {r.status_code}")
        return None
    data = r.json()
    df   = pd.DataFrame(data).T
    df.index.name = "coin_id"
    df.reset_index(inplace=True)
    df.rename(columns={
        vs_currency:                "price",
        f"{vs_currency}_market_cap":"market_cap",
        f"{vs_currency}_24h_vol":   "volume_24h",
        f"{vs_currency}_24h_change":"change_24h_%",
        "last_updated_at":          "last_updated_at",
    }, inplace=True)
    df["last_updated_at"] = pd.to_datetime(df["last_updated_at"], unit="s")
    for col in ["price","market_cap","volume_24h","change_24h_%"]:
        df[col] = pd.to_numeric(df[col], errors="coerce")
    return df


@st.cache_data(ttl=60)
def get_market_chart(coin_id, vs_currency="usd", days=30):
    url    = f"{COINGECKO_BASE_URL}/coins/{coin_id}/market_chart"
    params = {"vs_currency": vs_currency, "days": days}
    r = requests.get(url, headers=cg_headers, params=params)
    if r.status_code != 200:
        return None, None, None
    data       = r.json()
    def to_df(series, col):
        df = pd.DataFrame(series, columns=["ts", col])
        df["date"] = pd.to_datetime(df["ts"], unit="ms")
        return df[["date", col]]
    return to_df(data["prices"], "price"), to_df(data["market_caps"], "market_cap"), to_df(data["total_volumes"], "volume")


@st.cache_data(ttl=60)
def get_wallet_transactions(address, limit=100, chain_ids="1"):
    url    = f"{SIM_BASE_URL}/evm/transactions/{address}"
    params = {"limit": limit, "chain_ids": chain_ids}
    r = requests.get(url, headers=sim_headers, params=params)
    if r.status_code != 200:
        st.error(f"Dune SIM error: {r.status_code} — {r.text}")
        return None
    data = r.json()
    txs  = data.get("transactions", [])
    if not txs:
        return pd.DataFrame()
    df = pd.DataFrame(txs)
    if "block_time" in df.columns:
        df["block_time"] = pd.to_datetime(df["block_time"])
    if "value" in df.columns:
        df["value_eth"] = df["value"].apply(parse_wei)
    for col in ["gas","gas_price","gas_used"]:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")
    return df.sort_values("block_time", ascending=False) if "block_time" in df.columns else df


# Sidebar 
with st.sidebar:
    st.markdown("### ⛓️ On-Chain Dashboard")
    st.markdown("---")

    st.markdown("**Market Data**")
    coin_input = st.text_input(
        "Coins (comma-separated)",
        value="bitcoin,ethereum,solana,binancecoin,uniswap",
        help="CoinGecko coin IDs"
    )
    days_input = st.selectbox("Price history", [7, 14, 30, 90, 180], index=2)
    focus_coin = st.selectbox(
        "Chart focus",
        [c.strip() for c in coin_input.split(",") if c.strip()]
    )

    st.markdown("---")
    st.markdown("**Wallet Explorer**")
    wallet = st.text_input(
        "Wallet address",
        value="0xd8dA6BF26964aF9D7eEd9e03E53415D37aA96045",
        help="Any EVM address"
    )
    tx_limit = st.slider("Tx limit", 10, 100, 50, step=10)

    st.markdown("---")
    if st.button("Refresh", use_container_width=True):
        st.cache_data.clear()
        st.rerun()

    st.markdown(f"""
    <div style='font-family:IBM Plex Mono;font-size:0.68rem;color:#2d3a55;margin-top:1rem;'>
    Last refresh<br>{datetime.now().strftime('%H:%M:%S')}
    </div>
    """, unsafe_allow_html=True)

# Load data 
coin_ids = [c.strip() for c in coin_input.split(",") if c.strip()]

with st.spinner("Fetching market data…"):
    df_prices = get_crypto_prices(coin_ids)

with st.spinner("Fetching price history…"):
    df_price_hist, df_mktcap_hist, df_vol_hist = get_market_chart(focus_coin, days=days_input)

with st.spinner("Fetching wallet transactions…"):
    df_txs = get_wallet_transactions(wallet, limit=tx_limit)

#  Header 
st.markdown(f"""
<div class="dash-header">
  <div class="dash-title">⛓ On-Chain Dashboard</div>
  <div class="dash-subtitle">Dune SIM API &nbsp;·&nbsp; CoinGecko Pro &nbsp;·&nbsp; Ethereum Mainnet</div>
</div>
""", unsafe_allow_html=True)

# Tabs 
tab1, tab2, tab3 = st.tabs(["📈  Market", "🔍  Wallet", "📊  Raw Data"])

# TAB 1 — MARKET
with tab1:

    # Metric cards 
    if df_prices is not None and not df_prices.empty:
        cols = st.columns(len(df_prices))
        for i, row in df_prices.iterrows():
            chg   = row.get("change_24h_%", 0) or 0
            delta = f"▲ {chg:.2f}%" if chg >= 0 else f"▼ {abs(chg):.2f}%"
            cls   = "metric-delta-pos" if chg >= 0 else "metric-delta-neg"
            with cols[i]:
                st.markdown(f"""
                <div class="metric-card">
                  <div class="metric-label">{row['coin_id'].upper()}</div>
                  <div class="metric-value">{fmt_price(row['price'])}</div>
                  <div class="{cls}">{delta}</div>
                </div>
                """, unsafe_allow_html=True)

    st.markdown('<div class="section-header">Price history — ' + focus_coin.upper() + '</div>', unsafe_allow_html=True)

    # Price chart 
    if df_price_hist is not None:
        fig = go.Figure()
        fig.add_trace(go.Scatter(
            x=df_price_hist["date"],
            y=df_price_hist["price"],
            mode="lines",
            line=dict(color="#4299e1", width=1.5),
            fill="tozeroy",
            fillcolor="rgba(66,153,225,0.05)",
            name="Price",
            hovertemplate="$%{y:,.2f}<extra></extra>",
        ))
        fig.update_layout(**PLOT_LAYOUT, height=280)
        fig.update_yaxes(tickprefix="$", tickformat=",.0f")
        st.plotly_chart(fig, use_container_width=True)

    # Volume + Market cap side by side
    col_l, col_r = st.columns(2)

    with col_l:
        st.markdown('<div class="section-header">Volume</div>', unsafe_allow_html=True)
        if df_vol_hist is not None:
            fig2 = go.Figure()
            fig2.add_trace(go.Bar(
                x=df_vol_hist["date"],
                y=df_vol_hist["volume"],
                marker_color="#48bb78",
                marker_opacity=0.7,
                hovertemplate="$%{y:,.0f}<extra></extra>",
            ))
            fig2.update_layout(**PLOT_LAYOUT, height=200)
            fig2.update_yaxes(tickprefix="$", tickformat=".2s")
            st.plotly_chart(fig2, use_container_width=True)

    with col_r:
        st.markdown('<div class="section-header">Market cap</div>', unsafe_allow_html=True)
        if df_mktcap_hist is not None:
            fig3 = go.Figure()
            fig3.add_trace(go.Scatter(
                x=df_mktcap_hist["date"],
                y=df_mktcap_hist["market_cap"],
                mode="lines",
                line=dict(color="#ed8936", width=1.5),
                fill="tozeroy",
                fillcolor="rgba(237,137,54,0.05)",
                hovertemplate="$%{y:,.0f}<extra></extra>",
            ))
            fig3.update_layout(**PLOT_LAYOUT, height=200)
            fig3.update_yaxes(tickprefix="$", tickformat=".2s")
            st.plotly_chart(fig3, use_container_width=True)

    # ── All coins comparison table ────────────────────────────────────────────
    st.markdown('<div class="section-header">All coins snapshot</div>', unsafe_allow_html=True)
    if df_prices is not None:
        display = df_prices[["coin_id","price","market_cap","volume_24h","change_24h_%","last_updated_at"]].copy()
        display["price"]       = display["price"].apply(fmt_price)
        display["market_cap"]  = display["market_cap"].apply(fmt_usd)
        display["volume_24h"]  = display["volume_24h"].apply(fmt_usd)
        display["change_24h_%"]= display["change_24h_%"].apply(lambda x: f"{x:+.2f}%")
        st.dataframe(display, use_container_width=True, hide_index=True)

# TAB 2 — WALLET
with tab2:

    if df_txs is not None and not df_txs.empty:

        # Wallet summary metrics 
        total_txs    = len(df_txs)
        total_eth    = df_txs["value_eth"].sum() if "value_eth" in df_txs.columns else 0
        sent         = df_txs[df_txs["from"].str.lower() == wallet.lower()] if "from" in df_txs.columns else pd.DataFrame()
        received     = df_txs[df_txs["to"].str.lower()   == wallet.lower()] if "to"   in df_txs.columns else pd.DataFrame()

        c1, c2, c3, c4 = st.columns(4)
        for col, label, val in zip(
            [c1, c2, c3, c4],
            ["TRANSACTIONS", "TOTAL ETH MOVED", "SENT", "RECEIVED"],
            [str(total_txs), f"{total_eth:.4f} ETH", str(len(sent)), str(len(received))]
        ):
            with col:
                st.markdown(f"""
                <div class="metric-card">
                  <div class="metric-label">{label}</div>
                  <div class="metric-value" style="font-size:1.2rem">{val}</div>
                </div>
                """, unsafe_allow_html=True)

        # ETH value over time 
        if "block_time" in df_txs.columns and "value_eth" in df_txs.columns:
            st.markdown('<div class="section-header">ETH value per transaction</div>', unsafe_allow_html=True)
            plot_df = df_txs[df_txs["value_eth"] > 0].copy()
            if not plot_df.empty:
                fig4 = go.Figure()
                fig4.add_trace(go.Scatter(
                    x=plot_df["block_time"],
                    y=plot_df["value_eth"],
                    mode="markers",
                    marker=dict(
                        color=plot_df["value_eth"],
                        colorscale=[[0,"#1e2433"],[0.5,"#4299e1"],[1,"#48bb78"]],
                        size=7,
                        opacity=0.85,
                    ),
                    hovertemplate="%{y:.6f} ETH<br>%{x}<extra></extra>",
                ))
                fig4.update_layout(**PLOT_LAYOUT, height=260)
                fig4.update_yaxes(title_text="ETH")
                st.plotly_chart(fig4, use_container_width=True)

        # Tx count by day 
        if "block_time" in df_txs.columns:
            st.markdown('<div class="section-header">Transaction activity by day</div>', unsafe_allow_html=True)
            daily = df_txs.copy()
            daily["day"]  = daily["block_time"].dt.normalize()
            daily_counts  = daily.groupby("day").size().reset_index(name="tx_count")
            fig5 = go.Figure()
            fig5.add_trace(go.Bar(
                x=daily_counts["day"],
                y=daily_counts["tx_count"],
                marker_color="#805ad5",
                marker_opacity=0.8,
            ))
            fig5.update_layout(**PLOT_LAYOUT, height=200)
            st.plotly_chart(fig5, use_container_width=True)

        # Transaction table
        st.markdown('<div class="section-header">Recent transactions</div>', unsafe_allow_html=True)
        show_cols = [c for c in ["block_time","from","to","value_eth","gas_used"] if c in df_txs.columns]
        st.dataframe(df_txs[show_cols].head(20), use_container_width=True, hide_index=True)

    elif df_txs is not None and df_txs.empty:
        st.info("No transactions found for this address on Ethereum mainnet.")
    else:
        st.warning("Could not fetch wallet data. Check your Dune API key.")

# TAB 3 — RAW DATA
with tab3:
    st.markdown('<div class="section-header">Raw prices dataframe</div>', unsafe_allow_html=True)
    if df_prices is not None:
        st.dataframe(df_prices, use_container_width=True)

    st.markdown('<div class="section-header">Raw transactions dataframe</div>', unsafe_allow_html=True)
    if df_txs is not None and not df_txs.empty:
        st.dataframe(df_txs, use_container_width=True)