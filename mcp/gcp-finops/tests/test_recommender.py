from gcp_finops_mcp.tools.recommender import format_recommendations, RECOMMENDER_TYPES


def test_recommender_types_defined():
    assert len(RECOMMENDER_TYPES) > 0
    assert any("Cost" in v for v in RECOMMENDER_TYPES.values())


def test_format_recommendations_empty():
    result = format_recommendations([])
    assert "No recommendations" in result


def test_format_recommendations_with_data():
    recs = [
        {
            "name": "projects/example-project/locations/us-central1/recommenders/google.cloudsql.instance.IdleRecommender/recommendations/abc123",
            "description": "Cloud SQL instance 'example-db' has been idle for 14 days",
            "recommender_subtype": "IDLE_INSTANCE",
            "priority": "P2",
            "primary_impact_cost_usd": -15.50,
        }
    ]
    result = format_recommendations(recs)
    assert "IDLE_INSTANCE" in result
    assert "15.50" in result


def test_format_recommendations_no_cost():
    recs = [
        {
            "name": "rec1",
            "description": "Some recommendation",
            "recommender_subtype": "MACHINE_TYPE",
            "priority": "P3",
            "primary_impact_cost_usd": None,
        }
    ]
    result = format_recommendations(recs)
    assert "MACHINE_TYPE" in result
    assert "savings" not in result
