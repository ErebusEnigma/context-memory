/**
 * Chart.js wrapper functions for analytics.
 */

const chartInstances = new Map();

function getCtx(canvasId) {
    return document.getElementById(canvasId)?.getContext('2d');
}

function destroyChart(canvasId) {
    if (chartInstances.has(canvasId)) {
        chartInstances.get(canvasId).destroy();
        chartInstances.delete(canvasId);
    }
}

function getColors(count) {
    const palette = [
        '#58a6ff', '#3fb950', '#d29922', '#f85149', '#bc8cff',
        '#79c0ff', '#56d364', '#e3b341', '#ff7b72', '#d2a8ff',
        '#a5d6ff', '#7ee787', '#f0c846', '#ffa198', '#e8d5ff',
    ];
    const result = [];
    for (let i = 0; i < count; i++) {
        result.push(palette[i % palette.length]);
    }
    return result;
}

function getChartDefaults() {
    const style = getComputedStyle(document.documentElement);
    return {
        textColor: style.getPropertyValue('--text-secondary').trim() || '#8b949e',
        gridColor: style.getPropertyValue('--border-light').trim() || '#21262d',
    };
}

export function createTimelineChart(canvasId, data) {
    destroyChart(canvasId);
    const ctx = getCtx(canvasId);
    if (!ctx) return;

    const defaults = getChartDefaults();
    const chart = new Chart(ctx, {
        type: 'bar',
        data: {
            labels: data.map(d => d.period),
            datasets: [
                {
                    label: 'Manual',
                    data: data.map(d => d.manual_count || 0),
                    backgroundColor: '#58a6ff',
                },
                {
                    label: 'Auto-save',
                    data: data.map(d => d.auto_count || 0),
                    backgroundColor: '#30363d',
                },
            ],
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: { legend: { labels: { color: defaults.textColor } } },
            scales: {
                x: {
                    stacked: true,
                    ticks: { color: defaults.textColor, maxTicksLimit: 12 },
                    grid: { color: defaults.gridColor },
                },
                y: {
                    stacked: true,
                    beginAtZero: true,
                    ticks: { color: defaults.textColor, stepSize: 1 },
                    grid: { color: defaults.gridColor },
                },
            },
        },
    });
    chartInstances.set(canvasId, chart);
}

export function createTopicsChart(canvasId, data) {
    destroyChart(canvasId);
    const ctx = getCtx(canvasId);
    if (!ctx) return;

    const defaults = getChartDefaults();
    const colors = getColors(data.length);
    const chart = new Chart(ctx, {
        type: 'bar',
        data: {
            labels: data.map(d => d.topic),
            datasets: [{
                label: 'Sessions',
                data: data.map(d => d.count),
                backgroundColor: colors,
            }],
        },
        options: {
            indexAxis: 'y',
            responsive: true,
            maintainAspectRatio: false,
            plugins: { legend: { display: false } },
            scales: {
                x: {
                    beginAtZero: true,
                    ticks: { color: defaults.textColor, stepSize: 1 },
                    grid: { color: defaults.gridColor },
                },
                y: {
                    ticks: { color: defaults.textColor },
                    grid: { display: false },
                },
            },
        },
    });
    chartInstances.set(canvasId, chart);
}

export function createDoughnutChart(canvasId, labels, values) {
    destroyChart(canvasId);
    const ctx = getCtx(canvasId);
    if (!ctx) return;

    const defaults = getChartDefaults();
    const colors = getColors(labels.length);
    const chart = new Chart(ctx, {
        type: 'doughnut',
        data: {
            labels: labels,
            datasets: [{
                data: values,
                backgroundColor: colors,
                borderWidth: 0,
            }],
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: {
                    position: 'bottom',
                    labels: { color: defaults.textColor, padding: 12 },
                },
            },
        },
    });
    chartInstances.set(canvasId, chart);
}

export function createBarChart(canvasId, labels, values, label = 'Count') {
    destroyChart(canvasId);
    const ctx = getCtx(canvasId);
    if (!ctx) return;

    const defaults = getChartDefaults();
    const colors = getColors(labels.length);
    const chart = new Chart(ctx, {
        type: 'bar',
        data: {
            labels: labels,
            datasets: [{
                label: label,
                data: values,
                backgroundColor: colors,
            }],
        },
        options: {
            indexAxis: 'y',
            responsive: true,
            maintainAspectRatio: false,
            plugins: { legend: { display: false } },
            scales: {
                x: {
                    beginAtZero: true,
                    ticks: { color: defaults.textColor, stepSize: 1 },
                    grid: { color: defaults.gridColor },
                },
                y: {
                    ticks: { color: defaults.textColor },
                    grid: { display: false },
                },
            },
        },
    });
    chartInstances.set(canvasId, chart);
}

export function destroyAllCharts() {
    for (const [id, chart] of chartInstances) {
        chart.destroy();
    }
    chartInstances.clear();
}
