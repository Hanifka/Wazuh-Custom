const API_BASE = '/api/v1';

class UEBADashboard {
    constructor() {
        this.currentEntity = null;
        this.entities = [];
    }

    async init() {
        await this.loadEntities();
    }

    async loadEntities() {
        try {
            const response = await fetch(`${API_BASE}/entities`, {
                headers: this.getAuthHeaders(),
            });
            if (!response.ok) {
                throw new Error(`Failed to load entities: ${response.statusText}`);
            }
            const data = await response.json();
            this.entities = data.items;
            this.renderEntities();
        } catch (error) {
            console.error('Error loading entities:', error);
            this.showError('Failed to load entities');
        }
    }

    renderEntities() {
        const container = document.getElementById('entities-container');
        container.innerHTML = '';

        this.entities.forEach(entity => {
            const card = document.createElement('div');
            card.className = 'entity-card';
            card.innerHTML = `
                <h3>${entity.display_name || entity.entity_value}</h3>
                <p><strong>Type:</strong> ${entity.entity_type}</p>
                <p><strong>Value:</strong> ${entity.entity_value}</p>
                ${entity.latest_risk_score !== null ? `
                    <p>
                        <strong>Risk Score:</strong>
                        <span class="risk-badge ${this.getRiskLevel(entity.latest_risk_score)}">
                            ${(entity.latest_risk_score * 100).toFixed(1)}%
                        </span>
                    </p>
                ` : ''}
                ${entity.tp_count !== undefined ? `
                    <p><strong>TP:</strong> ${entity.tp_count} | <strong>FP:</strong> ${entity.fp_count}</p>
                ` : ''}
            `;
            card.onclick = () => this.showDetail(entity);
            container.appendChild(card);
        });
    }

    getRiskLevel(score) {
        if (score < 0.33) return 'low';
        if (score < 0.66) return 'medium';
        return 'high';
    }

    async showDetail(entity) {
        this.currentEntity = entity;
        const detailPane = document.getElementById('detail-pane');
        const content = document.getElementById('detail-content');

        content.innerHTML = '<div class="loading">Loading...</div>';
        detailPane.classList.add('active');

        try {
            const feedbackData = await this.loadFeedback(entity.entity_id);
            content.innerHTML = this.renderDetailPane(entity, feedbackData);
            this.attachFormListeners(entity.entity_id);
        } catch (error) {
            console.error('Error loading detail:', error);
            content.innerHTML = `<div class="error-message">Failed to load entity details</div>`;
        }
    }

    async loadFeedback(entityId) {
        const response = await fetch(`${API_BASE}/entities/${entityId}/feedback`, {
            headers: this.getAuthHeaders(),
        });
        if (!response.ok) {
            throw new Error(`Failed to load feedback: ${response.statusText}`);
        }
        return await response.json();
    }

    renderDetailPane(entity, feedbackData) {
        const fpsPercentage = (feedbackData.stats.fp_ratio * 100).toFixed(1);

        let html = `
            <h2>${entity.display_name || entity.entity_value}</h2>
            <p><strong>Entity Type:</strong> ${entity.entity_type} | <strong>Value:</strong> ${entity.entity_value}</p>

            <div class="stats-section">
                <h3>Feedback Statistics</h3>
                <div class="stats-grid">
                    <div class="stat-item">
                        <div class="stat-value">${feedbackData.stats.tp_count}</div>
                        <div class="stat-label">True Positives</div>
                    </div>
                    <div class="stat-item">
                        <div class="stat-value">${feedbackData.stats.fp_count}</div>
                        <div class="stat-label">False Positives</div>
                    </div>
                    <div class="stat-item">
                        <div class="stat-value">${fpsPercentage}%</div>
                        <div class="stat-label">FP Ratio</div>
                    </div>
                </div>
            </div>

            <div class="feedback-section">
                <h4>Submit Feedback</h4>
                <div id="feedback-status" class="status-message"></div>
                <form id="feedback-form" class="feedback-form">
                    <div class="feedback-options">
                        <div class="feedback-option">
                            <label>
                                <input type="radio" name="feedback_type" value="tp" required> True Positive (TP)
                            </label>
                        </div>
                        <div class="feedback-option">
                            <label>
                                <input type="radio" name="feedback_type" value="fp" required> False Positive (FP)
                            </label>
                        </div>
                    </div>

                    <div class="form-group">
                        <label for="notes">Notes (optional)</label>
                        <textarea
                            id="notes"
                            name="notes"
                            placeholder="Add any notes about this feedback..."
                        ></textarea>
                    </div>

                    <button type="submit" class="submit-button" id="submit-btn">Submit Feedback</button>
                </form>
            </div>

            <div class="feedback-history">
                <h4>Recent Submissions</h4>
                ${feedbackData.items.length > 0 ? `
                    <div class="feedback-list">
                        ${feedbackData.items.map(item => this.renderFeedbackItem(item)).join('')}
                    </div>
                ` : '<p style="color: #666;">No feedback submissions yet.</p>'}
            </div>
        `;

        return html;
    }

    renderFeedbackItem(item) {
        const submittedAt = new Date(item.submitted_at).toLocaleString();
        const typeClass = item.feedback_type === 'tp' ? 'tp' : 'fp';
        const typeLabel = item.feedback_type === 'tp' ? 'True Positive' : 'False Positive';

        return `
            <div class="feedback-item ${typeClass}">
                <div class="feedback-type ${typeClass}">${typeLabel}</div>
                ${item.notes ? `<div class="feedback-notes">${escapeHtml(item.notes)}</div>` : ''}
                <div class="feedback-meta">
                    Submitted by ${item.submitted_by || 'Unknown'} at ${submittedAt}
                </div>
            </div>
        `;
    }

    attachFormListeners(entityId) {
        const form = document.getElementById('feedback-form');
        form.addEventListener('submit', (e) => this.handleFeedbackSubmit(e, entityId));
    }

    async handleFeedbackSubmit(event, entityId) {
        event.preventDefault();

        const form = document.getElementById('feedback-form');
        const feedback_type = form.querySelector('input[name="feedback_type"]:checked')?.value;
        const notes = form.querySelector('input[name="notes"]')?.value || null;

        if (!feedback_type) {
            this.showStatus('Please select TP or FP', 'error');
            return;
        }

        const submitBtn = document.getElementById('submit-btn');
        submitBtn.disabled = true;

        try {
            const response = await fetch(`${API_BASE}/entities/${entityId}/feedback`, {
                method: 'POST',
                headers: {
                    ...this.getAuthHeaders(),
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({
                    feedback_type,
                    notes: notes || null,
                }),
            });

            if (!response.ok) {
                const error = await response.json();
                throw new Error(error.detail || 'Failed to submit feedback');
            }

            const result = await response.json();

            this.showStatus('Feedback submitted successfully!', 'success');

            form.reset();

            setTimeout(() => {
                this.showDetail(this.currentEntity);
            }, 1000);
        } catch (error) {
            console.error('Error submitting feedback:', error);
            this.showStatus(`Error: ${error.message}`, 'error');
        } finally {
            submitBtn.disabled = false;
        }
    }

    showStatus(message, type) {
        const statusEl = document.getElementById('feedback-status');
        statusEl.textContent = message;
        statusEl.className = `status-message ${type}`;

        if (type === 'success') {
            setTimeout(() => {
                statusEl.className = 'status-message';
            }, 3000);
        }
    }

    showError(message) {
        const container = document.getElementById('entities-container');
        container.innerHTML = `<div class="error-message">${message}</div>`;
    }

    getAuthHeaders() {
        const credentials = btoa('testuser:testpass');
        return {
            'Authorization': `Basic ${credentials}`,
        };
    }
}

function closeDetail() {
    const detailPane = document.getElementById('detail-pane');
    detailPane.classList.remove('active');
}

function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

const dashboard = new UEBADashboard();
document.addEventListener('DOMContentLoaded', () => {
    dashboard.init();
});
