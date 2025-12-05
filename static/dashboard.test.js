/**
 * Dashboard Frontend Tests
 * 
 * These tests verify that the dashboard HTML contains all required feedback widgets
 * and that the JavaScript properly handles user interactions.
 */

describe('UEBA Dashboard Feedback Widgets', () => {
    let dashboard;
    let mockEntities;

    beforeEach(() => {
        // Create a DOM container for testing
        document.body.innerHTML = `
            <div id="entities-container" class="entity-list"></div>
            <div id="detail-pane" class="detail-pane">
                <span class="close-button" onclick="closeDetail()">&times;</span>
                <div id="detail-content"></div>
            </div>
        `;

        dashboard = new UEBADashboard();
        mockEntities = [
            {
                entity_id: 1,
                entity_type: 'user',
                entity_value: 'user@example.com',
                display_name: 'Test User',
                latest_risk_score: 0.45,
                tp_count: 5,
                fp_count: 2,
                fp_ratio: 0.286,
            },
        ];
    });

    describe('Dashboard Initialization', () => {
        test('should have entities container in DOM', () => {
            const container = document.getElementById('entities-container');
            expect(container).toBeTruthy();
            expect(container.classList.contains('entity-list')).toBe(true);
        });

        test('should have detail pane in DOM', () => {
            const pane = document.getElementById('detail-pane');
            expect(pane).toBeTruthy();
            expect(pane.classList.contains('detail-pane')).toBe(true);
        });

        test('should have close button in detail pane', () => {
            const closeBtn = document.querySelector('.close-button');
            expect(closeBtn).toBeTruthy();
        });
    });

    describe('Entity List Rendering', () => {
        test('should render entity cards with feedback stats', () => {
            dashboard.entities = mockEntities;
            dashboard.renderEntities();

            const cards = document.querySelectorAll('.entity-card');
            expect(cards.length).toBe(1);

            const card = cards[0];
            expect(card.textContent).toContain('Test User');
            expect(card.textContent).toContain('user@example.com');
            expect(card.textContent).toContain('TP: 5');
            expect(card.textContent).toContain('FP: 2');
        });

        test('should display entity with risk level badge', () => {
            dashboard.entities = mockEntities;
            dashboard.renderEntities();

            const card = document.querySelector('.entity-card');
            expect(card.textContent).toContain('45.0%');
            expect(card.querySelector('.risk-badge')).toBeTruthy();
        });

        test('should add click listener to entity cards', () => {
            dashboard.entities = mockEntities;
            dashboard.renderEntities();

            const card = document.querySelector('.entity-card');
            const showDetailSpy = jest.spyOn(dashboard, 'showDetail');

            card.click();
            expect(showDetailSpy).toHaveBeenCalledWith(mockEntities[0]);
        });
    });

    describe('Feedback Form Widgets', () => {
        test('should include feedback form in detail pane', () => {
            const feedbackData = {
                entity_id: 1,
                items: [],
                stats: {
                    tp_count: 5,
                    fp_count: 2,
                    fp_ratio: 0.286,
                },
            };

            const html = dashboard.renderDetailPane(mockEntities[0], feedbackData);
            expect(html).toContain('feedback-form');
            expect(html).toContain('Submit Feedback');
        });

        test('should include TP/FP radio buttons', () => {
            const feedbackData = {
                entity_id: 1,
                items: [],
                stats: {
                    tp_count: 0,
                    fp_count: 0,
                    fp_ratio: 0,
                },
            };

            const html = dashboard.renderDetailPane(mockEntities[0], feedbackData);
            expect(html).toContain('True Positive');
            expect(html).toContain('False Positive');
            expect(html).toContain('type="radio"');
        });

        test('should include notes textarea', () => {
            const feedbackData = {
                entity_id: 1,
                items: [],
                stats: {
                    tp_count: 0,
                    fp_count: 0,
                    fp_ratio: 0,
                },
            };

            const html = dashboard.renderDetailPane(mockEntities[0], feedbackData);
            expect(html).toContain('textarea');
            expect(html).toContain('notes');
            expect(html).toContain('Notes (optional)');
        });

        test('should include submit button', () => {
            const feedbackData = {
                entity_id: 1,
                items: [],
                stats: {
                    tp_count: 0,
                    fp_count: 0,
                    fp_ratio: 0,
                },
            };

            const html = dashboard.renderDetailPane(mockEntities[0], feedbackData);
            expect(html).toContain('submit-button');
            expect(html).toContain('Submit Feedback');
        });
    });

    describe('Feedback Statistics Display', () => {
        test('should display TP count in stats section', () => {
            const feedbackData = {
                entity_id: 1,
                items: [],
                stats: {
                    tp_count: 5,
                    fp_count: 2,
                    fp_ratio: 0.286,
                },
            };

            const html = dashboard.renderDetailPane(mockEntities[0], feedbackData);
            expect(html).toContain('True Positives');
            expect(html).toContain('>5<');
        });

        test('should display FP count in stats section', () => {
            const feedbackData = {
                entity_id: 1,
                items: [],
                stats: {
                    tp_count: 5,
                    fp_count: 2,
                    fp_ratio: 0.286,
                },
            };

            const html = dashboard.renderDetailPane(mockEntities[0], feedbackData);
            expect(html).toContain('False Positives');
            expect(html).toContain('>2<');
        });

        test('should display FP ratio percentage', () => {
            const feedbackData = {
                entity_id: 1,
                items: [],
                stats: {
                    tp_count: 5,
                    fp_count: 2,
                    fp_ratio: 0.286,
                },
            };

            const html = dashboard.renderDetailPane(mockEntities[0], feedbackData);
            expect(html).toContain('FP Ratio');
            expect(html).toContain('28.6%');
        });
    });

    describe('Feedback History Display', () => {
        test('should display recent feedback submissions', () => {
            const feedbackData = {
                entity_id: 1,
                items: [
                    {
                        feedback_id: 1,
                        feedback_type: 'tp',
                        normalized_event_id: null,
                        notes: 'Confirmed attacker behavior',
                        submitted_by: 'analyst1',
                        submitted_at: '2024-01-15T10:30:00Z',
                    },
                ],
                stats: {
                    tp_count: 1,
                    fp_count: 0,
                    fp_ratio: 0,
                },
            };

            const html = dashboard.renderDetailPane(mockEntities[0], feedbackData);
            expect(html).toContain('Recent Submissions');
            expect(html).toContain('feedback-item');
            expect(html).toContain('Confirmed attacker behavior');
            expect(html).toContain('analyst1');
        });

        test('should display message when no feedback exists', () => {
            const feedbackData = {
                entity_id: 1,
                items: [],
                stats: {
                    tp_count: 0,
                    fp_count: 0,
                    fp_ratio: 0,
                },
            };

            const html = dashboard.renderDetailPane(mockEntities[0], feedbackData);
            expect(html).toContain('No feedback submissions yet');
        });

        test('should color-code feedback items by type', () => {
            const item = {
                feedback_id: 1,
                feedback_type: 'fp',
                notes: 'False alarm',
                submitted_by: 'analyst1',
                submitted_at: '2024-01-15T10:30:00Z',
            };

            const html = dashboard.renderFeedbackItem(item);
            expect(html).toContain('feedback-item fp');
            expect(html).toContain('False Positive');
        });
    });

    describe('Form Submission', () => {
        test('should require selecting TP or FP before submission', () => {
            const form = document.createElement('form');
            form.id = 'feedback-form';
            form.innerHTML = `
                <input type="radio" name="feedback_type" value="tp">
                <input type="radio" name="feedback_type" value="fp">
                <textarea name="notes"></textarea>
                <button type="submit">Submit</button>
            `;
            document.body.appendChild(form);

            const statusEl = document.createElement('div');
            statusEl.id = 'feedback-status';
            statusEl.className = 'status-message';
            document.body.appendChild(statusEl);

            const showStatusSpy = jest.spyOn(dashboard, 'showStatus');

            dashboard.currentEntity = mockEntities[0];
            dashboard.handleFeedbackSubmit({
                preventDefault: jest.fn(),
            }, mockEntities[0].entity_id);

            expect(showStatusSpy).toHaveBeenCalledWith(
                'Please select TP or FP',
                'error'
            );
        });

        test('should disable submit button during submission', () => {
            const form = document.createElement('form');
            form.id = 'feedback-form';
            form.innerHTML = `
                <input type="radio" name="feedback_type" value="tp" checked>
                <textarea name="notes"></textarea>
            `;
            document.body.appendChild(form);

            const submitBtn = document.createElement('button');
            submitBtn.id = 'submit-btn';
            document.body.appendChild(submitBtn);

            jest.spyOn(global, 'fetch').mockResolvedValueOnce({
                ok: true,
                json: async () => ({
                    entity_id: 1,
                    items: [],
                    stats: { tp_count: 1, fp_count: 0, fp_ratio: 0 },
                }),
            });

            dashboard.currentEntity = mockEntities[0];
            dashboard.handleFeedbackSubmit(
                { preventDefault: jest.fn() },
                mockEntities[0].entity_id
            );

            expect(submitBtn.disabled).toBe(true);
        });
    });

    describe('Close Detail Pane', () => {
        test('should close detail pane when close button clicked', () => {
            const detailPane = document.getElementById('detail-pane');
            detailPane.classList.add('active');

            closeDetail();

            expect(detailPane.classList.contains('active')).toBe(false);
        });
    });

    describe('Risk Level Classification', () => {
        test('should classify low risk correctly', () => {
            const level = dashboard.getRiskLevel(0.25);
            expect(level).toBe('low');
        });

        test('should classify medium risk correctly', () => {
            const level = dashboard.getRiskLevel(0.5);
            expect(level).toBe('medium');
        });

        test('should classify high risk correctly', () => {
            const level = dashboard.getRiskLevel(0.75);
            expect(level).toBe('high');
        });
    });
});
