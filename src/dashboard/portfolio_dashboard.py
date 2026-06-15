import streamlit as st
import pandas as pd
import psycopg2
from datetime import datetime
import os
from collections import defaultdict

# Page config
st.set_page_config(
    page_title="VOX Portfolio Dashboard",
    page_icon="🎯",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Colors
COLORS = {
    'bg': '#0B0E14',
    'bg_card': '#111318',
    'text': '#E2E8F0',
    'text_muted': '#64748B',
    'accent': '#3B82F6',
    'green': '#22C55E',
    'red': '#EF4444',
    'orange': '#F59E0B',
}

GRADE_COLORS = {
    'BUY': '#22C55E',
    'HOLD': '#F59E0B',
    'SELL': '#EF4444',
}

@st.cache_data(ttl=300)
def load_portfolio_data():
    """Load portfolio data from PostgreSQL"""
    # Use internal Railway database URL if available, otherwise fallback to external
    db_url = os.environ.get('DATABASE_URL')
    
    if db_url:
        # Parse the DATABASE_URL
        import urllib.parse
        parsed = urllib.parse.urlparse(db_url)
        conn = psycopg2.connect(
            host=parsed.hostname,
            port=parsed.port or 5432,
            database=parsed.path[1:],  # Remove leading slash
            user=parsed.username,
            password=parsed.password
        )
    else:
        # Fallback to external connection (for local development)
        conn = psycopg2.connect(
            host='acela.proxy.rlwy.net',
            port=35577,
            database='railway',
            user='postgres',
            password=os.environ['DB_PASSWORD']
        )
    
    cur = conn.cursor()
    
    # Get all broker positions
    cur.execute("""
        SELECT 
            broker,
            ticker,
            shares,
            live_price,
            live_value_usd,
            grade,
            council,
            sector,
            last_sync_at
        FROM broker_positions
        WHERE live_value_usd > 0
        ORDER BY broker, live_value_usd DESC
    """)
    
    data = []
    for row in cur.fetchall():
        data.append({
            'broker': row[0],
            'ticker': row[1],
            'shares': float(row[2]) if row[2] else 0,
            'price': float(row[3]) if row[3] else 0,
            'value_usd': float(row[4]) if row[4] else 0,
            'grade': row[5],
            'council': row[6],
            'sector': row[7],
            'last_sync': row[8]
        })
    
    conn.close()
    return data

def main():
    # Sidebar
    st.sidebar.title("🎯 VOX Dashboard")
    st.sidebar.markdown("---")
    
    page = st.sidebar.radio("Navigation", [
        "📊 Overview",
        "💼 Portfolio",
        "🏦 Brokers",
        "🎯 Rebalancing"
    ])
    
    # Load data
    data = load_portfolio_data()
    
    if not data:
        st.warning("No portfolio data found. Please run broker sync.")
        return
    
    df = pd.DataFrame(data)
    
    # Calculate metrics
    total_value = df['value_usd'].sum()
    total_positions = len(df)
    
    # Broker breakdown
    broker_data = df.groupby('broker').agg({
        'value_usd': 'sum',
        'ticker': 'count',
        'grade': 'mean'
    }).reset_index()
    broker_data.columns = ['Broker', 'Total USD', 'Positions', 'Avg Grade']
    
    # Council breakdown
    council_data = df.groupby('council').agg({
        'value_usd': 'sum',
        'ticker': 'count'
    }).reset_index()
    council_data.columns = ['Council', 'Total USD', 'Positions']
    
    if page == "📊 Overview":
        st.title("📊 Portfolio Overview")
        
        # Metrics
        col1, col2, col3, col4 = st.columns(4)
        with col1:
            st.metric("Total Value", f"${total_value:,.2f}")
        with col2:
            st.metric("Positions", f"{total_positions}")
        with col3:
            avg_grade = df['grade'].mean()
            st.metric("Avg Grade", f"{avg_grade:.1f}")
        with col4:
            hold_value = df[df['council'] == 'HOLD']['value_usd'].sum()
            st.metric("HOLD Value", f"${hold_value:,.2f}")
        
        st.markdown("---")
        
        # Broker breakdown
        st.subheader("🏦 Broker Breakdown")
        st.dataframe(broker_data.style.format({
            'Total USD': '${:,.2f}',
            'Avg Grade': '{:.1f}'
        }), use_container_width=True)
        
        # Council distribution
        st.subheader("🎯 Council Distribution")
        st.dataframe(council_data.style.format({
            'Total USD': '${:,.2f}'
        }), use_container_width=True)
        
    elif page == "💼 Portfolio":
        st.title("💼 Portfolio Positions")
        
        # Filter by broker
        brokers = ['All'] + sorted(df['broker'].unique().tolist())
        selected_broker = st.selectbox("Filter by Broker", brokers)
        
        if selected_broker != 'All':
            filtered_df = df[df['broker'] == selected_broker]
        else:
            filtered_df = df
        
        # Display positions
        st.dataframe(
            filtered_df[['broker', 'ticker', 'shares', 'price', 'value_usd', 'grade', 'council', 'sector']]
            .style.format({
                'shares': '{:.4f}',
                'price': '${:.2f}',
                'value_usd': '${:,.2f}',
                'grade': '{:.0f}'
            })
            .map(lambda x: f'color: {GRADE_COLORS.get(x, "white")}', subset=['council']),
            use_container_width=True
        )
        
    elif page == "🏦 Brokers":
        st.title("🏦 Broker Analysis")
        
        for broker in sorted(df['broker'].unique()):
            broker_df = df[df['broker'] == broker]
            broker_value = broker_df['value_usd'].sum()
            broker_positions = len(broker_df)
            avg_grade = broker_df['grade'].mean()
            
            with st.expander(f"{broker}: ${broker_value:,.2f} ({broker_positions} positions)"):
                st.dataframe(
                    broker_df[['ticker', 'shares', 'price', 'value_usd', 'grade', 'council']]
                    .style.format({
                        'shares': '{:.4f}',
                        'price': '${:.2f}',
                        'value_usd': '${:,.2f}',
                        'grade': '{:.0f}'
                    }),
                    use_container_width=True
                )
                
    elif page == "🎯 Rebalancing":
        st.title("🎯 Rebalancing Recommendations")
        
        # SELL recommendations
        sell_df = df[df['council'] == 'SELL'].sort_values('value_usd', ascending=False)
        if not sell_df.empty:
            st.subheader("✂️ SELL Recommendations")
            st.dataframe(
                sell_df[['broker', 'ticker', 'shares', 'value_usd', 'grade']]
                .style.format({
                    'shares': '{:.4f}',
                    'value_usd': '${:,.2f}',
                    'grade': '{:.0f}'
                }),
                use_container_width=True
            )
            st.metric("Total SELL Value", f"${sell_df['value_usd'].sum():,.2f}")
        
        # BUY recommendations
        buy_df = df[df['council'] == 'BUY'].sort_values('value_usd', ascending=False)
        if not buy_df.empty:
            st.subheader("➕ BUY Recommendations")
            st.dataframe(
                buy_df[['broker', 'ticker', 'shares', 'value_usd', 'grade']]
                .style.format({
                    'shares': '{:.4f}',
                    'value_usd': '${:,.2f}',
                    'grade': '{:.0f}'
                }),
                use_container_width=True
            )
            st.metric("Total BUY Value", f"${buy_df['value_usd'].sum():,.2f}")
        
        # HOLD recommendations
        hold_df = df[df['council'] == 'HOLD'].sort_values('value_usd', ascending=False)
        if not hold_df.empty:
            st.subheader("✅ HOLD Positions")
            strong_hold = hold_df[hold_df['grade'] >= 60]
            if not strong_hold.empty:
                st.markdown("**Strong HOLD (Grade 60+):**")
                st.dataframe(
                    strong_hold[['broker', 'ticker', 'shares', 'value_usd', 'grade']]
                    .head(10)
                    .style.format({
                        'shares': '{:.4f}',
                        'value_usd': '${:,.2f}',
                        'grade': '{:.0f}'
                    }),
                    use_container_width=True
                )

if __name__ == "__main__":
    main()
