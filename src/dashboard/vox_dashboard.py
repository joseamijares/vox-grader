import streamlit as st
import pandas as pd
from datetime import datetime
import sys
import os

# Add src path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from sync.vox_postgres_sync import get_client

# ═══════════════════════════════════════════════════════════════════════════════
# PAGE CONFIG
# ═══════════════════════════════════════════════════════════════════════════════
st.set_page_config(
    page_title="VOX Dashboard v12",
    page_icon="🎯",
    layout="wide",
    initial_sidebar_state="expanded"
)

# ═══════════════════════════════════════════════════════════════════════════════
# DESIGN SYSTEM — Dark Mode (Vercel/Railway inspired)
# ═══════════════════════════════════════════════════════════════════════════════
COLORS = {
    'bg': '#0B0E14',
    'bg_card': '#111318',
    'bg_hover': '#161B22',
    'border': '#1E2330',
    'border_hover': '#2A3042',
    'text': '#E2E8F0',
    'text_muted': '#64748B',
    'text_dim': '#475569',
    'accent': '#3B82F6',
    'accent_hover': '#2563EB',
    'green': '#22C55E',
    'green_dim': '#16A34A',
    'red': '#EF4444',
    'red_dim': '#DC2626',
    'orange': '#F59E0B',
    'yellow': '#EAB308',
    'purple': '#A855F7',
    'cyan': '#06B6D4',
}

GRADE_COLORS = {
    'STRONG_BUY': '#22C55E',
    'BUY': '#3B82F6',
    'HOLD': '#F59E0B',
    'SELL': '#EF4444',
    'STRONG_SELL': '#DC2626',
}

PAGE_ICONS = {
    'command': '📊',
    'portfolio': '💼',
    'watchlist': '👁️',
    'plays': '🎯',
    'alerts': '🔔',
    'brokers': '🏦',
    'analysis': '📈',
}

PAGE_LABELS = {
    'command': 'Command Center',
    'portfolio': 'Portfolio',
    'watchlist': 'Watchlist',
    'plays': 'Plays',
    'alerts': 'Alerts',
    'brokers': 'Brokers',
    'analysis': 'Analysis',
}

st.markdown(f"""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800&display=swap');
    
    * {{ font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif !important; }}
    
    .stApp {{
        background-color: {COLORS['bg']};
    }}
    
    /* ── Sidebar ── */
    .stSidebar {{
        background-color: {COLORS['bg_card']} !important;
        border-right: 1px solid {COLORS['border']};
    }}
    .stSidebar [data-testid="stVerticalBlock"] {{
        padding-top: 0 !important;
    }}
    
    /* ── Typography ── */
    h1 {{
        color: {COLORS['text']} !important;
        font-size: 24px !important;
        font-weight: 700 !important;
        letter-spacing: -0.02em !important;
        margin-bottom: 4px !important;
    }}
    h2 {{
        color: {COLORS['text']} !important;
        font-size: 18px !important;
        font-weight: 600 !important;
        letter-spacing: -0.01em !important;
        margin-top: 24px !important;
        margin-bottom: 12px !important;
    }}
    h3 {{
        color: {COLORS['text']} !important;
        font-size: 14px !important;
        font-weight: 600 !important;
        text-transform: uppercase;
        letter-spacing: 0.05em;
    }}
    p, .stMarkdown {{
        color: {COLORS['text_muted']};
    }}
    
    /* ── Cards ── */
    .vox-card {{
        background-color: {COLORS['bg_card']};
        border: 1px solid {COLORS['border']};
        border-radius: 12px;
        padding: 20px;
        transition: all 0.2s ease;
    }}
    .vox-card:hover {{
        border-color: {COLORS['border_hover']};
        transform: translateY(-1px);
    }}
    
    /* ── Metric Cards ── */
    .metric-card {{
        background: linear-gradient(135deg, {COLORS['bg_card']} 0%, {COLORS['bg_hover']} 100%);
        border: 1px solid {COLORS['border']};
        border-radius: 12px;
        padding: 20px;
    }}
    .metric-label {{
        color: {COLORS['text_muted']};
        font-size: 11px;
        font-weight: 500;
        text-transform: uppercase;
        letter-spacing: 0.08em;
        margin-bottom: 8px;
    }}
    .metric-value {{
        color: {COLORS['text']};
        font-size: 28px;
        font-weight: 700;
        letter-spacing: -0.02em;
    }}
    .metric-change {{
        font-size: 13px;
        font-weight: 500;
        margin-top: 4px;
    }}
    
    /* ── Grade Badges ── */
    .badge {{
        display: inline-flex;
        align-items: center;
        gap: 6px;
        padding: 4px 10px;
        border-radius: 6px;
        font-size: 11px;
        font-weight: 600;
        letter-spacing: 0.02em;
    }}
    .badge-strong-buy {{ background: rgba(34, 197, 94, 0.15); color: {COLORS['green']}; }}
    .badge-buy {{ background: rgba(59, 130, 246, 0.15); color: {COLORS['accent']}; }}
    .badge-hold {{ background: rgba(245, 158, 11, 0.15); color: {COLORS['orange']}; }}
    .badge-sell {{ background: rgba(239, 68, 68, 0.15); color: {COLORS['red']}; }}
    .badge-strong-sell {{ background: rgba(220, 38, 38, 0.15); color: {COLORS['red_dim']}; }}
    
    /* ── Tables ── */
    .stDataFrame {{
        background-color: {COLORS['bg_card']} !important;
        border: 1px solid {COLORS['border']};
        border-radius: 12px;
    }}
    .stDataFrame thead tr th {{
        background-color: {COLORS['bg_hover']} !important;
        color: {COLORS['text_muted']} !important;
        font-size: 11px !important;
        font-weight: 600 !important;
        text-transform: uppercase;
        letter-spacing: 0.05em;
        border-bottom: 1px solid {COLORS['border']} !important;
    }}
    .stDataFrame tbody tr td {{
        color: {COLORS['text']} !important;
        font-size: 13px !important;
        border-bottom: 1px solid {COLORS['border']} !important;
    }}
    .stDataFrame tbody tr:hover td {{
        background-color: {COLORS['bg_hover']} !important;
    }}
    
    /* ── Buttons ── */
    .stButton > button {{
        background-color: {COLORS['bg_card']};
        color: {COLORS['text']};
        border: 1px solid {COLORS['border']};
        border-radius: 8px;
        padding: 8px 16px;
        font-weight: 500;
        font-size: 13px;
        transition: all 0.2s ease;
    }}
    .stButton > button:hover {{
        background-color: {COLORS['bg_hover']};
        border-color: {COLORS['accent']};
        color: {COLORS['accent']};
    }}
    
    /* ── Primary Button ── */
    .stButton > button[kind="primary"] {{
        background-color: {COLORS['accent']};
        color: white;
        border: none;
    }}
    .stButton > button[kind="primary"]:hover {{
        background-color: {COLORS['accent_hover']};
        color: white;
    }}
    
    /* ── Navigation ── */
    .nav-item {{
        display: flex;
        align-items: center;
        gap: 12px;
        padding: 10px 14px;
        border-radius: 8px;
        color: {COLORS['text_muted']};
        font-size: 14px;
        font-weight: 500;
        cursor: pointer;
        transition: all 0.15s ease;
        margin-bottom: 2px;
    }}
    .nav-item:hover {{
        background-color: {COLORS['bg_hover']};
        color: {COLORS['text']};
    }}
    .nav-item.active {{
        background-color: rgba(59, 130, 246, 0.1);
        color: {COLORS['accent']};
    }}
    .nav-item .nav-icon {{
        font-size: 18px;
        width: 24px;
        text-align: center;
    }}
    
    /* ── Alerts ── */
    .alert-card {{
        background-color: {COLORS['bg_card']};
        border-left: 3px solid;
        border-radius: 0 8px 8px 0;
        padding: 14px 16px;
        margin-bottom: 8px;
    }}
    .alert-urgent {{ border-left-color: {COLORS['red']}; }}
    .alert-high {{ border-left-color: {COLORS['orange']}; }}
    .alert-medium {{ border-left-color: {COLORS['yellow']}; }}
    .alert-low {{ border-left-color: {COLORS['accent']}; }}
    
    /* ── Progress Bars ── */
    .progress-bar {{
        height: 6px;
        background-color: {COLORS['bg_hover']};
        border-radius: 3px;
        overflow: hidden;
    }}
    .progress-fill {{
        height: 100%;
        border-radius: 3px;
        transition: width 0.3s ease;
    }}
    
    /* ── Tabs ── */
    .stTabs [data-baseweb="tab-list"] {{
        gap: 0;
        background-color: {COLORS['bg_card']};
        border-radius: 8px;
        padding: 4px;
    }}
    .stTabs [data-baseweb="tab"] {{
        color: {COLORS['text_muted']};
        font-size: 13px;
        font-weight: 500;
        padding: 8px 16px;
        border-radius: 6px;
    }}
    .stTabs [aria-selected="true"] {{
        background-color: {COLORS['bg_hover']};
        color: {COLORS['text']};
    }}
    
    /* ── Scrollbar ── */
    ::-webkit-scrollbar {{ width: 6px; height: 6px; }}
    ::-webkit-scrollbar-track {{ background: {COLORS['bg']}; }}
    ::-webkit-scrollbar-thumb {{ background: {COLORS['border']}; border-radius: 3px; }}
    ::-webkit-scrollbar-thumb:hover {{ background: {COLORS['border_hover']}; }}
    
    /* ── Hide defaults ── */
    #MainMenu {{visibility: hidden;}}
    footer {{visibility: hidden;}}
    .stDeployButton {{display: none;}}
    header {{visibility: hidden;}}
    
    /* ── Divider ── */
    hr {{
        border: none;
        border-top: 1px solid {COLORS['border']};
        margin: 16px 0;
    }}
    
    /* ── Select / Input ── */
    .stSelectbox > div > div, .stTextInput > div > div {{
        background-color: {COLORS['bg_card']} !important;
        border: 1px solid {COLORS['border']} !important;
        border-radius: 8px !important;
        color: {COLORS['text']} !important;
    }}
    
    /* ── Slider ── */
    .stSlider > div > div > div {{
        background-color: {COLORS['accent']} !important;
    }}
    
    /* ═══════════════════════════════════════════════════════════════════ */
    /* MOBILE RESPONSIVE STYLES — Simplified v12.3                        */
    /* ═══════════════════════════════════════════════════════════════════ */
    
    /* ── Mobile Header ── */
    .mobile-header {{
        display: none;
    }}
    
    /* ── Mobile Radio Nav Styling ── */
    .stRadio > div {{
        display: flex;
        flex-wrap: nowrap;
        gap: 0;
        background-color: {COLORS['bg_card']};
        border: 1px solid {COLORS['border']};
        border-radius: 10px;
        padding: 4px;
        overflow-x: auto;
    }}
    .stRadio > div > label {{
        flex: 1;
        min-width: 0;
        text-align: center;
        padding: 8px 4px;
        border-radius: 6px;
        font-size: 12px;
        font-weight: 500;
        color: {COLORS['text_muted']};
        cursor: pointer;
        transition: all 0.15s ease;
        white-space: nowrap;
        overflow: hidden;
        text-overflow: ellipsis;
    }}
    .stRadio > div > label:hover {{
        background-color: {COLORS['bg_hover']};
        color: {COLORS['text']};
    }}
    .stRadio > div > label[data-baseweb="radio"] > div:first-child {{
        display: none !important;
    }}
    .stRadio > div > label[data-baseweb="radio"] > div:last-child {{
        margin-left: 0 !important;
    }}
    
    /* ═══════════════════════════════════════════════════════════════════ */
    /* MOBILE BREAKPOINT (max-width: 768px)                              */
    /* ═══════════════════════════════════════════════════════════════════ */
    @media screen and (max-width: 768px) {{
        /* Hide desktop sidebar completely */
        .stSidebar,
        .stSidebarNav,
        [data-testid="stSidebar"] {{
            display: none !important;
            width: 0 !important;
            min-width: 0 !important;
            max-width: 0 !important;
        }}
        
        /* Hide the sidebar collapse button */
        button[kind="header"] {{
            display: none !important;
        }}
        
        /* Expand main content to full width */
        .main .block-container {{
            padding-left: 12px !important;
            padding-right: 12px !important;
            padding-top: 12px !important;
            max-width: 100% !important;
        }}
        
        /* Stack all columns vertically */
        [data-testid="stHorizontalBlock"] {{
            flex-direction: column !important;
            gap: 12px !important;
        }}
        [data-testid="column"] {{
            width: 100% !important;
            flex: 1 1 100% !important;
            min-width: auto !important;
            max-width: 100% !important;
        }}
        
        /* Smaller metric cards */
        .metric-value {{
            font-size: 20px !important;
        }}
        
        /* Touch-friendly buttons */
        .stButton > button {{
            min-height: 44px;
            font-size: 14px;
        }}
        
        /* Compact tables */
        .stDataFrame tbody tr td {{
            font-size: 11px !important;
            padding: 6px 8px !important;
        }}
        .stDataFrame thead tr th {{
            font-size: 10px !important;
            padding: 6px 8px !important;
        }}
        
        /* Compact alerts */
        .alert-card {{
            padding: 10px;
        }}
        
        /* Mobile radio nav - full width sticky */
        .stRadio > div {{
            position: sticky;
            top: 0;
            z-index: 100;
            background-color: {COLORS['bg_card']};
            backdrop-filter: blur(20px);
            -webkit-backdrop-filter: blur(20px);
            margin: 0 -12px;
            border-radius: 0;
            border-left: none;
            border-right: none;
            border-top: none;
        }}
    }}
    
    /* ═══════════════════════════════════════════════════════════════════ */
    /* TABLET BREAKPOINT (max-width: 1024px)                             */
    /* ═══════════════════════════════════════════════════════════════════ */
    @media screen and (max-width: 1024px) and (min-width: 769px) {{
        .stSidebar {{
            min-width: 220px !important;
            max-width: 220px !important;
        }}
        
        .metric-value {{
            font-size: 24px !important;
        }}
    }}
    
    /* ── Safe area for notched phones ── */
    @supports (padding-bottom: env(safe-area-inset-bottom)) {{
        .main .block-container {{
            padding-bottom: max(24px, env(safe-area-inset-bottom)) !important;
        }}
    }}
</style>
""", unsafe_allow_html=True)

# ═══════════════════════════════════════════════════════════════════════════════
# MOBILE HEADER (visible on mobile only via CSS)
# ═══════════════════════════════════════════════════════════════════════════════
def render_mobile_nav_native(current_page):
    """Render mobile navigation using ONLY native Streamlit components.
    
    This replaces the broken custom HTML/JS mobile nav with a reliable
    Streamlit-native approach that works on all devices.
    """
    # Mobile header with logo
    st.markdown(f"""
    <div style="display: flex; align-items: center; justify-content: space-between; padding: 12px 0; margin-bottom: 8px;">
        <div style="display: flex; align-items: center; gap: 10px;">
            <div style="width: 32px; height: 32px; background: linear-gradient(135deg, {COLORS['accent']}, {COLORS['purple']}); border-radius: 8px; display: flex; align-items: center; justify-content: center; font-size: 16px;">🎯</div>
            <div>
                <div style="color: {COLORS['text']}; font-size: 18px; font-weight: 700;">VOX</div>
                <div style="color: {COLORS['text_dim']}; font-size: 11px;">v12.3 Mobile</div>
            </div>
        </div>
        <div style="color: {COLORS['accent']}; font-size: 13px; font-weight: 600;">
            {PAGE_ICONS.get(current_page, '📊')} {PAGE_LABELS.get(current_page, 'Dashboard')}
        </div>
    </div>
    """, unsafe_allow_html=True)
    
    # Native Streamlit segmented control for page switching
    # Use columns for a tab-bar-like experience
    bottom_items = ['command', 'portfolio', 'watchlist', 'plays', 'alerts']
    
    # Create a radio that looks like tabs
    page_options = [f"{PAGE_ICONS.get(k, '•')} {PAGE_LABELS.get(k, k)}" for k in bottom_items]
    current_idx = bottom_items.index(current_page) if current_page in bottom_items else 0
    
    selected = st.radio(
        "Navigation",
        options=page_options,
        index=current_idx,
        horizontal=True,
        label_visibility="collapsed",
        key="mobile_nav_radio"
    )
    
    # Extract the page key from selection
    selected_page = None
    for key in bottom_items:
        if PAGE_LABELS.get(key, key) in selected:
            selected_page = key
            break
    
    if selected_page and selected_page != current_page:
        st.session_state.page = selected_page
        st.query_params['page'] = selected_page
        st.rerun()
    
    # Divider
    st.markdown(f"<hr style='border-color: {COLORS['border']}; margin: 12px 0;'>", unsafe_allow_html=True)

# ═══════════════════════════════════════════════════════════════════════════════
# INITIALIZE SUPABASE
# ═══════════════════════════════════════════════════════════════════════════════
sb = get_client()

# ═══════════════════════════════════════════════════════════════════════════════
# DATA LOADING
# ═══════════════════════════════════════════════════════════════════════════════
@st.cache_data(ttl=60)
def load_positions():
    try:
        response = sb.table("positions").select("*").order("live_value", desc=True).execute()
        return response.data or []
    except Exception as e:
        st.error(f"Error loading positions: {e}")
        return []

@st.cache_data(ttl=300)
def load_watchlist():
    try:
        response = sb.table("watchlist").select("*").execute()
        return response.data or []
    except:
        return []

@st.cache_data(ttl=300)
def load_plays():
    try:
        response = sb.table("plays").select("*").order("id", desc=True).execute()
        return response.data or []
    except:
        return []

@st.cache_data(ttl=300)
def load_alerts():
    try:
        response = sb.table("alerts").select("*").order("id", desc=True).execute()
        return response.data or []
    except:
        return []

positions = load_positions()
watchlist = load_watchlist()
plays = load_plays()
alerts = load_alerts()

df = pd.DataFrame(positions)
if not df.empty:
    df['live_value'] = df['live_value'].fillna(0)
    df['grade'] = df['grade'].fillna(0)

# ═══════════════════════════════════════════════════════════════════════════════
# HELPER FUNCTIONS
# ═══════════════════════════════════════════════════════════════════════════════
def grade_color(grade):
    if grade >= 75: return COLORS['green']
    elif grade >= 60: return COLORS['accent']
    elif grade >= 50: return COLORS['orange']
    elif grade >= 30: return COLORS['red']
    else: return COLORS['red_dim']

def grade_label(grade):
    if grade >= 75: return "STRONG_BUY"
    elif grade >= 60: return "BUY"
    elif grade >= 50: return "HOLD"
    elif grade >= 30: return "SELL"
    else: return "STRONG_SELL"

def grade_badge_html(grade, council=None):
    label = council or grade_label(grade)
    color = grade_color(grade)
    css_class = label.lower().replace('_', '-')
    return f"<span class='badge badge-{css_class}'>{grade:.0f} {label}</span>"

def format_currency(value):
    if value >= 1_000_000:
        return f"${value/1_000_000:.2f}M"
    elif value >= 1_000:
        return f"${value:,.0f}"
    return f"${value:.2f}"

# ═══════════════════════════════════════════════════════════════════════════════
# SESSION STATE & NAVIGATION
# ═══════════════════════════════════════════════════════════════════════════════
if 'page' not in st.session_state:
    st.session_state.page = 'command'

# Check for URL hash navigation
query_params = st.query_params
if 'page' in query_params:
    page_from_url = query_params['page']
    if page_from_url in PAGE_LABELS:
        st.session_state.page = page_from_url

page = st.session_state.page

# ═══════════════════════════════════════════════════════════════════════════════
# MOBILE UI RENDERING — Native Streamlit (reliable on all devices)
# ═══════════════════════════════════════════════════════════════════════════════
render_mobile_nav_native(page)

# ═══════════════════════════════════════════════════════════════════════════════
# DESKTOP SIDEBAR NAVIGATION
# ═══════════════════════════════════════════════════════════════════════════════
with st.sidebar:
    # Logo
    st.markdown(f"""
    <div style='padding: 20px 0 16px 0;'>
        <div style='display: flex; align-items: center; gap: 10px;'>
            <div style='width: 32px; height: 32px; background: linear-gradient(135deg, {COLORS["accent"]}, {COLORS["purple"]}); border-radius: 8px; display: flex; align-items: center; justify-content: center; font-size: 16px;'>🎯</div>
            <div>
                <div style='color: {COLORS["text"]}; font-size: 18px; font-weight: 700; letter-spacing: -0.02em;'>VOX</div>
                <div style='color: {COLORS["text_dim"]}; font-size: 11px; font-weight: 500;'>v12.0 Python</div>
            </div>
        </div>
    </div>
    """, unsafe_allow_html=True)
    
    st.markdown(f"<hr style='border-color: {COLORS['border']}; margin: 0 0 12px 0;'>", unsafe_allow_html=True)
    
    # Navigation buttons
    for key, label in PAGE_LABELS.items():
        icon = PAGE_ICONS.get(key, "•")
        btn_type = "primary" if page == key else "secondary"
        if st.sidebar.button(f"{icon}  {label}", key=f"nav_btn_{key}", use_container_width=True, type=btn_type):
            st.session_state.page = key
            st.query_params['page'] = key
            st.rerun()
    
    st.markdown(f"<hr style='border-color: {COLORS['border']}; margin: 16px 0;'>", unsafe_allow_html=True)
    
    # Portfolio summary in sidebar
    if not df.empty:
        total_value = df['live_value'].sum()
        st.markdown(f"""
        <div style='padding: 0 4px;'>
            <div style='color: {COLORS["text_dim"]}; font-size: 10px; font-weight: 600; text-transform: uppercase; letter-spacing: 0.08em; margin-bottom: 4px;'>Portfolio Value</div>
            <div style='color: {COLORS["text"]}; font-size: 20px; font-weight: 700; letter-spacing: -0.02em;'>{format_currency(total_value)}</div>
            <div style='color: {COLORS["text_muted"]}; font-size: 11px; margin-top: 2px;'>{len(df)} positions</div>
        </div>
        """, unsafe_allow_html=True)
    
    st.markdown(f"<hr style='border-color: {COLORS['border']}; margin: 16px 0;'>", unsafe_allow_html=True)
    
    st.markdown(f"""
    <div style='padding: 0 4px;'>
        <div style='color: {COLORS["text_dim"]}; font-size: 10px; font-weight: 500;'>© 2026 VOX Systems</div>
        <div style='color: {COLORS["text_dim"]}; font-size: 10px;'>Last sync: {datetime.now().strftime('%H:%M')}</div>
    </div>
    """, unsafe_allow_html=True)

# ═══════════════════════════════════════════════════════════════════════════════
# COMMAND CENTER PAGE
# ═══════════════════════════════════════════════════════════════════════════════
if page == "command":
    st.title("Command Center")
    st.caption(f"Live from Supabase • {datetime.now().strftime('%B %d, %Y at %H:%M')}")
    
    if df.empty:
        st.warning("No positions found. Run broker sync.")
    else:
        total_value = df['live_value'].sum()
        total_positions = len(df)
        avg_grade = df[df['grade'] > 0]['grade'].mean() if not df.empty else 0
        strong_buy_count = len(df[df['grade'] >= 75])
        sell_count = len(df[df['grade'] < 50])
        
        # ── KPI Row ──
        cols = st.columns(4)
        metrics = [
            ("Portfolio Value", format_currency(total_value), None),
            ("Positions", f"{total_positions}", None),
            ("Avg Grade", f"{avg_grade:.1f}", f"{strong_buy_count} STRONG_BUY"),
            ("Risk Alerts", f"{sell_count}", "SELL signals" if sell_count > 0 else "Clean"),
        ]
        for col, (label, value, sub) in zip(cols, metrics):
            with col:
                st.markdown(f"""
                <div class='metric-card'>
                    <div class='metric-label'>{label}</div>
                    <div class='metric-value'>{value}</div>
                    {f'<div class="metric-change" style="color: {COLORS["text_muted"]}">{sub}</div>' if sub else ''}
                </div>
                """, unsafe_allow_html=True)
        
        # ── Alerts Section ──
        st.markdown("<div style='margin-top: 24px;'></div>", unsafe_allow_html=True)
        
        col_left, col_right = st.columns([3, 2])
        
        with col_left:
            st.subheader("🚨 Active Alerts")
            
            if alerts:
                alert_df = pd.DataFrame(alerts)
                urgent = alert_df[alert_df['priority'] == 'URGENT'] if 'priority' in alert_df.columns else pd.DataFrame()
                high = alert_df[alert_df['priority'] == 'HIGH'] if 'priority' in alert_df.columns else pd.DataFrame()
                
                if not urgent.empty:
                    for _, row in urgent.head(3).iterrows():
                        st.markdown(f"""
                        <div class='alert-card alert-urgent'>
                            <div style='display: flex; justify-content: space-between; align-items: center;'>
                                <div>
                                    <span style='color: {COLORS['red']}; font-size: 11px; font-weight: 600; text-transform: uppercase;'>{row.get('priority', 'URGENT')}</span>
                                    <div style='color: {COLORS['text']}; font-size: 14px; font-weight: 600; margin-top: 2px;'>{row.get('ticker', '')}</div>
                                    <div style='color: {COLORS['text_muted']}; font-size: 12px; margin-top: 2px;'>{row.get('message', '')[:80]}...</div>
                                </div>
                            </div>
                        </div>
                        """, unsafe_allow_html=True)
                
                if not high.empty:
                    for _, row in high.head(3).iterrows():
                        st.markdown(f"""
                        <div class='alert-card alert-high'>
                            <div style='display: flex; justify-content: space-between; align-items: center;'>
                                <div>
                                    <span style='color: {COLORS['orange']}; font-size: 11px; font-weight: 600; text-transform: uppercase;'>{row.get('priority', 'HIGH')}</span>
                                    <div style='color: {COLORS['text']}; font-size: 14px; font-weight: 600; margin-top: 2px;'>{row.get('ticker', '')}</div>
                                    <div style='color: {COLORS['text_muted']}; font-size: 12px; margin-top: 2px;'>{row.get('message', '')[:80]}...</div>
                                </div>
                            </div>
                        </div>
                        """, unsafe_allow_html=True)
            else:
                st.info("No active alerts")
            
            # ── Top Holdings ──
            st.subheader("🏆 Top Holdings")
            top10 = df.nlargest(10, 'live_value')[['ticker', 'live_value', 'grade', 'council']].copy()
            
            display_data = []
            for _, row in top10.iterrows():
                display_data.append({
                    'Ticker': row['ticker'],
                    'Value': format_currency(row['live_value']),
                    'Grade': row['grade'],
                    'Signal': grade_label(row['grade']),
                })
            
            top10_df = pd.DataFrame(display_data)
            st.dataframe(
                top10_df,
                column_config={
                    'Ticker': st.column_config.TextColumn("Ticker", width="small"),
                    'Value': st.column_config.TextColumn("Value", width="medium"),
                    'Grade': st.column_config.ProgressColumn("Grade", min_value=0, max_value=100, width="medium", format="%d"),
                    'Signal': st.column_config.TextColumn("Signal", width="small"),
                },
                hide_index=True,
                use_container_width=True
            )
        
        with col_right:
            # ── Grade Distribution ──
            st.subheader("📊 Grade Distribution")
            
            grade_buckets = {
                'STRONG_BUY': len(df[df['grade'] >= 75]),
                'BUY': len(df[(df['grade'] >= 60) & (df['grade'] < 75)]),
                'HOLD': len(df[(df['grade'] >= 50) & (df['grade'] < 60)]),
                'SELL': len(df[(df['grade'] >= 30) & (df['grade'] < 50)]),
                'STRONG_SELL': len(df[df['grade'] < 30]),
            }
            
            for label, count in grade_buckets.items():
                color = GRADE_COLORS.get(label, COLORS['text_muted'])
                total = sum(grade_buckets.values())
                pct = (count / total * 100) if total > 0 else 0
                st.markdown(f"""
                <div style='margin-bottom: 10px;'>
                    <div style='display: flex; justify-content: space-between; margin-bottom: 4px;'>
                        <span style='color: {color}; font-size: 12px; font-weight: 600;'>{label}</span>
                        <span style='color: {COLORS['text_muted']}; font-size: 12px;'>{count} ({pct:.0f}%)</span>
                    </div>
                    <div class='progress-bar'>
                        <div class='progress-fill' style='width: {pct}%; background-color: {color};'></div>
                    </div>
                </div>
                """, unsafe_allow_html=True)
            
            # ── By Broker ──
            st.subheader("🏦 By Broker")
            if 'brokers' in df.columns:
                broker_data = []
                for _, row in df.iterrows():
                    brokers = row['brokers']
                    if isinstance(brokers, list):
                        for broker in brokers:
                            broker_data.append({'broker': broker, 'value': row['live_value']})
                    elif isinstance(brokers, str):
                        broker_data.append({'broker': brokers, 'value': row['live_value']})
                
                if broker_data:
                    broker_df = pd.DataFrame(broker_data).groupby('broker')['value'].sum().reset_index()
                    broker_df = broker_df.sort_values('value', ascending=False)
                    
                    for _, row in broker_df.iterrows():
                        pct = row['value'] / total_value * 100
                        st.markdown(f"""
                        <div style='display: flex; justify-content: space-between; align-items: center; padding: 8px 0; border-bottom: 1px solid {COLORS["border"]};'>
                            <span style='color: {COLORS["text"]}; font-size: 13px; font-weight: 500;'>{row['broker']}</span>
                            <div style='text-align: right;'>
                                <div style='color: {COLORS["text"]}; font-size: 13px; font-weight: 600;'>{format_currency(row['value'])}</div>
                                <div style='color: {COLORS["text_muted"]}; font-size: 11px;'>{pct:.1f}%</div>
                            </div>
                        </div>
                        """, unsafe_allow_html=True)

# ═══════════════════════════════════════════════════════════════════════════════
# PORTFOLIO PAGE
# ═══════════════════════════════════════════════════════════════════════════════
elif page == "portfolio":
    st.title("Portfolio")
    
    if df.empty:
        st.warning("No positions found")
    else:
        # Summary bar
        total_value = df['live_value'].sum()
        cols = st.columns(4)
        with cols[0]:
            st.metric("Total Value", format_currency(total_value))
        with cols[1]:
            st.metric("Positions", len(df))
        with cols[2]:
            avg_grade = df[df['grade'] > 0]['grade'].mean()
            st.metric("Avg Grade", f"{avg_grade:.1f}")
        with cols[3]:
            sell_count = len(df[df['grade'] < 50])
            st.metric("SELL Signals", sell_count, delta="Trim" if sell_count > 5 else None)
        
        # Filters
        st.markdown("<div style='margin-top: 16px;'></div>", unsafe_allow_html=True)
        
        col1, col2, col3 = st.columns(3)
        with col1:
            min_grade = st.slider("Min Grade", 0, 100, 0)
        with col2:
            signal_filter = st.multiselect("Signal", 
                options=['STRONG_BUY', 'BUY', 'HOLD', 'SELL', 'STRONG_SELL'],
                default=[])
        with col3:
            search = st.text_input("Search Ticker", placeholder="e.g. NVDA")
        
        # Filter
        filtered = df.copy()
        if min_grade > 0:
            filtered = filtered[filtered['grade'] >= min_grade]
        if signal_filter:
            filtered = filtered[filtered['grade'].apply(lambda g: grade_label(g) in signal_filter)]
        if search:
            filtered = filtered[filtered['ticker'].str.contains(search.upper(), na=False)]
        
        # Display
        display_cols = ['ticker', 'shares', 'live_price', 'live_value', 'grade', 'council']
        display_df = filtered[display_cols].copy()
        display_df['Signal'] = display_df['grade'].apply(grade_label)
        display_df = display_df.sort_values('live_value', ascending=False)
        
        st.dataframe(
            display_df,
            column_config={
                'ticker': st.column_config.TextColumn("Ticker", width="small"),
                'shares': st.column_config.NumberColumn("Shares", format="%.4f", width="small"),
                'live_price': st.column_config.NumberColumn("Price", format="$%.2f", width="small"),
                'live_value': st.column_config.NumberColumn("Value", format="$%.2f", width="medium"),
                'grade': st.column_config.ProgressColumn("Grade", min_value=0, max_value=100, width="medium"),
                'Signal': st.column_config.TextColumn("Signal", width="small"),
                'council': st.column_config.TextColumn("Council", width="small"),
            },
            hide_index=True,
            use_container_width=True
        )

# ═══════════════════════════════════════════════════════════════════════════════
# WATCHLIST PAGE
# ═══════════════════════════════════════════════════════════════════════════════
elif page == "watchlist":
    st.title("Watchlist")
    
    if watchlist:
        wl_df = pd.DataFrame(watchlist)
        
        # Summary
        total = len(wl_df)
        strong_buy = len(wl_df[wl_df['grade'] >= 75]) if 'grade' in wl_df.columns else 0
        buy = len(wl_df[(wl_df['grade'] >= 60) & (wl_df['grade'] < 75)]) if 'grade' in wl_df.columns else 0
        
        cols = st.columns(4)
        with cols[0]:
            st.metric("Total Tickers", total)
        with cols[1]:
            st.metric("STRONG_BUY", strong_buy)
        with cols[2]:
            st.metric("BUY", buy)
        with cols[3]:
            st.metric("HOLD", total - strong_buy - buy)
        
        # Filters
        col1, col2 = st.columns(2)
        with col1:
            min_grade_wl = st.slider("Min Grade", 0, 100, 50, key="wl_grade")
        with col2:
            search_wl = st.text_input("Search", placeholder="Ticker or name...", key="wl_search")
        
        # Filter
        filtered_wl = wl_df.copy()
        if 'grade' in filtered_wl.columns and min_grade_wl > 0:
            filtered_wl = filtered_wl[filtered_wl['grade'] >= min_grade_wl]
        if search_wl:
            mask = filtered_wl['ticker'].str.contains(search_wl.upper(), na=False)
            if 'name' in filtered_wl.columns:
                mask = mask | filtered_wl['name'].str.contains(search_wl, case=False, na=False)
            filtered_wl = filtered_wl[mask]
        
        # Sort by grade desc
        if 'grade' in filtered_wl.columns:
            filtered_wl = filtered_wl.sort_values('grade', ascending=False)
        
        # Display columns
        display_cols = ['ticker', 'name', 'grade', 'council', 'entry_price', 'target_price', 'stop_loss']
        available_cols = [c for c in display_cols if c in filtered_wl.columns]
        
        st.dataframe(
            filtered_wl[available_cols],
            column_config={
                'ticker': st.column_config.TextColumn("Ticker", width="small"),
                'name': st.column_config.TextColumn("Name", width="medium"),
                'grade': st.column_config.ProgressColumn("Grade", min_value=0, max_value=100, width="small"),
                'council': st.column_config.TextColumn("Council", width="small"),
                'entry_price': st.column_config.NumberColumn("Entry", format="$%.2f", width="small"),
                'target_price': st.column_config.NumberColumn("Target", format="$%.2f", width="small"),
                'stop_loss': st.column_config.NumberColumn("Stop", format="$%.2f", width="small"),
            },
            hide_index=True,
            use_container_width=True
        )
    else:
        st.info("No watchlist items")

# ═══════════════════════════════════════════════════════════════════════════════
# PLAYS PAGE
# ═══════════════════════════════════════════════════════════════════════════════
elif page == "plays":
    st.title("Active Plays")
    
    if plays:
        plays_df = pd.DataFrame(plays)
        
        # Summary
        active = plays_df[plays_df['closed'] == False] if 'closed' in plays_df.columns else plays_df
        total_notional = active['notional'].sum() if 'notional' in active.columns else 0
        
        cols = st.columns(3)
        with cols[0]:
            st.metric("Active Plays", len(active))
        with cols[1]:
            st.metric("Total Notional", format_currency(total_notional))
        with cols[2]:
            buy_count = len(active[active['action'] == 'BUY']) if 'action' in active.columns else 0
            st.metric("BUY Orders", buy_count)
        
        # Tabs for active / closed
        tab_active, tab_closed = st.tabs(["🟢 Active", "⚪ Closed"])
        
        with tab_active:
            active_df = active.copy()
            if 'timestamp' in active_df.columns:
                active_df = active_df.sort_values('timestamp', ascending=False)
            
            display_cols = ['ticker', 'action', 'shares', 'price', 'notional', 'grade_at_entry', 'notes']
            available_cols = [c for c in display_cols if c in active_df.columns]
            
            st.dataframe(
                active_df[available_cols],
                column_config={
                    'ticker': st.column_config.TextColumn("Ticker", width="small"),
                    'action': st.column_config.TextColumn("Action", width="small"),
                    'shares': st.column_config.NumberColumn("Shares", format="%.0f", width="small"),
                    'price': st.column_config.NumberColumn("Price", format="$%.2f", width="small"),
                    'notional': st.column_config.NumberColumn("Notional", format="$%.0f", width="small"),
                    'grade_at_entry': st.column_config.NumberColumn("Grade", width="small"),
                    'notes': st.column_config.TextColumn("Notes", width="large"),
                },
                hide_index=True,
                use_container_width=True
            )
        
        with tab_closed:
            if 'closed' in plays_df.columns:
                closed_df = plays_df[plays_df['closed'] == True]
                if not closed_df.empty:
                    st.dataframe(closed_df[['ticker', 'action', 'notional', 'exit_price', 'pnl', 'pnl_pct']],
                        hide_index=True, use_container_width=True)
                else:
                    st.info("No closed plays")
            else:
                st.info("No closed plays")
    else:
        st.info("No active plays")

# ═══════════════════════════════════════════════════════════════════════════════
# ALERTS PAGE
# ═══════════════════════════════════════════════════════════════════════════════
elif page == "alerts":
    st.title("Alerts")
    
    if alerts:
        alerts_df = pd.DataFrame(alerts)
        
        # Priority filter
        if 'priority' in alerts_df.columns:
            priorities = alerts_df['priority'].unique().tolist()
            selected = st.multiselect("Filter by Priority", options=priorities, default=priorities)
            if selected:
                alerts_df = alerts_df[alerts_df['priority'].isin(selected)]
        
        # Sort by timestamp desc
        if 'timestamp' in alerts_df.columns:
            alerts_df = alerts_df.sort_values('timestamp', ascending=False)
        
        for _, row in alerts_df.head(20).iterrows():
            priority = row.get('priority', 'MEDIUM')
            alert_class = {
                'URGENT': 'alert-urgent',
                'HIGH': 'alert-high',
                'MEDIUM': 'alert-medium',
                'LOW': 'alert-low',
            }.get(priority, 'alert-medium')
            
            color = {
                'URGENT': COLORS['red'],
                'HIGH': COLORS['orange'],
                'MEDIUM': COLORS['yellow'],
                'LOW': COLORS['accent'],
            }.get(priority, COLORS['accent'])
            
            st.markdown(f"""
            <div class='alert-card {alert_class}'>
                <div style='display: flex; justify-content: space-between; align-items: flex-start;'>
                    <div>
                        <div style='display: flex; align-items: center; gap: 8px; margin-bottom: 4px;'>
                            <span style='color: {color}; font-size: 10px; font-weight: 700; text-transform: uppercase; letter-spacing: 0.08em;'>{priority}</span>
                            <span style='color: {COLORS['text']}; font-size: 14px; font-weight: 700;'>{row.get('ticker', '')}</span>
                            <span style='color: {COLORS['text_dim']}; font-size: 11px;'>{row.get('alert_type', '')}</span>
                        </div>
                        <div style='color: {COLORS['text_muted']}; font-size: 13px; line-height: 1.5;'>{row.get('message', '')}</div>
                    </div>
                </div>
            </div>
            """, unsafe_allow_html=True)
    else:
        st.info("No active alerts")

# ═══════════════════════════════════════════════════════════════════════════════
# BROKERS PAGE
# ═══════════════════════════════════════════════════════════════════════════════
elif page == "brokers":
    st.title("Broker Sync")
    
    brokers_config = [
        ("eToro", "etoro_sync.py", "Live API"),
        ("Binance", "binance_sync.py", "Live API"),
        ("GBM Main", "gbm_sync.py", "JSON Export"),
        ("GBM USA", "gbm_sync.py", "JSON Export"),
        ("IBKR", "remaining_sync.py", "JSON Export"),
        ("Schwab", "remaining_sync.py", "JSON Export"),
        ("Bitso", "remaining_sync.py", "JSON Export"),
    ]
    
    for broker, script, method in brokers_config:
        col1, col2, col3, col4 = st.columns([2, 2, 2, 1])
        
        with col1:
            st.markdown(f"**{broker}**")
            st.caption(method)
        
        with col2:
            if not df.empty and 'brokers' in df.columns:
                broker_value = df[df['brokers'].apply(
                    lambda x: broker in (x if isinstance(x, list) else [x]) if x else False
                )]['live_value'].sum()
                st.markdown(f"<span style='color: {COLORS['text']}; font-weight: 600;'>${broker_value:,.2f}</span>", unsafe_allow_html=True)
            else:
                st.write("$0.00")
        
        with col3:
            status_color = COLORS['green'] if method == "Live API" else COLORS['orange']
            st.markdown(f"<span style='color: {status_color}; font-size: 12px;'>● {method}</span>", unsafe_allow_html=True)
        
        with col4:
            if st.button("Sync", key=f"sync_btn_{broker}"):
                with st.spinner(f"Syncing {broker}..."):
                    try:
                        import subprocess
                        result = subprocess.run(
                            [sys.executable, script],
                            capture_output=True, text=True, timeout=120,
                            cwd=os.path.join(os.path.dirname(__file__), '..', 'brokers')
                        )
                        if result.returncode == 0:
                            st.success(f"✅ {broker} synced")
                            st.cache_data.clear()
                        else:
                            st.error(f"❌ Failed: {result.stderr[:200]}")
                    except Exception as e:
                        st.error(f"❌ Error: {e}")
        
        st.markdown(f"<hr style='border-color: {COLORS['border']}; margin: 8px 0;'>", unsafe_allow_html=True)

# ═══════════════════════════════════════════════════════════════════════════════
# ANALYSIS PAGE
# ═══════════════════════════════════════════════════════════════════════════════
elif page == "analysis":
    st.title("Portfolio Analysis")
    
    if not df.empty:
        total = df['live_value'].sum()
        
        # Risk metrics
        col1, col2, col3 = st.columns(3)
        with col1:
            high_risk = df[df['grade'] < 40]['live_value'].sum()
            risk_pct = (high_risk / total * 100) if total > 0 else 0
            st.metric("High Risk Exposure", format_currency(high_risk), f"{risk_pct:.1f}%")
        with col2:
            hold_risk = df[(df['grade'] >= 40) & (df['grade'] < 50)]['live_value'].sum()
            hold_pct = (hold_risk / total * 100) if total > 0 else 0
            st.metric("SELL Exposure", format_currency(hold_risk), f"{hold_pct:.1f}%")
        with col3:
            quality = df[df['grade'] >= 60]['live_value'].sum()
            quality_pct = (quality / total * 100) if total > 0 else 0
            st.metric("Quality (Grade 60+)", format_currency(quality), f"{quality_pct:.1f}%")
        
        # Risk assessment
        st.markdown("<div style='margin-top: 16px;'></div>", unsafe_allow_html=True)
        
        if risk_pct > 20:
            st.error(f"⚠️ High risk exposure is {risk_pct:.1f}% — consider trimming SELL-grade positions")
        elif risk_pct > 10:
            st.warning(f"⚠️ Moderate risk exposure is {risk_pct:.1f}%")
        else:
            st.success(f"✅ Risk exposure is healthy at {risk_pct:.1f}%")
        
        # Grade distribution
        st.subheader("Grade Distribution")
        grade_counts = df['grade'].apply(grade_label).value_counts()
        st.bar_chart(grade_counts, use_container_width=True)
        
        # Sector breakdown (if available)
        st.subheader("Sector Breakdown")
        st.info("Sector data requires yfinance lookups. Run full sync to populate.")
    else:
        st.warning("No positions loaded")
