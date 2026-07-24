document.addEventListener('DOMContentLoaded', function() {
    const root = document.getElementById('dashboard-root');
    if (!root) return;
    
    const analysisId = root.dataset.analysisId;
    if (!analysisId) return;

    const loadingOverlay = document.getElementById('loading-overlay');
    
    // Fetch dashboard data
    function fetchDashboardData(queryString = '') {
        loadingOverlay.classList.add('active');
        const url = `/analyzer/api/analysis/${analysisId}/${queryString ? '?' + queryString : ''}`;
        
        fetch(url)
            .then(response => response.json())
            .then(data => {
                renderNarrative(data.narrative);
                renderQuality(data.quality);
                renderKPIs(data.kpis);
                renderCharts(data.charts);
                renderInsights(data.insights);
                if (!queryString) {
                    setupFilters(data.filters);
                }
            })
            .catch(error => {
                console.error('Error fetching dashboard data:', error);
                // Handle error visually if needed
            })
            .finally(() => {
                loadingOverlay.classList.remove('active');
            });
    }

    // Initial fetch
    fetchDashboardData();

    function renderNarrative(narrativeText) {
        const el = document.getElementById('narrative-text');
        if (el && narrativeText) {
            el.textContent = narrativeText;
            el.classList.add('fade-in');
        }
    }

    function renderQuality(qualityData) {
        const container = document.getElementById('quality-badges');
        if (container && qualityData) {
            container.innerHTML = '';
            for (const [key, item] of Object.entries(qualityData)) {
                let badgeClass = 'bg-secondary';
                if (item.ratio < 5) badgeClass = 'bg-success';
                else if (item.ratio < 15) badgeClass = 'bg-warning text-dark';
                else badgeClass = 'bg-danger';
                
                const badge = `<span class="badge ${badgeClass} fs-6">${item.label || key}: ${item.value} (${item.ratio}%)</span>`;
                container.innerHTML += badge;
            }
        }
    }

    function renderKPIs(kpis) {
        const container = document.getElementById('kpi-container');
        if (container && kpis) {
            container.innerHTML = '';
            kpis.forEach(kpi => {
                const trendClass = kpi.trend === 'up' ? 'up' : (kpi.trend === 'down' ? 'down' : 'neutral');
                const trendIcon = kpi.trend === 'up' ? 'arrow-up' : (kpi.trend === 'down' ? 'arrow-down' : 'minus');
                const color = kpi.color || 'var(--primary)';
                
                container.innerHTML += `
                <div class="col-xl-3 col-md-4 col-sm-6 mb-4 fade-in">
                    <div class="kpi-card" style="border-right-color: ${color}">
                        <div class="kpi-icon" style="color: ${color}">
                            <i class="fas fa-${kpi.icon || 'chart-bar'}"></i>
                        </div>
                        <div class="kpi-content">
                            <div class="kpi-label">${kpi.label}</div>
                            <div class="kpi-value">${kpi.value}</div>
                            ${kpi.trend_value ? `
                            <div class="kpi-trend ${trendClass}">
                                <i class="fas fa-${trendIcon}"></i> ${kpi.trend_value}%
                            </div>` : ''}
                        </div>
                    </div>
                </div>`;
            });
        }
    }

    function renderCharts(chartsData) {
        const container = document.getElementById('charts-container');
        if (container && chartsData) {
            chartManager.destroyAll();
            container.innerHTML = '';
            
            chartsData.forEach((chart, index) => {
                const canvasId = `chart-${index}`;
                // Determine column width based on chart size request or default to 6
                const colClass = chart.fullWidth ? 'col-12' : 'col-md-6';
                
                container.innerHTML += `
                <div class="${colClass} mb-4 fade-in">
                    <div class="card h-100 shadow-sm">
                        <div class="card-header bg-white border-0 pt-3">
                            <h6 class="mb-0 fw-bold">${chart.title}</h6>
                        </div>
                        <div class="card-body">
                            <div class="chart-container">
                                <canvas id="${canvasId}"></canvas>
                            </div>
                        </div>
                    </div>
                </div>`;
            });

            // Need to let the DOM render canvases before creating charts
            setTimeout(() => {
                chartsData.forEach((chart, index) => {
                    const canvasId = `chart-${index}`;
                    const config = {
                        type: chart.type,
                        data: chart.data,
                        options: chart.options || {}
                    };
                    chartManager.create(canvasId, config);
                });
            }, 50);
        }
    }

    function renderInsights(insights) {
        const container = document.getElementById('insights-container');
        if (container && insights) {
            container.innerHTML = '';
            
            const typeMap = {
                'positive': { color: 'success', icon: 'check-circle' },
                'negative': { color: 'danger', icon: 'exclamation-circle' },
                'neutral': { color: 'info', icon: 'info-circle' },
                'warning': { color: 'warning', icon: 'exclamation-triangle' }
            };

            insights.slice(0, 4).forEach(insight => {
                const style = typeMap[insight.type] || typeMap['neutral'];
                
                container.innerHTML += `
                <div class="col-md-6 mb-4 fade-in">
                  <div class="insight-card border-start border-${style.color} border-4">
                    <div class="insight-icon bg-${style.color}">
                        <i class="fas fa-${style.icon}"></i>
                    </div>
                    <div class="insight-content">
                      <div class="insight-category">${insight.category || 'عام'}</div>
                      <h6>${insight.title}</h6>
                      <p class="mb-0 text-muted small">${insight.description}</p>
                    </div>
                  </div>
                </div>`;
            });
        }
    }

    function setupFilters(filters) {
        if (!filters) return;
        
        const catSelect = document.getElementById('filter-category');
        if (catSelect && filters.categories) {
            filters.categories.forEach(cat => {
                catSelect.innerHTML += `<option value="${cat.value}">${cat.label}</option>`;
            });
        }

        const dateFrom = document.getElementById('filter-date-from');
        const dateTo = document.getElementById('filter-date-to');
        if (filters.dateRange) {
            if (dateFrom && filters.dateRange.min) dateFrom.value = filters.dateRange.min;
            if (dateTo && filters.dateRange.max) dateTo.value = filters.dateRange.max;
        }

        const filterForm = document.getElementById('filter-form');
        if (filterForm) {
            filterForm.addEventListener('submit', function(e) {
                e.preventDefault();
                const formData = new FormData(filterForm);
                const queryParams = new URLSearchParams(formData).toString();
                fetchDashboardData(queryParams);
            });
        }

        const resetBtn = document.getElementById('reset-filters');
        if (resetBtn) {
            resetBtn.addEventListener('click', function() {
                if (filterForm) filterForm.reset();
                if (filters.dateRange) {
                    if (dateFrom && filters.dateRange.min) dateFrom.value = filters.dateRange.min;
                    if (dateTo && filters.dateRange.max) dateTo.value = filters.dateRange.max;
                }
                fetchDashboardData();
            });
        }
    }
});
