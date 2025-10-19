"""
Central Wafer Monitor Dashboard - Multi-site aggregated view.

Provides centralized monitoring across multiple fabrication sites with:
- Multi-site comparison
- Cross-site analytics
- Site health monitoring
- Aggregated metrics
"""
import os
import requests
import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime, timedelta
from typing import Dict, List, Any

CENTRAL_API = os.getenv('CENTRAL_API', 'http://localhost:19000')
DEFAULT_SITE = os.getenv('DEFAULT_SITE', 'fab1')

# Page configuration
st.set_page_config(
    page_title='Central Wafer Monitor',
    layout='wide',
    page_icon='🌐',
    initial_sidebar_state='expanded'
)

# Custom CSS
st.markdown("""
<style>
    .site-card {
        background-color: #f0f2f6;
        padding: 15px;
        border-radius: 10px;
        margin: 10px 0;
    }
    .stMetric {
        background-color: #ffffff;
        padding: 15px;
        border-radius: 8px;
        box-shadow: 0 2px 4px rgba(0,0,0,0.1);
    }
</style>
""", unsafe_allow_html=True)

st.title('🌐 Central Wafer Monitor — Multi-Site Aggregation')

# Sidebar
st.sidebar.header('⚙️ Settings')

# Auto-refresh
auto_refresh = st.sidebar.checkbox('🔄 Auto-refresh (every 15s)', value=False)

# Load available sites
@st.cache_data(ttl=60)
def load_sites() -> Dict[str, Any]:
    """Load available sites from Central API."""
    try:
        r = requests.get(f'{CENTRAL_API}/v1/sites', timeout=3)
        r.raise_for_status()
        return r.json()
    except Exception as e:
        st.sidebar.error(f"Failed to load sites: {str(e)}")
        return {'sites': [], 'count': 0}


sites_data = load_sites()
available_sites = [s['id'] for s in sites_data.get('sites', [])]

if not available_sites:
    st.error("⚠️ No sites configured. Please configure SITES in the Central API.")
    st.stop()

# Site selector
site = st.sidebar.selectbox(
    '🏭 Select Site',
    available_sites,
    index=available_sites.index(DEFAULT_SITE) if DEFAULT_SITE in available_sites else 0
)

# Time window
window = st.sidebar.selectbox(
    '📅 Time Window',
    ['1h', '6h', '24h', '72h'],
    index=3
)

# Status filter
status_options = ['running', 'succeeded', 'failed', 'canceled']
select_all = st.sidebar.checkbox('Select All Statuses', value=True)
if select_all:
    status = status_options
else:
    status = st.sidebar.multiselect(
        '📊 Status',
        status_options,
        default=['running', 'succeeded', 'failed']
    )

# App name filter
app_name = st.sidebar.text_input('🔍 App name contains')

# Multi-site comparison
with st.sidebar.expander('🌍 Multi-Site Comparison'):
    compare_sites = st.checkbox('Enable multi-site comparison', value=False)
    if compare_sites:
        comparison_sites = st.multiselect(
            'Sites to compare',
            available_sites,
            default=available_sites[:3] if len(available_sites) >= 3 else available_sites
        )


@st.cache_data(ttl=15 if auto_refresh else 60)
def load_jobs(site_id: str, params: Dict[str, Any]) -> Dict[str, Any]:
    """Load jobs from Central API for a specific site."""
    try:
        params['site'] = site_id
        r = requests.get(f'{CENTRAL_API}/v1/jobs', params=params, timeout=5)
        r.raise_for_status()
        return r.json()
    except Exception as e:
        st.error(f"Failed to load jobs for {site_id}: {str(e)}")
        return {'items': [], 'count': 0}


@st.cache_data(ttl=10 if auto_refresh else 30)
def load_health() -> Dict[str, Any]:
    """Load health status from Central API."""
    try:
        r = requests.get(f'{CENTRAL_API}/v1/healthz', timeout=3)
        r.raise_for_status()
        return r.json()
    except Exception as e:
        return {'status': 'error', 'error': str(e), 'sites': {}}


# Build query parameters
now = datetime.utcnow()
delta = {'1h': 1, '6h': 6, '24h': 24, '72h': 72}[window]
frm = (now - timedelta(hours=delta)).isoformat() + 'Z'
to = now.isoformat() + 'Z'

params = {
    'from': frm,
    'to': to,
    'status': ','.join(status) if status else '',
    'limit': 1000
}

if app_name:
    params['app_name'] = app_name

# Load data
data = load_jobs(site, params)
items = data.get('items', [])
health = load_health()

# Display system health
st.sidebar.divider()
st.sidebar.subheader('🏥 System Health')

central_status = health.get('status', 'unknown')
if central_status == 'ok':
    st.sidebar.success('✅ Central API: Healthy')
else:
    st.sidebar.warning(f"⚠️ Central API: {central_status}")

# Site health status
site_health = health.get('sites', {})
for site_id in available_sites:
    site_info = site_health.get(site_id, {})
    site_status = site_info.get('status', 'unknown')
    
    if site_status == 'ok':
        st.sidebar.success(f"✅ {site_id}: Healthy")
    elif site_status == 'degraded':
        st.sidebar.warning(f"⚠️ {site_id}: Degraded")
    else:
        st.sidebar.error(f"❌ {site_id}: {site_status}")

# Main dashboard
st.subheader(f"📊 Site: {site}")

# Key metrics
col1, col2, col3, col4, col5 = st.columns(5)

total_jobs = len(items)
succeeded = sum(1 for i in items if i.get('status') == 'succeeded')
failed = sum(1 for i in items if i.get('status') == 'failed')
running = sum(1 for i in items if i.get('status') == 'running')
canceled = sum(1 for i in items if i.get('status') == 'canceled')

col1.metric('📊 Total Jobs', total_jobs)
col2.metric('✅ Succeeded', succeeded)
col3.metric('❌ Failed', failed)
col4.metric('🔄 Running', running)
col5.metric('🚫 Canceled', canceled)

# Success rate
if total_jobs > 0:
    success_rate = (succeeded / (succeeded + failed)) * 100 if (succeeded + failed) > 0 else 0
    st.metric('🎯 Success Rate', f"{success_rate:.2f}%")

# Multi-site comparison
if compare_sites and 'comparison_sites' in locals():
    st.divider()
    st.subheader('🌍 Multi-Site Comparison')
    
    comparison_data = []
    for comp_site in comparison_sites:
        site_data = load_jobs(comp_site, params)
        site_items = site_data.get('items', [])
        
        comparison_data.append({
            'Site': comp_site,
            'Total Jobs': len(site_items),
            'Succeeded': sum(1 for i in site_items if i.get('status') == 'succeeded'),
            'Failed': sum(1 for i in site_items if i.get('status') == 'failed'),
            'Running': sum(1 for i in site_items if i.get('status') == 'running'),
            'Success Rate (%)': (sum(1 for i in site_items if i.get('status') == 'succeeded') / 
                                len(site_items) * 100) if site_items else 0
        })
    
    df_comparison = pd.DataFrame(comparison_data)
    
    # Comparison bar chart
    fig_comparison = px.bar(
        df_comparison,
        x='Site',
        y=['Succeeded', 'Failed', 'Running'],
        title='Jobs by Status Across Sites',
        barmode='group',
        color_discrete_map={
            'Succeeded': '#00cc00',
            'Failed': '#ff4444',
            'Running': '#4488ff'
        }
    )
    st.plotly_chart(fig_comparison, use_container_width=True)
    
    # Comparison table
    st.dataframe(df_comparison, use_container_width=True, hide_index=True)

# Charts
if items:
    st.divider()
    st.subheader('📈 Analytics')
    
    df = pd.DataFrame(items)
    
    # Convert timestamps
    if 'inserted_at' in df.columns:
        df['inserted_at'] = pd.to_datetime(df['inserted_at'])
    
    chart_col1, chart_col2 = st.columns(2)
    
    with chart_col1:
        # Status pie chart
        status_counts = df['status'].value_counts()
        fig_pie = px.pie(
            values=status_counts.values,
            names=status_counts.index,
            title=f'Job Status Distribution - {site}',
            color=status_counts.index,
            color_discrete_map={
                'succeeded': '#00cc00',
                'failed': '#ff4444',
                'running': '#4488ff',
                'canceled': '#999999'
            }
        )
        st.plotly_chart(fig_pie, use_container_width=True)
    
    with chart_col2:
        # Timeline
        if 'inserted_at' in df.columns:
            df_time = df.set_index('inserted_at').resample('1H').size().reset_index(name='count')
            fig_time = px.area(
                df_time,
                x='inserted_at',
                y='count',
                title=f'Job Activity Timeline - {site}',
                labels={'inserted_at': 'Time', 'count': 'Jobs per Hour'}
            )
            st.plotly_chart(fig_time, use_container_width=True)
    
    # Performance metrics
    if all(col in df.columns for col in ['duration_s', 'mem_max_mb']):
        st.divider()
        st.subheader('⚡ Performance Overview')
        
        perf_col1, perf_col2, perf_col3, perf_col4 = st.columns(4)
        
        with perf_col1:
            avg_duration = df['duration_s'].mean()
            st.metric('Avg Duration', f"{avg_duration:.2f}s")
        
        with perf_col2:
            max_duration = df['duration_s'].max()
            st.metric('Max Duration', f"{max_duration:.2f}s")
        
        with perf_col3:
            avg_memory = df['mem_max_mb'].mean()
            st.metric('Avg Memory', f"{avg_memory:.1f} MB")
        
        with perf_col4:
            max_memory = df['mem_max_mb'].max()
            st.metric('Max Memory', f"{max_memory:.1f} MB")

# Jobs table
st.divider()
st.subheader('📋 Recent Jobs')

if items:
    st.info(f"Showing {len(items)} jobs from {site} (last {window})")
    
    df_display = pd.DataFrame(items)
    
    # Select and format columns
    columns_to_show = [
        'job_id', 'app_name', 'status', 'job_key',
        'duration_s', 'mem_max_mb', 'started_at', 'inserted_at'
    ]
    
    columns_to_show = [col for col in columns_to_show if col in df_display.columns]
    
    # Format numeric columns
    if 'duration_s' in df_display.columns:
        df_display['duration_s'] = df_display['duration_s'].round(2)
    if 'mem_max_mb' in df_display.columns:
        df_display['mem_max_mb'] = df_display['mem_max_mb'].round(1)
    
    st.dataframe(
        df_display[columns_to_show],
        use_container_width=True,
        hide_index=True
    )
    
    # Export
    csv = df_display.to_csv(index=False)
    st.download_button(
        label='📥 Download CSV',
        data=csv,
        file_name=f'jobs_{site}_{datetime.now():%Y%m%d_%H%M%S}.csv',
        mime='text/csv'
    )
else:
    st.warning(f"No jobs found for {site} matching the selected filters")

# Auto-refresh
if auto_refresh:
    import time
    time.sleep(15)
    st.rerun()

# Footer
st.divider()
st.caption(f"Last updated: {datetime.now():%Y-%m-%d %H:%M:%S} | Site: {site} | Range: {window}")
