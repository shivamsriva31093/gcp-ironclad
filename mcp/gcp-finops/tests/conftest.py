import pytest
from gcp_finops_mcp.config import Config


@pytest.fixture
def test_config():
    return Config(
        gcp_project_id="test-project",
        bq_billing_dataset="test_billing",
        bq_billing_table="gcp_billing_export_v1_TEST",
        llm_usage_db_url=None,
    )
