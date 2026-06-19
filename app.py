import streamlit as st
import yfinance as yf
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px
import numpy as np

# ── Page config ──────────────────────────────────────────────────────────────
st.set_page_config(page_title="Stock Valuation Dashboard", layout="wide", page_icon="📈")

st.markdown("""
<style>
  body { background-color: #0f1117; }
  .metric-card {
    background: #1e2130;
    border-radius: 12px;
    padding: 20px;
    text-align: center;
  }
</style>
""", unsafe_allow_html=True)


# ── Helper functions ──────────────────────────────────────────────────────────

def get_stock_data(ticker: str):
    stock = yf.Ticker(ticker)
    info = stock.info
    cashflow = stock.cashflow
    financials = stock.financials
    return stock, info, cashflow, financials


def run_dcf(free_cash_flows: list, growth_rate: float, discount_rate: float, terminal_growth: float = 0.03):
    last_fcf = free_cash_flows[-1]
    projected = []
    discounted = []

    for year in range(1, 6):
        fcf = last_fcf * (1 + growth_rate) ** year
        pv = fcf / (1 + discount_rate) ** year
        projected.append(fcf)
        discounted.append(pv)

    terminal_value = projected[-1] * (1 + terminal_growth) / (discount_rate - terminal_growth)
    terminal_pv = terminal_value / (1 + discount_rate) ** 5

    total_value = sum(discounted) + terminal_pv
    return total_value, projected, discounted


def get_intrinsic_price(total_value: float, shares_outstanding: float):
    return total_value / shares_outstanding if shares_outstanding else None


def valuation_signal(intrinsic: float, market: float):
    ratio = intrinsic / market
    if ratio > 1.15:
        return "🟢 Undervalued", "green"
    elif ratio < 0.85:
        return "🔴 Overvalued", "red"
    else:
        return "🟡 Fairly Valued", "orange"


# ── Sidebar ───────────────────────────────────────────────────────────────────

with st.sidebar:
    st.title("⚙️ Settings")
    ticker_input = st.text_input("Stock Ticker", value="AAPL").upper().strip()
    growth_rate = st.slider("Revenue Growth Rate (%)", min_value=1, max_value=20, value=7) / 100
    discount_rate = st.slider("Discount Rate (%)", min_value=5, max_value=15, value=9) / 100
    analyze = st.button("Analyze", use_container_width=True)
    st.markdown("---")
    st.caption("Data via Yahoo Finance · Built with Streamlit")


# ── Main ──────────────────────────────────────────────────────────────────────

st.title("📈 Stock Valuation Dashboard")
st.caption("Enter a ticker in the sidebar and click Analyze to run a DCF valuation.")

if analyze:
    with st.spinner(f"Fetching data for {ticker_input}..."):
        try:
            stock, info, cashflow, financials = get_stock_data(ticker_input)

            col1, col2 = st.columns([1, 4])
            with col1:
                logo = info.get("logo_url")
                if logo:
                    st.image(logo, width=80)
            with col2:
                st.subheader(info.get("longName", ticker_input))
                st.caption(f"{info.get('sector', '')} · {info.get('industry', '')}")

            st.markdown("---")

            try:
                fcf_row = cashflow.loc["Free Cash Flow"] if "Free Cash Flow" in cashflow.index else None
                if fcf_row is None:
                    op_cf = cashflow.loc["Operating Cash Flow"]
                    capex = cashflow.loc["Capital Expenditure"]
                    fcf_row = op_cf + capex
                fcf_values = [v for v in fcf_row.values if not np.isnan(v)][::-1]
            except Exception:
                st.error("⚠️ Could not extract Free Cash Flow data. Try AAPL, MSFT, or KO.")
                st.stop()

            if len(fcf_values) < 2:
                st.error("Not enough cash flow history. Try a different ticker.")
                st.stop()

            shares = info.get("sharesOutstanding", None)
            current_price = info.get("currentPrice", None)

            total_value, projected_fcf, discounted_fcf = run_dcf(fcf_values, growth_rate, discount_rate)
            intrinsic_price = get_intrinsic_price(total_value, shares) if shares else None

            st.subheader("Valuation Summary")
            m1, m2, m3, m4 = st.columns(4)

            with m1:
                st.metric("Current Price", f"${current_price:,.2f}" if current_price else "N/A")
            with m2:
                st.metric("Intrinsic Value (DCF)", f"${intrinsic_price:,.2f}" if intrinsic_price else "N/A")
            with m3:
                if intrinsic_price and current_price:
                    upside = ((intrinsic_price - current_price) / current_price) * 100
                    st.metric("Upside / Downside", f"{upside:+.1f}%")
            with m4:
                if intrinsic_price and current_price:
                    signal, color = valuation_signal(intrinsic_price, current_price)
                    st.metric("Signal", signal)

            st.markdown("---")

            st.subheader("Historical Financials")

            try:
                rev = financials.loc["Total Revenue"].values[::-1]
                net = financials.loc["Net Income"].values[::-1]
                years = [str(d.year) for d in financials.columns[::-1]]

                fig1 = go.Figure()
                fig1.add_bar(x=years, y=rev / 1e9, name="Revenue ($B)", marker_color="#4f8ef7")
                fig1.add_bar(x=years, y=net / 1e9, name="Net Income ($B)", marker_color="#00c9a7")
                fig1.update_layout(
                    title="Revenue vs Net Income",
                    barmode="group",
                    plot_bgcolor="#1e2130",
                    paper_bgcolor="#1e2130",
                    font_color="#ffffff",
                    yaxis_title="Billions USD"
                )
                st.plotly_chart(fig1, use_container_width=True)
            except Exception:
                st.warning("Could not render revenue chart.")

            fcf_years = [f"Year -{i}" for i in range(len(fcf_values) - 1, -1, -1)]
            fig2 = go.Figure()
            fig2.add_bar(x=fcf_years, y=[v / 1e9 for v in fcf_values], marker_color="#f7c948")
            fig2.update_layout(
                title="Historical Free Cash Flow",
                plot_bgcolor="#1e2130",
                paper_bgcolor="#1e2130",
                font_color="#ffffff",
                yaxis_title="Billions USD"
            )
            st.plotly_chart(fig2, use_container_width=True)

            st.subheader("DCF Projection (Next 5 Years)")
            proj_years = [f"Year {i+1}" for i in range(5)]
            fig3 = go.Figure()
            fig3.add_bar(x=proj_years, y=[v / 1e9 for v in projected_fcf], name="Projected FCF", marker_color="#4f8ef7")
            fig3.add_bar(x=proj_years, y=[v / 1e9 for v in discounted_fcf], name="Discounted FCF", marker_color="#00c9a7")
            fig3.update_layout(
                barmode="group",
                plot_bgcolor="#1e2130",
                paper_bgcolor="#1e2130",
                font_color="#ffffff",
                yaxis_title="Billions USD"
            )
            st.plotly_chart(fig3, use_container_width=True)

            if intrinsic_price:
                st.subheader("Sensitivity Analysis")
                st.caption("How intrinsic value per share changes with different growth & discount rate assumptions")

                growth_range = [0.03, 0.05, 0.07, 0.09, 0.11]
                discount_range = [0.07, 0.08, 0.09, 0.10, 0.11]

                table = {}
                for g in growth_range:
                    row = {}
                    for d in discount_range:
                        try:
                            tv, _, _ = run_dcf(fcf_values, g, d)
                            ip = get_intrinsic_price(tv, shares)
                            row[f"DR {int(d*100)}%"] = round(ip, 2) if ip else "-"
                        except Exception:
                            row[f"DR {int(d*100)}%"] = "-"
                    table[f"Growth {int(g*100)}%"] = row

                df_sensitivity = pd.DataFrame(table).T
                st.dataframe(df_sensitivity, use_container_width=True)

        except Exception as e:
            st.error(f"Something went wrong: {e}. Double-check the ticker and try again.")