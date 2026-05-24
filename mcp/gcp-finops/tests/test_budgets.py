from gcp_finops_mcp.tools.budgets import format_budgets


def test_format_budgets_empty():
    result = format_budgets([])
    assert "No budgets" in result


def test_format_budgets_with_data():
    budgets = [
        {
            "name": "Deep Mentor Monthly",
            "amount_usd": 500.00,
            "current_spend_usd": 320.00,
            "pct_used": 64.0,
            "thresholds": ["50%", "90%", "100%"],
        }
    ]
    result = format_budgets(budgets)
    assert "Deep Mentor Monthly" in result
    assert "64.0%" in result
    assert "500.00" in result


def test_format_budgets_no_amount():
    budgets = [
        {
            "name": "Test Budget",
            "amount_usd": None,
            "thresholds": ["80%"],
        }
    ]
    result = format_budgets(budgets)
    assert "not set" in result
    assert "80%" in result
