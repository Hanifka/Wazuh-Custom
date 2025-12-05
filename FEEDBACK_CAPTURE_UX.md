# Feedback Capture UX - Real-time TP/FP Marking Workflow

## Overview

The Feedback Capture UX feature enables analysts to mark alerts as True Positives (TP) or False Positives (FP) directly from the UEBA Dashboard without page reloads. Feedback is recorded in the `tp_fp_feedback` table and immediately reflected in entity statistics.

## Architecture

### Database Layer

**Table: `tp_fp_feedback`**
- Stores analyst feedback on individual alerts
- Fields:
  - `id` (PK): Auto-incrementing ID
  - `entity_id` (FK): Reference to `entities.id` (CASCADE on delete)
  - `normalized_event_id` (FK, optional): Reference to `normalized_events.id` (SET NULL on delete)
  - `feedback_type` (str): Either "tp" or "fp"
  - `notes` (text, optional): Analyst notes
  - `submitted_by` (str, optional): Username of submitter (from HTTP Basic Auth)
  - `submitted_at` (datetime): Submission timestamp (auto-managed)
  - Standard mixins: `created_at`, `updated_at`, `deleted_at`, `status`

### API Layer

#### Endpoints

##### GET `/api/v1/entities/{entity_id}/feedback`
**Authentication**: Required (HTTP Basic Auth)

Retrieves feedback history and statistics for an entity.

**Query Parameters**:
- `limit` (int, default: 100, max: 1000): Maximum feedback items to return

**Response** (200 OK):
```json
{
  "entity_id": 123,
  "items": [
    {
      "feedback_id": 1,
      "feedback_type": "tp",
      "normalized_event_id": 456,
      "notes": "Confirmed suspicious activity",
      "submitted_by": "analyst1",
      "submitted_at": "2024-01-15T10:30:00Z"
    }
  ],
  "stats": {
    "tp_count": 5,
    "fp_count": 2,
    "fp_ratio": 0.286
  }
}
```

**Error Responses**:
- 401 Unauthorized: Invalid credentials
- 404 Not Found: Entity doesn't exist

##### POST `/api/v1/entities/{entity_id}/feedback`
**Authentication**: Required (HTTP Basic Auth)

Submits new feedback (TP/FP marking) for an entity. Returns updated feedback history and statistics for immediate UI updates.

**Request Body**:
```json
{
  "feedback_type": "tp",
  "normalized_event_id": 456,
  "notes": "Optional notes about this feedback"
}
```

**Request Validation**:
- `feedback_type` (required): Must be exactly "tp" or "fp"
- `normalized_event_id` (optional): If provided, must reference existing non-deleted event
- `notes` (optional): Free-form text

**Response** (201 Created):
```json
{
  "entity_id": 123,
  "items": [
    {
      "feedback_id": 1,
      "feedback_type": "tp",
      "normalized_event_id": 456,
      "notes": "Confirmed suspicious activity",
      "submitted_by": "analyst1",
      "submitted_at": "2024-01-15T10:30:00Z"
    }
  ],
  "stats": {
    "tp_count": 5,
    "fp_count": 2,
    "fp_ratio": 0.286
  }
}
```

**Error Responses**:
- 401 Unauthorized: Invalid credentials
- 404 Not Found: Entity doesn't exist
- 422 Unprocessable Entity:
  - `feedback_type` not in ("tp", "fp")
  - `normalized_event_id` references non-existent event

#### Entity Roster Enhancement

GET `/api/v1/entities` now includes per-entity TP/FP statistics:

```json
{
  "total_count": 100,
  "page": 1,
  "page_size": 50,
  "items": [
    {
      "entity_id": 1,
      "entity_type": "user",
      "entity_value": "user@example.com",
      "display_name": "John Doe",
      "latest_risk_score": 0.45,
      "baseline_avg": 0.35,
      "baseline_sigma": 0.1,
      "delta": 0.1,
      "is_anomalous": false,
      "triggered_rules": ["high_event_volume"],
      "last_observed_at": "2024-01-15T10:30:00Z",
      "tp_count": 5,
      "fp_count": 2,
      "fp_ratio": 0.286
    }
  ]
}
```

### Frontend Layer

#### HTML Dashboard (`static/index.html`)

The dashboard provides:
- **Entity List**: Grid of entity cards showing TP/FP counts
- **Detail Pane**: Side panel with full entity details and feedback form
- **Feedback Statistics**: Display of TP count, FP count, and FP%
- **Feedback Form**: Radio buttons for TP/FP selection + optional notes textarea
- **Feedback History**: Chronologically-ordered list of past submissions
- **Status Messages**: Real-time user feedback (success/error)

#### JavaScript Dashboard (`static/dashboard.js`)

Key features:
- **Lazy Loading**: Fetches entity list and feedback data on demand
- **Optimistic UI Updates**: Updates form state immediately before server response
- **Form Reset**: Clears form after successful submission
- **Status Feedback**: Shows success/error messages with auto-dismiss on success
- **Authentication**: Sends HTTP Basic Auth header with all requests

#### JavaScript Tests (`static/dashboard.test.js`)

Comprehensive DOM and integration tests verify:
- Feedback form widgets are rendered
- Radio buttons for TP/FP selection
- Notes textarea for optional comments
- Statistics display (TP, FP, FP%)
- Feedback history with proper chronological ordering
- Form submission and response handling
- Error handling and validation
- Authentication requirements

### Schema Updates

#### `EntityRosterItem` Schema Extension
```python
tp_count: int = 0              # True positive count
fp_count: int = 0              # False positive count
fp_ratio: float = 0.0          # FP / (TP + FP), range [0.0, 1.0]
```

#### New Schemas
- `FeedbackSubmissionRequest`: Request body for POST feedback
- `FeedbackItem`: Individual feedback submission
- `FeedbackStats`: Aggregated TP/FP statistics
- `FeedbackResponse`: Response body for GET/POST feedback

## Testing

### Backend Tests (`tests/test_api_feedback.py`)

**Coverage**:
- Empty feedback retrieval (no prior submissions)
- 404 error for non-existent entities
- TP feedback submission and validation
- FP feedback submission and validation
- Invalid feedback type rejection
- Optional notes handling
- Feedback with normalized_event_id
- Invalid event_id rejection
- Statistics calculation (TP/FP counts, FP ratio)
- Feedback history ordering (reverse chronological)
- Pagination and limit parameter
- Authentication (required, invalid credentials)
- Entity roster includes feedback stats

### Frontend Tests (`static/dashboard.test.js`)

**Coverage**:
- HTML structure verification (containers, buttons)
- Entity card rendering with feedback stats
- Feedback form widget presence
- TP/FP radio button options
- Notes textarea
- Submit button
- Statistics display accuracy
- Feedback history rendering
- Color-coding by feedback type
- Form submission logic
- Close button functionality
- Risk level classification

## Workflow

### Analyst Perspective

1. **Dashboard Load**: Analyst opens `/` in browser
2. **Entity Selection**: Clicks entity card to open detail pane
3. **Review Stats**: Sees current TP/FP counts and FP%
4. **Mark Feedback**: 
   - Selects TP or FP radio button
   - Optionally adds notes
   - Clicks "Submit Feedback"
5. **Instant Confirmation**: 
   - Form shows success message
   - Statistics update immediately
   - Feedback appears in history list
   - Form resets for next submission

### System Perspective

1. **API Validation**: 
   - Verify entity exists
   - Verify feedback_type is tp/fp
   - Verify normalized_event_id if provided
2. **Persistence**: Create TPFPFeedback record with submitted_by from auth
3. **Response Generation**:
   - Query updated stats for entity
   - Fetch recent feedback history
   - Return FeedbackResponse with stats + items
4. **UI Updates**: Dashboard re-renders statistics and history

## Real-time Feedback Collection

The "real-time" aspects of this workflow:

1. **No Page Reloads**: Feedback submission uses fetch API with optimistic UI
2. **Immediate Stats Update**: FP ratio and counts updated before analyst's eyes
3. **History Display**: New submission appears in feedback list immediately
4. **Chronological Ordering**: Newest submissions appear at top
5. **Form Reset**: Cleared and ready for next submission instantly

## Downstream Integration

The TP/FP statistics enable:
- **Threshold Tuning**: Use FP% to adjust alert thresholds
- **Model Training**: Feedback as labeled data for ML systems
- **Quality Metrics**: Track alert quality per entity/source
- **Analyst Performance**: Monitor feedback patterns over time
- **Alert Suppression**: Auto-suppress entities with >X% FP rate

## Environment Variables

No new environment variables required. Uses existing:
- `UEBA_DASH_USERNAME`: For HTTP Basic Auth validation
- `UEBA_DASH_PASSWORD`: For HTTP Basic Auth validation

## Implementation Details

### Database Efficiency
- Conditional counting in SQLAlchemy using `func.count().filter()`
- Index on `(entity_id, feedback_type)` implicit through model setup
- Soft-delete support through `deleted_at.is_(None)` filters

### API Patterns
- Consistent error responses (404, 401, 422)
- Response models for strict typing and validation
- Authentication via `verify_credentials` dependency injection
- Session management via `get_session` dependency

### Frontend Architecture
- Class-based dashboard (`UEBADashboard`) for state management
- Async/await for clean promise handling
- Form state validation before submission
- Automatic credential injection from hardcoded test values

## Future Enhancements

Potential improvements:
1. **Batch Feedback**: Submit multiple TP/FP marks in single request
2. **Feedback Reasons**: Dropdown of common reasons (vacation, change, etc.)
3. **Revert Feedback**: Allow analysts to undo/delete submissions
4. **Feedback Analytics**: Dashboard showing feedback trends
5. **Role-based Visibility**: Restrict feedback viewing to specific roles
6. **Event Linking**: Link feedback directly to normalized_event records
7. **Audit Trail**: Full history of feedback modifications
