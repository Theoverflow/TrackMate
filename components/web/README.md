# Web Component

**Independent CI/CD** | **Version**: 0.2.0

## Overview

The Web Component provides interactive dashboards:
1. **Local Dashboard** - Site-level monitoring and analytics
2. **Central Dashboard** - Multi-site aggregation and comparison

## Components

### 1. Local Dashboard

Streamlit dashboard for site-level monitoring.

**Location**: `local-dashboard/app/`

**Features**:
- Real-time job monitoring
- Performance analytics
- Failure rate tracking
- Interactive charts (Plotly)
- Auto-refresh (configurable interval)
- CSV export
- Time range filtering
- Job detail views

**Pages**:
- **Overview**: Current job status and metrics
- **Jobs**: Job list with filtering
- **Performance**: Duration, CPU, memory charts
- **Failures**: Error tracking and analysis
- **Analytics**: Trends and patterns

**URL**: `http://localhost:8501`

### 2. Central Dashboard

Multi-site aggregation dashboard.

**Location**: `central-dashboard/app/`

**Features**:
- Multi-site comparison
- Cross-site analytics
- Site health status
- Aggregated metrics
- Top sites by performance
- Failure correlation

**Pages**:
- **Multi-Site Overview**: All sites at a glance
- **Site Comparison**: Side-by-side comparison
- **Global Analytics**: Cross-site trends
- **Site Health**: Health status dashboard

**URL**: `http://localhost:8502`

## Installation

### Docker Compose

```bash
docker compose -f ../../deploy/docker-compose/web.yml up -d
```

### Local Development

#### Local Dashboard
```bash
cd components/web/local-dashboard
pip install -r requirements.txt
streamlit run app/streamlit_app.py --server.port=8501
```

#### Central Dashboard
```bash
cd components/web/central-dashboard
pip install -r requirements.txt
streamlit run app/streamlit_app.py --server.port=8502
```

## Configuration

### Environment Variables

**Local Dashboard**:
```bash
LOCAL_API_URL=http://localhost:18000
REFRESH_INTERVAL_S=5
CACHE_TTL_S=30
LOG_LEVEL=INFO
```

**Central Dashboard**:
```bash
CENTRAL_API_URL=http://localhost:19000
REFRESH_INTERVAL_S=10
CACHE_TTL_S=60
LOG_LEVEL=INFO
```

### Streamlit Configuration

Create `.streamlit/config.toml`:
```toml
[server]
port = 8501
enableCORS = false
enableXsrfProtection = true

[browser]
gatherUsageStats = false

[theme]
primaryColor = "#0066CC"
backgroundColor = "#FFFFFF"
secondaryBackgroundColor = "#F0F2F6"
textColor = "#262730"
font = "sans serif"
```

## Testing

```bash
cd components/web
pytest tests/ -v --cov=.
```

**UI Tests**:
```bash
pytest tests/ui/ -v
```

## CI/CD

**GitHub Actions**: `.github/workflows/web.yml`

**Triggers**:
- Push to `main` or `develop`
- Changes to `components/web/**`

**Pipeline**:
1. **Test**: Python 3.10, 3.11, 3.12
2. **Lint**: ruff
3. **Build**: Docker images for both dashboards
4. **Push**: ghcr.io registry
5. **Deploy**: Staging environment

## Docker Images

- **Local Dashboard**: `ghcr.io/theoverflow/trackmate/local-dashboard:latest`
- **Central Dashboard**: `ghcr.io/theoverflow/trackmate/central-dashboard:latest`

## Features

### Real-Time Updates

Both dashboards support auto-refresh:
- **Local**: 5-second intervals (configurable)
- **Central**: 10-second intervals (configurable)

### Interactive Charts

All charts use Plotly for interactivity:
- Zoom, pan, hover tooltips
- Export to PNG
- Custom styling
- Responsive design

### Data Export

Export data to CSV:
- Filtered job lists
- Performance metrics
- Time-series data

### Performance

- **Caching**: API results cached (30-60s TTL)
- **Pagination**: Large datasets paginated
- **Lazy Loading**: Charts loaded on-demand
- **Connection Pooling**: Efficient API calls

## Development

### Setup
```bash
cd components/web
python -m venv venv
source venv/bin/activate
pip install -e ".[dev]"
```

### Run Tests
```bash
pytest tests/ -v
```

### Build Docker Images
```bash
docker build -f Dockerfile.local-dashboard -t local-dashboard .
docker build -f Dockerfile.central-dashboard -t central-dashboard .
```

### Hot Reload

Streamlit supports hot reload during development:
```bash
cd local-dashboard
streamlit run app/streamlit_app.py
# Edit files and see changes immediately
```

## Customization

### Themes

Edit `.streamlit/config.toml` to customize colors and fonts.

### Layouts

Modify dashboard layouts in `app/streamlit_app.py`:
```python
# Add custom page
def custom_page():
    st.title("Custom Analytics")
    # Your custom code
    
# Register page
pages = {
    "Overview": overview_page,
    "Custom": custom_page,
}
```

### Charts

Add custom charts using Plotly:
```python
import plotly.express as px

fig = px.line(df, x='timestamp', y='duration_s', 
              title='Job Duration Over Time')
st.plotly_chart(fig)
```

## Dependencies

See `pyproject.toml` for full dependency list.

**Core**:
- streamlit
- plotly
- pandas
- httpx
- requests

## Troubleshooting

### Dashboard not loading
- Check API URL is correct
- Verify API is running: `curl $API_URL/v1/healthz`
- Check network connectivity

### Slow performance
- Increase `CACHE_TTL_S`
- Reduce `REFRESH_INTERVAL_S`
- Enable pagination for large datasets

### Charts not displaying
- Check data format from API
- Verify Plotly version compatibility
- Clear browser cache

## Versioning

**Current Version**: 0.2.0

**Version Strategy**: Independent from other components

## Support

For issues specific to the web component, create an issue with the `component:web` label.

