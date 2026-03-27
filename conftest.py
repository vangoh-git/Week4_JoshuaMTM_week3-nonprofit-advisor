"""
Shared test fixtures for the Nonprofit Advisor eval suite.
"""

import pytest


@pytest.fixture
def sample_org_profile():
    """Standard test organization profile."""
    return {
        "org_name": "Hope Community Center",
        "budget_tier": "Under $5M",
        "staff_count": "35",
        "cause_area": "Community Services",
        "current_tech": "Google Workspace, Spreadsheets",
        "pain_points": "No CRM, security concerns, interested in AI",
        "it_capacity": "No dedicated IT staff, IT-savvy staff",
    }


@pytest.fixture
def large_org_profile():
    """Large organization profile for budget-sensitive testing."""
    return {
        "org_name": "National Health Foundation",
        "budget_tier": "Over $100M",
        "staff_count": "500",
        "cause_area": "Health & Human Services",
        "current_tech": "Microsoft 365, Salesforce, Zoom",
        "pain_points": "HIPAA compliance, data governance",
        "it_capacity": "IT team, Fractional CISO",
    }
