"""
Local Wafer Monitor Dashboard - Enhanced with real-time updates and visualizations.

Provides a comprehensive view of local site monitoring with:
- Real-time metrics updates
- Interactive charts and visualizations
- Detailed job and subjob inspection
- Performance analytics
"""
import os
import requests
import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime, timedelta
from typing import Dict, List, Any

BASE_URL = os.getenv('LOCAL_API', 'http://localhost:18000')

# Page configuration
st.set_page_config(
    page_title='Local Wafer Monitor',
    layout='wide',
    page_icon='🏭',
    initial_sidebar_state='expanded'
)

# Custom CSS for better styling
st.markdown("""
<style>
    .metric-card {
        background-color: #f0f2f6;
        padding: 20px;
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

st.title('🏭 Local Wafer Monitor — Jobs & Performance')

# Sidebar filters
st.sidebar.header('⚙️ Filters')

# Auto-refresh toggle
auto_refresh = st.sidebar.checkbox('🔄 Auto-refresh (every 10s)', value=False)
if auto_refresh:
    st.sidebar.info('Dashboard will auto-refresh every 10 seconds')

# Time window selector
window = st.sidebar.selectbox(
    '📅 Time Window',
    ['1h', '6h', '24h', '72h'],
    index=3
)

# Status filter with all/select all
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

# Advanced filters
with st.sidebar.expander('🔧 Advanced Filters'):
    show_metrics = st.checkbox('Show detailed metrics', value=True)
    show_charts = st.checkbox('Show charts', value=True)
    max_rows = st.slider('Max rows to display', 10, 1000, 100)


@st.cache_data(ttl=10 if auto_refresh else 60)
def load_jobs(params: Dict[str, Any]) -> Dict[str, Any]:
    """Load jobs from the API with caching."""
    try:
        r = requests.get(f'{BASE_URL}/v1/jobs', params=params, timeout=5)
        r.raise_for_status()
        return r.json()
    except Exception as e:
        st.error(f"Failed to load jobs: {str(e)}")
        return {'items': [], 'count': 0}


@st.cache_data(ttl=10 if auto_refresh else 60)
def load_health() -> Dict[str, Any]:
    """Load health status from the API."""
    try:
        r = requests.get(f'{BASE_URL}/v1/healthz', timeout=2)
        r.raise_for_status()
        return r.json()
    except Exception as e:
        return {'status': 'error', 'error': str(e)}


# Build query parameters
now = datetime.utcnow()
delta = {'1h': 1, '6h': 6, '24h': 24, '72h': 72}[window]
frm = (now - timedelta(hours=delta)).isoformat() + 'Z'
to = now.isoformat() + 'Z'

params = {
    'from': frm,
    'to': to,
    'status': ','.join(status) if status else '',
    'limit': max_rows
}

if app_name:
    params['app_name'] = app_name

# Load data
data = load_jobs(params)
items = data.get('items', [])
health = load_health()

# Display health status
if health.get('status') == 'ok':
    st.sidebar.success('✅ API Status: Healthy')
else:
    st.sidebar.error(f"❌ API Status: {health.get('status', 'Unknown')}")

# Main dashboard
col1, col2, col3, col4, col5 = st.columns(5)

total_jobs = len(items)
succeeded = sum(1 for i in items if i.get('status') == 'succeeded')
failed = sum(1 for i in items if i.get('status') == 'failed')
running = sum(1 for i in items if i.get('status') == 'running')
canceled = sum(1 for i in items if i.get('status') == 'canceled')

col1.metric('📊 Total Jobs', total_jobs)
col2.metric('✅ Succeeded', succeeded, delta=f"{succeeded/total_jobs*100:.1f}%" if total_jobs > 0 else "0%")
col3.metric('❌ Failed', failed, delta=f"{failed/total_jobs*100:.1f}%" if total_jobs > 0 else "0%")
col4.metric('🔄 Running', running)
col5.metric('🚫 Canceled', canceled)

# Success rate calculation
if total_jobs > 0:
    success_rate = (succeeded / (succeeded + failed)) * 100 if (succeeded + failed) > 0 else 0
    st.metric('🎯 Success Rate', f"{success_rate:.2f}%")

# Charts section
if show_charts and items:
    st.divider()
    st.subheader('📈 Analytics')
    
    df = pd.DataFrame(items)
    
    # Convert timestamps
    if 'inserted_at' in df.columns:
        df['inserted_at'] = pd.to_datetime(df['inserted_at'])
    if 'started_at' in df.columns:
        df['started_at'] = pd.to_datetime(df['started_at'])
    if 'ended_at' in df.columns:
        df['ended_at'] = pd.to_datetime(df['ended_at'])
    
    chart_col1, chart_col2 = st.columns(2)
    
    with chart_col1:
        # Status distribution pie chart
        status_counts = df['status'].value_counts()
        fig_pie = px.pie(
            values=status_counts.values,
            names=status_counts.index,
            title='Job Status Distribution',
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
        # Jobs over time
        if 'inserted_at' in df.columns:
            df_time = df.set_index('inserted_at').resample('1H').size().reset_index(name='count')
            fig_time = px.line(
                df_time,
                x='inserted_at',
                y='count',
                title='Jobs Over Time (Hourly)',
                labels={'inserted_at': 'Time', 'count': 'Number of Jobs'}
            )
            st.plotly_chart(fig_time, use_container_width=True)
    
    # Performance metrics
    if show_metrics and all(col in df.columns for col in ['duration_s', 'cpu_user_s', 'mem_max_mb']):
        st.divider()
        st.subheader('⚡ Performance Metrics')
        
        perf_col1, perf_col2, perf_col3 = st.columns(3)
        
        with perf_col1:
            # Duration histogram
            fig_duration = px.histogram(
                df[df['duration_s'].notna()],
                x='duration_s',
                title='Job Duration Distribution',
                labels={'duration_s': 'Duration (seconds)'},
                nbins=30
            )
            st.plotly_chart(fig_duration, use_container_width=True)
        
        with perf_col2:
            # CPU usage
            fig_cpu = px.box(
                df[df['cpu_user_s'].notna()],
                y='cpu_user_s',
                title='CPU Usage Distribution',
                labels={'cpu_user_s': 'CPU User Time (s)'}
            )
            st.plotly_chart(fig_cpu, use_container_width=True)
        
        with perf_col3:
            # Memory usage
            fig_mem = px.box(
                df[df['mem_max_mb'].notna()],
                y='mem_max_mb',
                title='Memory Usage Distribution',
                labels={'mem_max_mb': 'Peak Memory (MB)'}
            )
            st.plotly_chart(fig_mem, use_container_width=True)
        
        # Performance summary statistics
        st.subheader('📊 Performance Summary')
        summary_col1, summary_col2, summary_col3 = st.columns(3)
        
        with summary_col1:
            st.metric('Avg Duration', f"{df['duration_s'].mean():.2f}s")
            st.metric('Max Duration', f"{df['duration_s'].max():.2f}s")
        
        with summary_col2:
            st.metric('Avg CPU Time', f"{df['cpu_user_s'].mean():.2f}s")
            st.metric('Max CPU Time', f"{df['cpu_user_s'].max():.2f}s")
        
        with summary_col3:
            st.metric('Avg Memory', f"{df['mem_max_mb'].mean():.2f} MB")
            st.metric('Max Memory', f"{df['mem_max_mb'].max():.2f} MB")
    
    # Application breakdown
    if 'app_name' in df.columns:
        st.divider()
        st.subheader('📦 Application Breakdown')
        
        app_stats = df.groupby('app_name').agg({
            'job_id': 'count',
            'status': lambda x: (x == 'succeeded').sum() / len(x) * 100,
            'duration_s': 'mean',
            'mem_max_mb': 'mean'
        }).round(2)
        
        app_stats.columns = ['Total Jobs', 'Success Rate (%)', 'Avg Duration (s)', 'Avg Memory (MB)']
        st.dataframe(app_stats, use_container_width=True)

# Jobs table
st.divider()
st.subheader('📋 Jobs Table')

# Display info about filters
if items:
    st.info(f"Showing {len(items)} jobs from the last {window}")
else:
    st.warning("No jobs found matching the selected filters")

# Format and display the table
if items:
    df_display = pd.DataFrame(items)
    
    # Select columns to display
    columns_to_show = [
        'job_id', 'app_name', 'app_version', 'status', 'job_key',
        'duration_s', 'cpu_user_s', 'cpu_system_s', 'mem_max_mb',
        'started_at', 'ended_at', 'inserted_at'
    ]
    
    columns_to_show = [col for col in columns_to_show if col in df_display.columns]
    
    # Format numeric columns
    numeric_cols = ['duration_s', 'cpu_user_s', 'cpu_system_s', 'mem_max_mb']
    for col in numeric_cols:
        if col in df_display.columns:
            df_display[col] = df_display[col].round(2)
    
    st.dataframe(
        df_display[columns_to_show],
        use_container_width=True,
        hide_index=True
    )
    
    # Download button
    csv = df_display.to_csv(index=False)
    st.download_button(
        label='📥 Download CSV',
        data=csv,
        file_name=f'jobs_{datetime.now():%Y%m%d_%H%M%S}.csv',
        mime='text/csv'
    )

# Auto-refresh logic
if auto_refresh:
    import time
    time.sleep(10)
    st.rerun()

# Footer
st.divider()
st.caption(f"Last updated: {datetime.now():%Y-%m-%d %H:%M:%S} | Data range: {window}")
