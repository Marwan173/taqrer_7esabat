// Chart manager for creating and managing Chart.js instances
const chartManager = {
    instances: {},
    
    // Default options for all charts (Arabic RTL)
    defaultOptions: {
        responsive: true,
        maintainAspectRatio: false,
        plugins: {
            legend: {
                rtl: true,
                textDirection: 'rtl',
                position: 'bottom',
                labels: {
                    font: { family: 'Cairo', size: 12 },
                    usePointStyle: true,
                    padding: 15,
                }
            },
            tooltip: {
                rtl: true,
                textDirection: 'rtl',
                titleFont: { family: 'Cairo', size: 13 },
                bodyFont: { family: 'Cairo', size: 12 },
                backgroundColor: 'rgba(26, 29, 58, 0.9)',
                cornerRadius: 8,
                padding: 12,
                boxPadding: 6
            }
        },
        scales: {
            x: {
                ticks: { font: { family: 'Cairo', size: 11 } },
                grid: { color: 'rgba(0,0,0,0.05)', drawBorder: false }
            },
            y: {
                ticks: { font: { family: 'Cairo', size: 11 } },
                grid: { color: 'rgba(0,0,0,0.05)', drawBorder: false },
                beginAtZero: true
            }
        }
    },
    
    getOptionsForType: function(type, userOptions = {}) {
        // Deep clone default options to avoid modifying them
        let options = JSON.parse(JSON.stringify(this.defaultOptions));
        
        // Apply type-specific modifications
        if (type === 'doughnut' || type === 'pie') {
            delete options.scales;
            if (type === 'doughnut') {
                options.cutout = '70%';
            }
        } else if (type === 'line') {
            options.elements = {
                line: { tension: 0.4, borderWidth: 3 },
                point: { radius: 4, hoverRadius: 6 }
            };
        } else if (type === 'bar') {
            options.elements = {
                bar: { borderRadius: 4 }
            };
        }
        
        // Merge with user options (simple merge for 1st level, might need deep merge for complex objects)
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
