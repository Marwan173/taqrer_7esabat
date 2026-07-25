// Chart manager for creating and managing Chart.js instances with theme awareness
const chartManager = {
    instances: {},
    
    // Curated brand palette matching design system
    colors: [
        '#6366f1', '#10b981', '#0284c7', '#f59e0b', '#ec4899', 
        '#8b5cf6', '#14b8a6', '#f97316', '#3b82f6', '#84cc16'
    ],
    
    getThemeColors: function() {
        const isDark = document.documentElement.getAttribute('data-theme') === 'dark';
        return {
            text: isDark ? '#cbd5e1' : '#475569',
            grid: isDark ? 'rgba(255, 255, 255, 0.08)' : 'rgba(0, 0, 0, 0.06)',
            tooltipBg: isDark ? '#1e293b' : '#0f172a',
            tooltipText: isDark ? '#f8fafc' : '#ffffff'
        };
    },

    getDefaultOptions: function() {
        const theme = this.getThemeColors();
        return {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: {
                    rtl: true,
                    textDirection: 'rtl',
                    position: 'bottom',
                    labels: {
                        font: { family: 'Cairo', size: 12, weight: '600' },
                        color: theme.text,
                        usePointStyle: true,
                        pointStyleWidth: 10,
                        padding: 16,
                    }
                },
                tooltip: {
                    rtl: true,
                    textDirection: 'rtl',
                    titleFont: { family: 'Cairo', size: 13, weight: '700' },
                    bodyFont: { family: 'Cairo', size: 12 },
                    backgroundColor: theme.tooltipBg,
                    titleColor: theme.tooltipText,
                    bodyColor: theme.tooltipText,
                    cornerRadius: 10,
                    padding: 12,
                    boxPadding: 6,
                    elevation: 4
                }
            },
            scales: {
                x: {
                    ticks: { font: { family: 'Cairo', size: 11 }, color: theme.text },
                    grid: { color: theme.grid, drawBorder: false }
                },
                y: {
                    ticks: { font: { family: 'Cairo', size: 11 }, color: theme.text },
                    grid: { color: theme.grid, drawBorder: false },
                    beginAtZero: true
                }
            }
        };
    },
    
    getOptionsForType: function(type, userOptions = {}) {
        let options = this.getDefaultOptions();
        
        if (type === 'doughnut' || type === 'pie') {
            delete options.scales;
            if (type === 'doughnut') {
                options.cutout = '68%';
            }
        } else if (type === 'line') {
            options.elements = {
                line: { tension: 0.4, borderWidth: 3 },
                point: { radius: 3, hoverRadius: 6 }
            };
        } else if (type === 'bar') {
            options.elements = {
                bar: { borderRadius: 6 }
            };
        }
        
        if (userOptions.plugins) {
            Object.assign(options.plugins, userOptions.plugins);
        }
        if (userOptions.scales && options.scales) {
            Object.assign(options.scales, userOptions.scales);
        }
        
        return options;
    },
    
    create: function(canvasId, chartConfig) {
        this.destroy(canvasId);
        
        const canvas = document.getElementById(canvasId);
        if (!canvas) return null;
        
        const mergedOptions = this.getOptionsForType(chartConfig.type, chartConfig.options);
        
        this.instances[canvasId] = new Chart(canvas, {
            type: chartConfig.type,
            data: chartConfig.data,
            options: mergedOptions
        });
        
        return this.instances[canvasId];
    },
    
    updateTheme: function() {
        const theme = this.getThemeColors();
        for (const id in this.instances) {
            const chart = this.instances[id];
            if (chart.options.plugins && chart.options.plugins.legend) {
                chart.options.plugins.legend.labels.color = theme.text;
            }
            if (chart.options.plugins && chart.options.plugins.tooltip) {
                chart.options.plugins.tooltip.backgroundColor = theme.tooltipBg;
                chart.options.plugins.tooltip.titleColor = theme.tooltipText;
                chart.options.plugins.tooltip.bodyColor = theme.tooltipText;
            }
            if (chart.options.scales) {
                if (chart.options.scales.x) {
                    chart.options.scales.x.ticks.color = theme.text;
                    chart.options.scales.x.grid.color = theme.grid;
                }
                if (chart.options.scales.y) {
                    chart.options.scales.y.ticks.color = theme.text;
                    chart.options.scales.y.grid.color = theme.grid;
                }
            }
            chart.update('none');
        }
    },
    
    destroy: function(canvasId) {
        if (this.instances[canvasId]) {
            this.instances[canvasId].destroy();
            delete this.instances[canvasId];
        }
    },
    
    destroyAll: function() {
        for (const id in this.instances) {
            this.destroy(id);
        }
    }
};

window.chartManager = chartManager;
