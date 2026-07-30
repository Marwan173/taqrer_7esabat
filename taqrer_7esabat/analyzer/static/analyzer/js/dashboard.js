document.addEventListener('DOMContentLoaded', function() {
    const root = document.getElementById('dashboard-root');
    if (!root) return;
    
    const analysisId = root.dataset.analysisId;
    if (!analysisId) return;

    const loadingOverlay = document.getElementById('loading-overlay');
    
    // Fetch dashboard data
    function fetchDashboardData(queryString = '') {
        if (loadingOverlay) loadingOverlay.classList.add('active');
        const url = `/analyzer/api/analysis/${analysisId}/${queryString ? '?' + queryString : ''}`;
        
        fetch(url)
            .then(response => response.json())
            .then(data => {
                renderModeBanner(data);
                renderNarrative(data.narrative);
                renderQuality(data.quality);
                renderChecklist(data.requested_items_checklist);
                renderKPIs(data.kpis);
                renderCharts(data.charts);
                renderInsights(data.insights);
                if (!queryString) {
                    setupFilters(data.filters);
                }
            })
            .catch(error => {
                console.error('Error fetching dashboard data:', error);
            })
            .finally(() => {
                if (loadingOverlay) loadingOverlay.classList.remove('active');
            });
    }

    // Initial fetch
    fetchDashboardData();

    function renderModeBanner(data) {
        const container = document.getElementById('analysis-mode-banner');
        if (!container) return;
        
        const mode = data.analysis_mode;
        const customQuery = data.custom_query;
        const isFallback = data.is_ai_fallback === true;

        let badgeAi = isFallback
            ? `<span class="badge bg-warning text-dark ms-2 p-2 fs-6 rounded-pill"><i class="fas fa-exclamation-circle ms-1"></i> تحليل مبسط — خدمة الذكاء الاصطناعي غير متوفرة حالياً</span>`
            : `<span class="badge bg-success text-white ms-2 p-2 fs-6 rounded-pill"><i class="fas fa-brain ms-1"></i> تحليل محرك الذكاء الاصطناعي (Claude)</span>`;

        if (mode === 'custom' && customQuery) {
            container.innerHTML = `
            <div class="col-12 fade-in">
                <div class="card border-0 bg-info-subtle border-start border-info border-4 shadow-sm">
                    <div class="card-body py-3 px-4 d-flex align-items-center justify-content-between flex-wrap gap-2">
                        <div class="d-flex align-items-center flex-wrap gap-2">
                            ${badgeAi}
                            <span class="badge bg-info text-dark ms-2 p-2 fs-6 rounded-pill">
                                <i class="fas fa-sliders-h ms-1"></i> نوع التحليل: تحليل مخصص
                            </span>
                            <div>
                                <span class="text-muted small d-block">الطلب المخصص المحدد:</span>
                                <h6 class="mb-0 fw-bold text-dark"><i class="fas fa-comment-dots text-info ms-2"></i>"${customQuery}"</h6>
                            </div>
                        </div>
                        <a href="/analyzer/" class="btn btn-sm btn-outline-info rounded-pill px-3">
                            <i class="fas fa-plus ms-1"></i> تحليل جديد
                        </a>
                    </div>
                </div>
            </div>`;
        } else {
            container.innerHTML = `
            <div class="col-12 fade-in">
                <div class="d-flex align-items-center justify-content-between flex-wrap gap-2 card p-3 shadow-sm border-0">
                    <div class="d-flex align-items-center gap-2">
                        ${badgeAi}
                        <span class="badge bg-primary-subtle text-primary border border-primary-subtle p-2 fs-6 rounded-pill">
                            <i class="fas fa-wand-magic-sparkles ms-1"></i> نوع التحليل: تحليل تلقائي شامل
                        </span>
                    </div>
                    <a href="/analyzer/" class="btn btn-sm btn-outline-primary rounded-pill px-3">
                        <i class="fas fa-plus ms-1"></i> تحليل جديد
                    </a>
                </div>
            </div>`;
        }
    }

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
            
            const issues = qualityData.issues || [];
            const completeness = qualityData.completeness_score;
            
            if (completeness !== undefined) {
                let badgeClass = completeness >= 95 ? 'bg-success-subtle text-success border border-success-subtle' : (completeness >= 85 ? 'bg-warning-subtle text-warning border border-warning-subtle' : 'bg-danger-subtle text-danger border border-danger-subtle');
                container.innerHTML += `<span class="badge ${badgeClass} p-2 px-3 rounded-pill fs-7 fw-bold"><i class="fas fa-check-double ms-1"></i> درجة الاكتمال: ${completeness}%</span>`;
            }

            if (issues.length === 0 || (issues.length === 1 && issues[0].type === 'clean')) {
                container.innerHTML += `<span class="badge bg-success-subtle text-success border border-success-subtle p-2 px-3 rounded-pill fs-7 fw-bold"><i class="fas fa-check-circle ms-1"></i> جودة سليمة بدون مشاكل</span>`;
            } else {
                issues.forEach(iss => {
                    let badgeClass = (iss.severity === 'danger' || iss.severity === 'high') ? 'bg-danger-subtle text-danger border border-danger-subtle' : 'bg-warning-subtle text-warning border border-warning-subtle';
                    let icon = iss.icon || 'exclamation-triangle';
                    container.innerHTML += `<span class="badge ${badgeClass} p-2 px-3 rounded-pill fs-7 fw-bold"><i class="fas fa-${icon} ms-1"></i> ${iss.message}</span>`;
                });
            }
        }
    }

    function renderChecklist(checklist) {
        const container = document.getElementById('checklist-container');
        if (!container) return;

        if (!checklist || checklist.length === 0) {
            container.style.display = 'none';
            container.innerHTML = '';
            return;
        }

        container.style.display = 'flex';
        let itemsHtml = '';
        checklist.forEach(item => {
            const isFulfilled = item.fulfilled;
            const badgeClass = isFulfilled ? 'bg-success text-white' : 'bg-danger text-white';
            const icon = isFulfilled ? 'check-circle' : 'times-circle';
            const statusText = isFulfilled ? 'تم التوافق' : 'غير متوفر في البيانات';
            const noteText = item.how ? item.how : '';

            itemsHtml += `
            <div class="col-md-6 col-lg-4 mb-3">
                <div class="card h-100 border-0 shadow-sm border-start border-${isFulfilled ? 'success' : 'danger'} border-4">
                    <div class="card-body p-3">
                        <div class="d-flex align-items-center justify-content-between mb-2">
                            <span class="badge ${badgeClass} p-1 px-2 rounded-pill fs-7">
                                <i class="fas fa-${icon} ms-1"></i> ${statusText}
                            </span>
                        </div>
                        <h6 class="fw-bold mb-1 text-dark fs-7">${item.request_item}</h6>
                        ${noteText ? `<small class="text-muted d-block mt-1">${noteText}</small>` : ''}
                    </div>
                </div>
            </div>`;
        });

        container.innerHTML = `
        <div class="col-12">
            <div class="card border-0 shadow-sm p-4 bg-light">
                <div class="d-flex align-items-center mb-3">
                    <div class="bg-primary text-white rounded-circle p-2 ms-3 d-flex align-items-center justify-content-center" style="width: 38px; height: 38px;">
                        <i class="fas fa-tasks fs-6"></i>
                    </div>
                    <div>
                        <h6 class="mb-0 fw-bold">تقرير التوافق مع متطلبات التحليل المخصص</h6>
                        <small class="text-muted">متابعة تنفيذ كافة النقاط المطلوبة من قبل محرك الذكاء الاصطناعي</small>
                    </div>
                </div>
                <div class="row">
                    ${itemsHtml}
                </div>
            </div>
        </div>`;
    }


    function renderKPIs(kpis) {
        const container = document.getElementById('kpi-container');
        if (container && kpis) {
            container.innerHTML = '';
            kpis.forEach(kpi => {
                const trendClass = kpi.trend === 'up' ? 'up' : (kpi.trend === 'down' ? 'down' : 'neutral');
                const trendIcon = kpi.trend === 'up' ? 'arrow-up' : (kpi.trend === 'down' ? 'arrow-down' : 'minus');
                
                let iconColorClass = 'text-primary';
                let borderColor = 'var(--primary)';
                if (kpi.color === 'success') { iconColorClass = 'text-success'; borderColor = 'var(--success)'; }
                else if (kpi.color === 'danger') { iconColorClass = 'text-danger'; borderColor = 'var(--danger)'; }
                else if (kpi.color === 'info') { iconColorClass = 'text-info'; borderColor = 'var(--info)'; }
                else if (kpi.color === 'warning') { iconColorClass = 'text-warning'; borderColor = 'var(--warning)'; }

                container.innerHTML += `
                <div class="col-xl-3 col-md-4 col-sm-6 mb-4 fade-in">
                    <div class="kpi-card" style="border-right-color: ${borderColor}">
                        <div class="kpi-icon ${iconColorClass}">
                            <i class="fas fa-${kpi.icon || 'chart-bar'}"></i>
                        </div>
                        <div class="kpi-content">
                            <div class="kpi-label">${kpi.label}</div>
                            <div class="kpi-value">${kpi.value}</div>
                            ${kpi.subtitle ? `<div class="text-muted small">${kpi.subtitle}</div>` : ''}
                            ${kpi.trend_value ? `
                            <div class="kpi-trend ${trendClass}">
                                <i class="fas fa-${trendIcon} ms-1"></i> ${kpi.trend_value}%
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
                const colClass = chart.fullWidth ? 'col-12' : 'col-md-6';
                
                let icon = 'chart-bar';
                if (chart.type === 'line') icon = 'chart-line';
                else if (chart.type === 'doughnut' || chart.type === 'pie') icon = 'chart-pie';
                else if (chart.type === 'scatter') icon = 'braille';

                container.innerHTML += `
                <div class="${colClass} mb-4 fade-in">
                    <div class="card h-100 shadow-sm border-0">
                        <div class="card-header border-bottom py-3 d-flex align-items-center justify-content-between">
                            <h6 class="mb-0 fw-bold d-flex align-items-center">
                                <i class="fas fa-${icon} text-primary me-2 ms-2"></i>
                                ${chart.title}
                            </h6>
                        </div>
                        <div class="card-body p-3">
                            <div class="chart-container">
                                <canvas id="${canvasId}"></canvas>
                            </div>
                        </div>
                    </div>
                </div>`;
            });

            // Allow DOM to render before binding Chart instances
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
                'success': { color: 'success', icon: 'check-circle' },
                'danger': { color: 'danger', icon: 'exclamation-circle' },
                'info': { color: 'info', icon: 'info-circle' },
                'warning': { color: 'warning', icon: 'exclamation-triangle' },
                'primary': { color: 'primary', icon: 'lightbulb' }
            };

            insights.forEach(insight => {
                const styleKey = insight.color || 'primary';
                const style = typeMap[styleKey] || typeMap['primary'];
                const icon = insight.icon || style.icon;
                
                container.innerHTML += `
                <div class="col-md-6 mb-4 fade-in">
                  <div class="insight-card border-start border-${style.color} border-4">
                    <div class="insight-icon bg-${style.color}">
                        <i class="fas fa-${icon}"></i>
                    </div>
                    <div class="insight-content">
                      <div class="insight-category">${insight.category || 'ملاحظة'}</div>
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
            catSelect.innerHTML = '<option value="">الكل</option>';
            for (const [colName, valList] of Object.entries(filters.categories)) {
                valList.forEach(catVal => {
                    catSelect.innerHTML += `<option value="${catVal}">${catVal} (${colName})</option>`;
                });
            }
        }

        const dateFrom = document.getElementById('filter-date-from');
        const dateTo = document.getElementById('filter-date-to');
        if (filters.date) {
            if (dateFrom && filters.date.min) dateFrom.value = filters.date.min;
            if (dateTo && filters.date.max) dateTo.value = filters.date.max;
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
                if (filters.date) {
                    if (dateFrom && filters.date.min) dateFrom.value = filters.date.min;
                    if (dateTo && filters.date.max) dateTo.value = filters.date.max;
                }
                fetchDashboardData();
            });
        }

        setupExportButton();
    }

    function setupExportButton() {
        const exportBtn = document.getElementById('btn-export-excel');
        if (!exportBtn) return;
        
        exportBtn.addEventListener('click', function() {
            const filterForm = document.getElementById('filter-form');
            let queryParams = '';
            if (filterForm) {
                const formData = new FormData(filterForm);
                queryParams = new URLSearchParams(formData).toString();
            }
            const exportUrl = `/analyzer/export/${analysisId}/${queryParams ? '?' + queryParams : ''}`;
            window.location.href = exportUrl;
        });
    }

    // Always setup export button in case filters haven't loaded yet
    setupExportButton();
});
