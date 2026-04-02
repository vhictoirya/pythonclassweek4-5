import streamlit as st
import requests
import pandas as pd
import time

API_KEY = "input your api key"
QUERY_ID = "6941518"

def run_query():
    r = requests.post(
        f"https://api.dune.com/api/v1/query/{QUERY_ID}/execute",
        headers={"x-dune-api-key": API_KEY}
    )
    exec_id = r.json()["execution_id"]

    with st.spinner("Running query on Dune..."):
        while True:
            res = requests.get(
                f"https://api.dune.com/api/v1/execution/{exec_id}/results",
                headers={"x-dune-api-key": API_KEY}
            )
            data = res.json()
            if data["state"] == "QUERY_STATE_COMPLETED":
                break
            time.sleep(2)

    return pd.DataFrame(data["result"]["rows"])

st.title("Ethereum DEX Volume")

if st.button("Run Query"):
    df = run_query()

    col1, col2, col3 = st.columns(3)
    col1.metric("Total Volume", f"${df['volume_usd'].sum():,.0f}")
    col2.metric("Total Trades", f"{df['trade_count'].sum():,.0f}")
    col3.metric("Unique Traders", f"{df['unique_traders'].sum():,.0f}")

    st.bar_chart(df.groupby("protocol")["volume_usd"].sum().sort_values(ascending=False))
    st.dataframe(df)