/**
 * Analytics view — charts and summary statistics.
 */

import { getStats, getTimeline, getTopTopics, getProjects, getOutcomes, getTechnologies } from '../api.js';
import { createTimelineChart, createTopicsChart, createDoughnutChart, createBarChart, destroyAllCharts } from '../components/charts.js';
import { escapeHtml, projectName } from '../app.js';

export async function renderAnalyticsView(container) {
    container.innerHTML = `
        <h1 style="font-size: 1.25rem; font-weight: 600; margin-bottom: 1rem;">Analytics</h1>

        <div id="stats-grid" class="stat-grid"></div>

        <div class="analytics-grid">
            <div class="analytics-card">
                <div class="flex items-center justify-between">
                    <div class="analytics-card-title">Session Timeline</div>
                    <select class="select" id="timeline-granularity" style="max-width: 100px;">
                        <option value="week">Week</option>
                        <option value="day">Day</option>
                        <option value="month">Month</option>
                    </select>
                </div>
                <div style="height: 250px;"><canvas id="chart-timeline"></canvas></div>
            </div>

            <div class="analytics-card">
                <div class="analytics-card-title">Top Topics</div>
                <div style="height: 250px;"><canvas id="chart-topics"></canvas></div>
            </div>

            <div class="analytics-card">
                <div class="analytics-card-title">Projects</div>
                <div style="height: 250px;"><canvas id="chart-projects"></canvas></div>
            </div>

            <div class="analytics-card">
                <div class="analytics-card-title">Outcomes</div>
                <div style="height: 250px;"><canvas id="chart-outcomes"></canvas></div>
            </div>

            <div class="analytics-card">
                <div class="analytics-card-title">Technologies</div>
                <div style="height: 250px;"><canvas id="chart-technologies"></canvas></div>
            </div>
        </div>
    `;

    const statsGrid = document.getElementById('stats-grid');

    // Load stats
    try {
        const stats = await getStats();
        if (stats.error) {
            statsGrid.innerHTML = `<div class="stat-card"><div class="stat-value">--</div><div class="stat-label">No database</div></div>`;
        } else {
            const dbSizeMB = stats.db_size_bytes ? (stats.db_size_bytes / 1024 / 1024).toFixed(1) : '0';
            statsGrid.innerHTML = `
                <div class="stat-card">
                    <div class="stat-value">${stats.sessions || 0}</div>
                    <div class="stat-label">Sessions</div>
                </div>
                <div class="stat-card">
                    <div class="stat-value">${stats.messages || 0}</div>
                    <div class="stat-label">Messages</div>
                </div>
                <div class="stat-card">
                    <div class="stat-value">${stats.code_snippets || 0}</div>
                    <div class="stat-label">Code Snippets</div>
                </div>
                <div class="stat-card">
                    <div class="stat-value">${stats.topics || 0}</div>
                    <div class="stat-label">Topics</div>
                </div>
                <div class="stat-card">
                    <div class="stat-value">${dbSizeMB} MB</div>
                    <div class="stat-label">DB Size</div>
                </div>
            `;
        }
    } catch {
        statsGrid.innerHTML = '<p class="text-muted text-sm">Could not load stats</p>';
    }

    // Load all charts concurrently
    async function loadTimeline(granularity = 'week') {
        try {
            const data = await getTimeline(granularity);
            createTimelineChart('chart-timeline', data.data || []);
        } catch {
            // Silently fail for individual charts
        }
    }

    const chartLoads = [
        loadTimeline('week'),
        (async () => {
            try {
                const data = await getTopTopics();
                createTopicsChart('chart-topics', data.data || []);
            } catch { /* skip */ }
        })(),
        (async () => {
            try {
                const data = await getProjects();
                const items = data.data || [];
                createDoughnutChart(
                    'chart-projects',
                    items.map(d => projectName(d.project_path)),
                    items.map(d => d.count),
                );
            } catch { /* skip */ }
        })(),
        (async () => {
            try {
                const data = await getOutcomes();
                const items = data.data || [];
                createDoughnutChart(
                    'chart-outcomes',
                    items.map(d => d.outcome),
                    items.map(d => d.count),
                );
            } catch { /* skip */ }
        })(),
        (async () => {
            try {
                const data = await getTechnologies();
                const items = data.data || [];
                createBarChart(
                    'chart-technologies',
                    items.map(d => d.technology),
                    items.map(d => d.count),
                    'Sessions',
                );
            } catch { /* skip */ }
        })(),
    ];

    await Promise.allSettled(chartLoads);

    // Timeline granularity change
    document.getElementById('timeline-granularity')?.addEventListener('change', (e) => {
        loadTimeline(e.target.value);
    });

    // Cleanup charts on view exit
    return () => {
        destroyAllCharts();
    };
}
