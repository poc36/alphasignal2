from __future__ import annotations

import os
from datetime import datetime

import pandas as pd
import plotly.express as px
import requests
import streamlit as st

try:
    import yfinance as yf
except Exception:
    yf = None


DEFAULT_API_CANDIDATES = [
    "http://127.0.0.1:8011",
    "http://127.0.0.1:18011",
    "http://127.0.0.1:8000",
    "http://localhost:8011",
    "http://localhost:18011",
    "http://localhost:8000",
]


def detect_api_base() -> str:
    for candidate in DEFAULT_API_CANDIDATES:
        if not candidate:
            continue
        candidate = candidate.strip().replace(" ", "")
        try:
            response = requests.get(f"{candidate}/admin/status", timeout=1.5)
            if response.ok:
                return candidate.rstrip("/")
        except Exception:
            continue
    return "http://127.0.0.1:18011"


API_BASE = detect_api_base()


def get_json(path: str, timeout: float = 10) -> dict:
    response = requests.get(f"{API_BASE}{path}", timeout=timeout)
    response.raise_for_status()
    return response.json()


def post_json(path: str, payload: dict | None = None, timeout: float = 15) -> dict:
    response = requests.post(f"{API_BASE}{path}", json=payload or {}, timeout=timeout)
    response.raise_for_status()
    return response.json()


def price_chart(symbol: str):
    if yf is None:
        return None
    try:
        history = yf.Ticker(symbol).history(period="1mo")
        if history.empty:
            return None
        history = history.reset_index()
        return px.line(history, x="Date", y="Close", title=f"{symbol} price history")
    except Exception:
        return None


st.set_page_config(page_title="AlphaSignal", layout="wide")
st.title("AlphaSignal")
st.caption("AI Trading Research Assistant")

try:
    health = get_json("/health")
    status = get_json("/admin/status")
    signals_payload = get_json("/api/signals")
    signals = signals_payload.get("signals", [])
    tickers = get_json("/tickers").get("tickers", [])
    articles = get_json("/admin/articles").get("articles", [])
except Exception as exc:
    st.error(f"Cannot reach AlphaSignal API at {API_BASE}: {exc}")
    st.info("Start the backend first or use the isolated backend on http://127.0.0.1:18011.")
    st.stop()

with st.sidebar:
    st.subheader("Operations")
    if st.button("Run ingestion now", use_container_width=True):
        try:
            result = post_json("/admin/ingest", timeout=20)
            st.success(f"Ingested RSS: {result['rss_articles']}, SEC: {result['sec_filings']}")
        except Exception as exc:
            st.warning(f"Ingestion request did not complete cleanly: {exc}")

    if st.button("Load demo signals", use_container_width=True):
        try:
            result = post_json("/admin/demo/load", timeout=10)
            st.success(f"Loaded {result['loaded']} demo signals")
        except Exception as exc:
            st.warning(f"Demo load failed: {exc}")

    scheduler_label = "Running" if status["scheduler_running"] else "Stopped"
    st.metric("Scheduler", scheduler_label)
    if status["scheduler_running"]:
        if st.button("Stop scheduler", use_container_width=True):
            try:
                post_json("/admin/scheduler/stop", timeout=10)
                st.rerun()
            except Exception as exc:
                st.warning(f"Scheduler stop failed: {exc}")
    else:
        if st.button("Start scheduler", use_container_width=True):
            try:
                post_json("/admin/scheduler/start", timeout=10)
                st.rerun()
            except Exception as exc:
                st.warning(f"Scheduler start failed: {exc}")

    st.metric("LLM", status["llm_provider"])
    st.caption(f"Model: {status['llm_model']}")
    if status.get("llm_last_error"):
        st.warning(status["llm_last_error"])
    st.caption(f"Last health check: {datetime.fromisoformat(health['timestamp']).strftime('%Y-%m-%d %H:%M:%S')}")

col1, col2, col3 = st.columns(3)
col1.metric("Signals", len(signals))
col2.metric("Tracked tickers", len(tickers))
col3.metric("Articles", len(articles))

tab_feed, tab_ticker, tab_chat, tab_ops = st.tabs(["Signal Feed", "Ticker Research", "Chat", "Operations"])

with tab_feed:
    st.subheader("Latest Signals")
    if signals:
        st.dataframe(pd.DataFrame(signals), use_container_width=True)
    else:
        st.info("No signals yet. Run ingestion or load demo signals.")

    st.subheader("Recently Ingested Articles")
    if articles:
        st.dataframe(pd.DataFrame(articles), use_container_width=True)
    else:
        st.info("No articles ingested yet.")

with tab_ticker:
    st.subheader("Ticker View")
    selected = st.selectbox("Select ticker", tickers or ["AAPL"])
    col_a, col_b = st.columns([1, 1])
    with col_a:
        if st.button("Generate fresh signal", use_container_width=True):
            try:
                generated = post_json("/api/signals/generate", {"ticker": selected}, timeout=20)
                st.success(f"Generated {generated['signal']} for {generated['ticker']}")
                st.rerun()
            except Exception as exc:
                st.warning(f"Signal generation failed: {exc}")
    with col_b:
        st.metric("30-day window", "Active")

    if selected:
        ticker_payload = get_json(f"/api/tickers/{selected}")
        latest = ticker_payload.get("latest_signal")
        if latest:
            st.markdown(f"**Latest signal:** `{latest['signal']}` with {latest['confidence']}% confidence")
            st.write(latest["summary"])
            if latest["sources"]:
                st.write("Sources:")
                for source in latest["sources"]:
                    st.markdown(f"- [{source}]({source})")
        else:
            st.info("No history for this ticker yet.")

        chart = price_chart(selected)
        if chart is not None:
            st.plotly_chart(chart, use_container_width=True)

        history = get_json(f"/api/history/{selected}?days=30&limit=100").get("signals", [])
        if history:
            st.dataframe(pd.DataFrame(history), use_container_width=True)

with tab_chat:
    st.subheader("Research Chat")
    chat_default = tickers[0] if tickers else "AAPL"
    query = st.text_input("Ask about a company or ticker", placeholder="What are the risks for Tesla in 2026?")
    chat_ticker = st.text_input("Ticker context (optional)", value=chat_default)
    if st.button("Ask AlphaSignal", use_container_width=False) and query:
        try:
            answer = post_json("/api/chat", {"query": query, "ticker": chat_ticker or None}, timeout=20)
            st.write(answer["answer"])
            st.caption(f"Confidence: {round(answer['confidence'] * 100)}%")
            if answer["sources"]:
                for source in answer["sources"]:
                    st.markdown(f"- [{source}]({source})")
        except Exception as exc:
            st.warning(f"Chat request failed: {exc}")

with tab_ops:
    st.subheader("System Status")
    st.json(status)
    st.subheader("Health")
    st.json(health)
