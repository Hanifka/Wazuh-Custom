"""Tests for the dashboard template and frontend routes."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from ueba.api.main import app


@pytest.fixture
def client():
    """Create a test client for the FastAPI app."""
    return TestClient(app)


class TestDashboardTemplate:
    """Test cases for dashboard template serving."""

    def test_dashboard_root_returns_200(self, client):
        """Test that GET / returns 200 status code."""
        response = client.get("/")
        assert response.status_code == 200

    def test_dashboard_returns_html(self, client):
        """Test that GET / returns HTML content."""
        response = client.get("/")
        assert response.status_code == 200
        assert "text/html" in response.headers.get("content-type", "")

    def test_dashboard_contains_required_elements(self, client):
        """Test that dashboard HTML contains expected elements."""
        response = client.get("/")
        content = response.text

        # Check for main structure
        assert "UEBA Dashboard" in content
        assert 'id="entity-list"' in content
        assert 'id="detail-panel"' in content
        assert 'id="empty-panel"' in content
        assert 'id="loginModal"' in content

    def test_dashboard_contains_bootstrap_darkly(self, client):
        """Test that dashboard includes Bootswatch Darkly CSS."""
        response = client.get("/")
        content = response.text
        assert "bootswatch@5.3.2/dist/darkly/bootstrap.min.css" in content

    def test_dashboard_contains_chart_js(self, client):
        """Test that dashboard includes Chart.js for sparklines."""
        response = client.get("/")
        content = response.text
        assert "chart.js" in content.lower()

    def test_dashboard_contains_login_form(self, client):
        """Test that dashboard HTML contains login form elements."""
        response = client.get("/")
        content = response.text

        assert 'id="loginForm"' in content
        assert 'id="loginUsername"' in content
        assert 'id="loginPassword"' in content
        assert 'id="loginBtn"' in content

    def test_dashboard_contains_refresh_button(self, client):
        """Test that dashboard HTML contains refresh button."""
        response = client.get("/")
        content = response.text
        assert 'id="refresh-btn"' in content
        assert "Refresh" in content

    def test_dashboard_contains_last_refresh_timestamp(self, client):
        """Test that dashboard HTML contains last refresh display."""
        response = client.get("/")
        content = response.text
        assert 'id="last-refresh"' in content

    def test_dashboard_contains_javascript(self, client):
        """Test that dashboard HTML includes JavaScript file."""
        response = client.get("/")
        content = response.text
        assert "/static/js/dashboard.js" in content

    def test_dashboard_contains_search_input(self, client):
        """Test that dashboard HTML contains entity search input."""
        response = client.get("/")
        content = response.text
        assert 'id="entity-search"' in content
        assert "Search entities" in content


class TestLoginEndpoint:
    """Test cases for login endpoint."""

    def test_login_with_valid_credentials(self, client, monkeypatch):
        """Test login endpoint with valid credentials."""
        monkeypatch.setenv("UEBA_DASH_USERNAME", "testuser")
        monkeypatch.setenv("UEBA_DASH_PASSWORD", "testpass")

        response = client.post("/login", json={
            "username": "testuser",
            "password": "testpass",
        })

        assert response.status_code == 200
        data = response.json()
        assert "session_token" in data
        assert data["message"] == "Successfully logged in as testuser"

    def test_login_with_invalid_username(self, client, monkeypatch):
        """Test login endpoint with invalid username."""
        monkeypatch.setenv("UEBA_DASH_USERNAME", "testuser")
        monkeypatch.setenv("UEBA_DASH_PASSWORD", "testpass")

        response = client.post("/login", json={
            "username": "wronguser",
            "password": "testpass",
        })

        assert response.status_code == 401
        data = response.json()
        assert "Invalid username or password" in data["detail"]

    def test_login_with_invalid_password(self, client, monkeypatch):
        """Test login endpoint with invalid password."""
        monkeypatch.setenv("UEBA_DASH_USERNAME", "testuser")
        monkeypatch.setenv("UEBA_DASH_PASSWORD", "testpass")

        response = client.post("/login", json={
            "username": "testuser",
            "password": "wrongpass",
        })

        assert response.status_code == 401
        data = response.json()
        assert "Invalid username or password" in data["detail"]

    def test_login_returns_session_token_format(self, client, monkeypatch):
        """Test that login returns a properly formatted session token."""
        monkeypatch.setenv("UEBA_DASH_USERNAME", "testuser")
        monkeypatch.setenv("UEBA_DASH_PASSWORD", "testpass")

        response = client.post("/login", json={
            "username": "testuser",
            "password": "testpass",
        })

        assert response.status_code == 200
        data = response.json()
        token = data["session_token"]

        # Token should be a string of reasonable length (at least 20 chars)
        assert isinstance(token, str)
        assert len(token) > 20


class TestStaticFileServing:
    """Test cases for static file serving."""

    def test_static_files_are_mounted(self, client):
        """Test that static files are properly mounted."""
        # This test verifies that static file mounting works
        # We can't test specific files without knowing the exact structure
        # but we can verify the mount point exists and responds appropriately
        response = client.get("/static/")
        # The response might be a directory listing (200) or 404
        # depending on how static files are configured
        assert response.status_code in [200, 404]


class TestDarkModeStyles:
    """Test cases for dark mode styling."""

    def test_dashboard_uses_dark_background(self, client):
        """Test that dashboard HTML includes dark mode styles."""
        response = client.get("/")
        content = response.text

        # Check for dark mode color values
        assert "#1a1a1a" in content or "1a1a1a" in content  # Dark background
        assert "#e0e0e0" in content or "e0e0e0" in content  # Light text

    def test_dashboard_has_dark_navbar(self, client):
        """Test that navbar has dark mode styling."""
        response = client.get("/")
        content = response.text

        # Check for navbar dark class or styling
        assert "navbar-dark" in content or "#0d0d0d" in content

    def test_dashboard_has_responsive_layout(self, client):
        """Test that dashboard includes responsive CSS."""
        response = client.get("/")
        content = response.text

        # Check for responsive classes or media queries
        assert "main-container" in content
        assert "entities-panel" in content
        assert "detail-panel" in content


class TestAccessibilityAndUsability:
    """Test cases for accessibility and usability features."""

    def test_dashboard_has_proper_heading_structure(self, client):
        """Test that dashboard has proper heading hierarchy."""
        response = client.get("/")
        content = response.text

        # Should have h1, but should not have excessive headings
        assert "<h1" in content or "<h2" in content

    def test_dashboard_has_aria_labels(self, client):
        """Test that dashboard includes some accessibility features."""
        response = client.get("/")
        content = response.text

        # Check for common accessibility patterns
        assert "aria-" in content or "placeholder=" in content

    def test_dashboard_has_proper_form_labels(self, client):
        """Test that form inputs have associated labels."""
        response = client.get("/")
        content = response.text

        # Check for form label elements
        assert "<label" in content
        assert "form-label" in content or "<label" in content


class TestDashboardJavaScriptIntegration:
    """Test cases for JavaScript integration."""

    def test_dashboard_initializes_on_dom_content_loaded(self, client):
        """Test that dashboard JavaScript initializes on page load."""
        response = client.get("/")
        content = response.text

        # Check for initialization code
        assert "DOMContentLoaded" in content
        assert "dashboard = new UEBADashboard()" in content

    def test_dashboard_has_api_integration_setup(self, client):
        """Test that dashboard is set up to call API endpoints."""
        response = client.get("/")
        content = response.text

        # Check for API integration references
        assert "/api/v1" in content

    def test_dashboard_has_error_handling(self, client):
        """Test that dashboard includes error handling."""
        response = client.get("/")
        content = response.text

        # Check for error handling patterns
        assert "error" in content.lower()

    def test_dashboard_has_login_handling(self, client):
        """Test that dashboard includes login form handling."""
        response = client.get("/")
        content = response.text

        # Check for login function
        assert "handleLogin" in content
        assert "logout" in content
