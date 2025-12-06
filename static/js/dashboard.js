const API_BASE = '/api/v1';
const SESSION_COOKIE_NAME = 'ueba_session';

class UEBADashboard {
    constructor() {
        this.currentEntity = null;
        this.entities = [];
        this.filteredEntities = [];
        this.sparklineCharts = {};
        this.lastRefreshTime = null;
        this.authenticated = false;
        this.sessionToken = null;
    }

    async init() {
        // Check if already authenticated via session cookie
        if (this.getSessionCookie()) {
            this.authenticated = true;
            this.initializeDashboard();
        } else {
            // Show login modal
            this.showLoginModal();
        }

        // Setup event listeners
        this.setupEventListeners();
    }

    getSessionCookie() {
        const name = SESSION_COOKIE_NAME + '=';
        const decodedCookie = decodeURIComponent(document.cookie);
        const cookieArray = decodedCookie.split(';');
        for (let cookie of cookieArray) {
            cookie = cookie.trim();
            if (cookie.indexOf(name) === 0) {
                return cookie.substring(name.length);
            }
        }
        return null;
    }

    setSessionCookie(value, username) {
        // Set session cookie for 24 hours
        const date = new Date();
        date.setTime(date.getTime() + 24 * 60 * 60 * 1000);
        const expires = 'expires=' + date.toUTCString();
        document.cookie = `${SESSION_COOKIE_NAME}=${value};${expires};path=/`;
        
        // Store username in localStorage
        localStorage.setItem('ueba_username', username);
        document.getElementById('username-display').textContent = username;
    }

    clearSessionCookie() {
        document.cookie = `${SESSION_COOKIE_NAME}=;expires=Thu, 01 Jan 1970 00:00:00 UTC;path=/`;
        localStorage.removeItem('ueba_username');
    }

    getAuthHeaders() {
        const sessionToken = this.getSessionCookie();
        if (sessionToken) {
            return {
                'Authorization': `Bearer ${sessionToken}`,
                'Content-Type': 'application/json',
            };
        }
        return { 'Content-Type': 'application/json' };
    }

    showLoginModal() {
        const loginModal = new bootstrap.Modal(document.getElementById('loginModal'), {
            backdrop: 'static',
            keyboard: false,
        });
        loginModal.show();
    }

    setupEventListeners() {
        // Refresh button
        document.getElementById('refresh-btn').addEventListener('click', () => {
            this.refreshData();
        });

        // Entity search
        document.getElementById('entity-search').addEventListener('input', (e) => {
            this.filterEntities(e.target.value);
        });

        // Enter key on login form
        document.getElementById('loginForm').addEventListener('keypress', (e) => {
            if (e.key === 'Enter') {
                handleLogin();
            }
        });
    }

    initializeDashboard() {
        const username = localStorage.getItem('ueba_username');
        if (username) {
            document.getElementById('username-display').textContent = username;
        }
        this.loadEntities();
    }

    async login(username, password) {
        try {
            const response = await fetch('/login', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ username, password }),
            });

            if (!response.ok) {
                const error = await response.json();
                throw new Error(error.detail || 'Login failed');
            }

            const data = await response.json();
            this.setSessionCookie(data.session_token, username);
            this.authenticated = true;

            // Hide login modal and initialize dashboard
            const loginModal = bootstrap.Modal.getInstance(document.getElementById('loginModal'));
            if (loginModal) {
                loginModal.hide();
            }

            this.initializeDashboard();
            return true;
        } catch (error) {
            console.error('Login error:', error);
            document.getElementById('loginError').textContent = error.message;
            document.getElementById('loginError').classList.remove('d-none');
            return false;
        }
    }

    async loadEntities() {
        try {
            document.getElementById('refresh-btn').disabled = true;
            const response = await fetch(`${API_BASE}/entities`, {
                headers: this.getAuthHeaders(),
            });

            if (response.status === 401) {
                this.clearSessionCookie();
                this.authenticated = false;
                this.showLoginModal();
                return;
            }

            if (!response.ok) {
                throw new Error(`Failed to load entities: ${response.statusText}`);
            }

            const data = await response.json();
            this.entities = data.items;
            this.filteredEntities = [...this.entities];
            this.renderEntities();
            this.updateLastRefresh();
        } catch (error) {
            console.error('Error loading entities:', error);
            this.showError('Failed to load entities');
        } finally {
            document.getElementById('refresh-btn').disabled = false;
        }
    }

    filterEntities(searchTerm) {
        const term = searchTerm.toLowerCase();
        this.filteredEntities = this.entities.filter(entity => {
            const name = (entity.display_name || entity.entity_value || '').toLowerCase();
            const value = (entity.entity_value || '').toLowerCase();
            const type = (entity.entity_type || '').toLowerCase();
            return name.includes(term) || value.includes(term) || type.includes(term);
        });
        this.renderEntities();
    }

    renderEntities() {
        const container = document.getElementById('entity-list');
        container.innerHTML = '';

        if (this.filteredEntities.length === 0) {
            container.innerHTML = '<div class="text-muted p-3 text-center">No entities found</div>';
            return;
        }

        this.filteredEntities.forEach(entity => {
            const item = document.createElement('div');
            item.className = 'entity-item';
            if (this.currentEntity && this.currentEntity.entity_id === entity.entity_id) {
                item.classList.add('active');
            }

            const riskLevel = this.getRiskLevel(entity.latest_risk_score);
            const riskBadgeClass = `risk-${riskLevel}`;
            const riskScore = entity.latest_risk_score !== null
                ? (entity.latest_risk_score * 100).toFixed(1)
                : 'N/A';

            let deltaText = '';
            if (entity.delta !== null) {
                const deltaSign = entity.delta >= 0 ? '+' : '';
                deltaText = `Δ ${deltaSign}${(entity.delta * 100).toFixed(1)}%`;
            }

            const triggeredCount = entity.triggered_rules ? entity.triggered_rules.length : 0;

            item.innerHTML = `
                <div class="entity-item-info">
                    <div class="entity-name">${this.escapeHtml(entity.display_name || entity.entity_value)}</div>
                    <div class="entity-type">${entity.entity_type}</div>
                    <div class="entity-stats">
                        <div class="entity-stat">
                            <span class="risk-badge ${riskBadgeClass}">${riskScore}%</span>
                        </div>
                        ${deltaText ? `<div class="entity-stat">${deltaText}</div>` : ''}
                        <div class="entity-stat">
                            <i class="bi bi-exclamation-triangle"></i> ${triggeredCount}
                        </div>
                    </div>
                </div>
            `;

            item.addEventListener('click', () => this.showDetail(entity));
            container.appendChild(item);
        });
    }

    getRiskLevel(score) {
        if (score === null || score === undefined) return 'medium';
        if (score < 0.33) return 'low';
        if (score < 0.66) return 'medium';
        return 'high';
    }

    escapeHtml(text) {
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    }

    async showDetail(entity) {
        this.currentEntity = entity;
        this.renderEntities();

        const detailPanel = document.getElementById('detail-panel');
        const emptyPanel = document.getElementById('empty-panel');
        const detailContent = document.getElementById('detail-content');

        // Show loading state
        detailPanel.classList.add('active');
        emptyPanel.classList.remove('active');
        detailContent.innerHTML = `
            <div class="loading">
                <div class="loading-spinner"></div>
                <p>Loading details...</p>
            </div>
        `;

        try {
            const [historyData, eventsData] = await Promise.all([
                this.loadEntityHistory(entity.entity_id),
                this.loadEntityEvents(entity.entity_id),
            ]);

            detailContent.innerHTML = this.renderDetailPane(entity, historyData, eventsData);
            this.attachDetailListeners();
            
            // Create sparkline if history data exists
            if (historyData && historyData.items && historyData.items.length > 0) {
                this.createSparkline(entity.entity_id, historyData.items);
            }
        } catch (error) {
            console.error('Error loading detail:', error);
            detailContent.innerHTML = `
                <div class="error-message">
                    <i class="bi bi-exclamation-circle"></i>
                    Failed to load entity details
                </div>
            `;
        }
    }

    async loadEntityHistory(entityId) {
        const response = await fetch(`${API_BASE}/entities/${entityId}/history?limit=100`, {
            headers: this.getAuthHeaders(),
        });
        if (!response.ok) {
            throw new Error(`Failed to load history: ${response.statusText}`);
        }
        return await response.json();
    }

    async loadEntityEvents(entityId) {
        const response = await fetch(`${API_BASE}/entities/${entityId}/events?limit=100`, {
            headers: this.getAuthHeaders(),
        });
        if (!response.ok) {
            throw new Error(`Failed to load events: ${response.statusText}`);
        }
        return await response.json();
    }

    renderDetailPane(entity, historyData, eventsData) {
        const riskLevel = this.getRiskLevel(entity.latest_risk_score);
        const riskScore = entity.latest_risk_score !== null
            ? (entity.latest_risk_score * 100).toFixed(1)
            : 'N/A';

        let baselineHtml = '';
        if (entity.baseline_avg !== null && entity.baseline_sigma !== null) {
            const delta = entity.delta !== null ? (entity.delta * 100).toFixed(2) : 'N/A';
            const anomalousFlag = entity.is_anomalous
                ? '<span class="badge bg-danger">Anomalous</span>'
                : '<span class="badge bg-success">Normal</span>';

            baselineHtml = `
                <div class="detail-section">
                    <h4><i class="bi bi-graph-up"></i> Baseline Analysis</h4>
                    <div class="baseline-card">
                        <div class="baseline-item">
                            <div class="baseline-label">Current Risk</div>
                            <div class="baseline-value">${riskScore}%</div>
                        </div>
                        <div class="baseline-item">
                            <div class="baseline-label">Baseline Avg</div>
                            <div class="baseline-value">${(entity.baseline_avg * 100).toFixed(1)}%</div>
                            <div class="baseline-comparison">σ = ${(entity.baseline_sigma * 100).toFixed(2)}%</div>
                        </div>
                        <div class="baseline-item">
                            <div class="baseline-label">Delta (Δ)</div>
                            <div class="baseline-value">${delta}%</div>
                            <div class="baseline-comparison">${anomalousFlag}</div>
                        </div>
                    </div>
                </div>
            `;
        }

        let historyChartHtml = '';
        if (historyData && historyData.items && historyData.items.length > 0) {
            historyChartHtml = `
                <div class="detail-section">
                    <h4><i class="bi bi-graph-up-arrow"></i> Risk History</h4>
                    <div class="history-chart">
                        <canvas id="history-sparkline-${entity.entity_id}"></canvas>
                    </div>
                </div>
            `;
        }

        let triggeredRulesHtml = '';
        if (entity.triggered_rules && entity.triggered_rules.length > 0) {
            const rulesList = entity.triggered_rules
                .map(rule => `<li><i class="bi bi-check-circle"></i> ${this.escapeHtml(rule)}</li>`)
                .join('');
            triggeredRulesHtml = `
                <div class="detail-section">
                    <h4><i class="bi bi-shield-alert"></i> Triggered Rules</h4>
                    <ul class="rules-list">${rulesList}</ul>
                </div>
            `;
        }

        let eventsHtml = '';
        if (eventsData && eventsData.items && eventsData.items.length > 0) {
            const eventRows = eventsData.items
                .map((event, idx) => `
                    <tr>
                        <td>${this.escapeHtml(event.rule_name || 'N/A')}</td>
                        <td>${this.escapeHtml(event.event_type || 'N/A')}</td>
                        <td>${new Date(event.observed_at).toLocaleString()}</td>
                        <td>
                            <button class="btn btn-sm btn-link event-detail-btn p-0" onclick="dashboard.toggleEventDetail(${idx})">
                                <i class="bi bi-chevron-down"></i> View
                            </button>
                        </td>
                    </tr>
                    <tr id="event-detail-${idx}" class="d-none">
                        <td colspan="4">
                            <div class="event-json">${this.escapeHtml(JSON.stringify(event, null, 2))}</div>
                        </td>
                    </tr>
                `)
                .join('');

            eventsHtml = `
                <div class="detail-section">
                    <h4><i class="bi bi-list-check"></i> Normalized Events (${eventsData.items.length})</h4>
                    <table class="table table-sm events-table">
                        <thead>
                            <tr>
                                <th>Rule</th>
                                <th>Type</th>
                                <th>Timestamp</th>
                                <th></th>
                            </tr>
                        </thead>
                        <tbody>
                            ${eventRows}
                        </tbody>
                    </table>
                </div>
            `;
        }

        return `
            <div class="detail-header">
                <div>
                    <h2 class="detail-title">${this.escapeHtml(entity.display_name || entity.entity_value)}</h2>
                    <div class="detail-meta">
                        Type: <strong>${entity.entity_type}</strong> | 
                        Value: <strong>${this.escapeHtml(entity.entity_value)}</strong>
                    </div>
                </div>
            </div>

            <div class="detail-section">
                <h4><i class="bi bi-percent"></i> Risk Score</h4>
                <div class="baseline-card">
                    <div class="baseline-item">
                        <div class="baseline-label">Latest Risk Score</div>
                        <div class="baseline-value">${riskScore}%</div>
                        <span class="risk-badge risk-${riskLevel}" style="margin-top: 0.5rem;">${riskLevel.toUpperCase()}</span>
                    </div>
                </div>
            </div>

            ${baselineHtml}
            ${historyChartHtml}
            ${triggeredRulesHtml}
            ${eventsHtml}
        `;
    }

    attachDetailListeners() {
        // Any additional detail pane event listeners can be added here
    }

    toggleEventDetail(index) {
        const detailRow = document.getElementById(`event-detail-${index}`);
        if (detailRow) {
            detailRow.classList.toggle('d-none');
        }
    }

    createSparkline(entityId, historyItems) {
        // Reverse to get chronological order
        const sortedItems = [...historyItems].reverse();

        const labels = sortedItems.map(item => 
            new Date(item.observed_at).toLocaleDateString('en-US', { month: 'short', day: 'numeric' })
        );

        const data = sortedItems.map(item => item.risk_score * 100);

        const ctx = document.getElementById(`history-sparkline-${entityId}`);
        if (!ctx) return;

        // Destroy previous chart if it exists
        if (this.sparklineCharts[entityId]) {
            this.sparklineCharts[entityId].destroy();
        }

        this.sparklineCharts[entityId] = new Chart(ctx, {
            type: 'line',
            data: {
                labels: labels,
                datasets: [{
                    label: 'Risk Score (%)',
                    data: data,
                    borderColor: '#0d6efd',
                    backgroundColor: 'rgba(13, 110, 253, 0.1)',
                    borderWidth: 2,
                    fill: true,
                    tension: 0.4,
                    pointRadius: 3,
                    pointBackgroundColor: '#0d6efd',
                    pointBorderColor: '#252525',
                    pointBorderWidth: 2,
                    pointHoverRadius: 5,
                }],
            },
            options: {
                responsive: true,
                maintainAspectRatio: true,
                plugins: {
                    legend: {
                        display: true,
                        labels: { color: '#e0e0e0' },
                    },
                    tooltip: {
                        backgroundColor: '#0d0d0d',
                        titleColor: '#fff',
                        bodyColor: '#e0e0e0',
                        borderColor: '#333',
                        borderWidth: 1,
                        padding: 8,
                        titleFont: { size: 12 },
                        bodyFont: { size: 11 },
                    },
                },
                scales: {
                    y: {
                        min: 0,
                        max: 100,
                        grid: { color: '#333' },
                        ticks: { color: '#999' },
                        title: { display: true, text: 'Risk Score (%)', color: '#999' },
                    },
                    x: {
                        grid: { color: '#333' },
                        ticks: { color: '#999' },
                    },
                },
            },
        });
    }

    async refreshData() {
        await this.loadEntities();
        if (this.currentEntity) {
            // Reload current entity details
            const updatedEntity = this.entities.find(e => e.entity_id === this.currentEntity.entity_id);
            if (updatedEntity) {
                await this.showDetail(updatedEntity);
            }
        }
    }

    updateLastRefresh() {
        const now = new Date();
        const timeString = now.toLocaleTimeString('en-US', {
            hour: '2-digit',
            minute: '2-digit',
            second: '2-digit',
            hour12: true,
        });
        document.getElementById('last-refresh').textContent = `Last refresh: ${timeString}`;
    }

    showError(message) {
        // Could show a toast or alert here
        console.error(message);
    }
}

// Global dashboard instance
let dashboard;

async function handleLogin() {
    const username = document.getElementById('loginUsername').value;
    const password = document.getElementById('loginPassword').value;

    if (!username || !password) {
        document.getElementById('loginError').textContent = 'Please enter both username and password';
        document.getElementById('loginError').classList.remove('d-none');
        return;
    }

    document.getElementById('loginError').classList.add('d-none');
    const success = await dashboard.login(username, password);
}

function logout() {
    dashboard.clearSessionCookie();
    dashboard.authenticated = false;
    location.reload();
}

// Initialize dashboard on page load
document.addEventListener('DOMContentLoaded', () => {
    dashboard = new UEBADashboard();
    dashboard.init();
});
