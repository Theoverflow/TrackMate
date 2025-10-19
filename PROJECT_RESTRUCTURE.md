# Project Restructure - 3-Component Architecture

## Overview

Restructuring project into 3 independent components for separate CI/CD pipelines:

1. **Monitoring Component** - SDK + Sidecar Agent
2. **Data Plane Component** - APIs + Database + Archiver
3. **Web Component** - Dashboards (Local + Central)

## New Structure

```
wafer-monitor-v2/
├── components/
│   ├── monitoring/              # Component 1: Monitoring
│   │   ├── sdk/                 # Monitoring SDK
│   │   │   ├── monitoring_sdk/
│   │   │   ├── pyproject.toml
│   │   │   ├── Dockerfile
│   │   │   └── tests/
│   │   ├── sidecar/             # Sidecar Agent
│   │   │   ├── app/
│   │   │   ├── pyproject.toml
│   │   │   ├── Dockerfile
│   │   │   └── tests/
│   │   ├── .gitlab-ci.yml       # Monitoring CI/CD
│   │   └── README.md
│   │
│   ├── data-plane/              # Component 2: Data Plane
│   │   ├── local-api/           # Local API
│   │   │   ├── app/
│   │   │   ├── pyproject.toml
│   │   │   └── Dockerfile
│   │   ├── central-api/         # Central API
│   │   │   ├── app/
│   │   │   ├── pyproject.toml
│   │   │   └── Dockerfile
│   │   ├── archiver/            # Data Archiver
│   │   │   ├── app/
│   │   │   ├── pyproject.toml
│   │   │   └── Dockerfile
│   │   ├── database/            # Database schemas & migrations
│   │   │   ├── schema.sql
│   │   │   ├── migrations/
│   │   │   └── scripts/
│   │   ├── tests/
│   │   ├── .gitlab-ci.yml       # Data Plane CI/CD
│   │   └── README.md
│   │
│   └── web/                     # Component 3: Web Dashboards
│       ├── local-dashboard/     # Local Site Dashboard
│       │   ├── app/
│       │   ├── pyproject.toml
│       │   └── Dockerfile
│       ├── central-dashboard/   # Central Dashboard
│       │   ├── app/
│       │   ├── pyproject.toml
│       │   └── Dockerfile
│       ├── tests/
│       ├── .gitlab-ci.yml       # Web CI/CD
│       └── README.md
│
├── shared/                      # Shared utilities
│   ├── utils/
│   ├── integrations/
│   └── config/
│
├── deploy/                      # Deployment configurations
│   ├── kubernetes/
│   │   ├── monitoring/
│   │   ├── data-plane/
│   │   └── web/
│   ├── docker-compose/
│   │   ├── monitoring.yml
│   │   ├── data-plane.yml
│   │   └── web.yml
│   └── helm/
│
├── examples/                    # Examples remain shared
├── docs/                        # Documentation
├── .github/                     # GitHub Actions CI/CD
│   └── workflows/
│       ├── monitoring.yml
│       ├── data-plane.yml
│       └── web.yml
├── .gitlab-ci.yml               # Root GitLab CI/CD (orchestrator)
└── README.md
```

## Migration Plan

### Phase 1: Create New Structure
1. Create `components/` directory
2. Move monitoring components
3. Move data-plane components
4. Move web components
5. Extract shared utilities

### Phase 2: Update Configurations
1. Create component-specific `pyproject.toml`
2. Create component-specific Dockerfiles
3. Update import paths

### Phase 3: CI/CD Setup
1. Create GitHub Actions workflows per component
2. Create GitLab CI/CD per component
3. Setup dependency triggers

### Phase 4: Documentation
1. Update component READMEs
2. Update deployment guides
3. Create migration guide

## Benefits

1. **Independent Deployment**: Deploy monitoring without affecting web
2. **Separate Testing**: Test each component in isolation
3. **Parallel CI/CD**: Run pipelines concurrently
4. **Clear Ownership**: Teams can own specific components
5. **Versioning**: Independent version numbers per component
6. **Scalability**: Scale components independently

