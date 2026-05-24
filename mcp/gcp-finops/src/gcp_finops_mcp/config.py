import os
from dataclasses import dataclass


@dataclass(frozen=True)
class Config:
    gcp_project_id: str
    bq_billing_dataset: str
    bq_billing_table: str | None
    llm_usage_db_url: str | None
    currency_symbol: str = "$"

    @classmethod
    def from_env(cls) -> "Config":
        project = (
            os.environ.get("GCP_PROJECT_ID")
            or os.environ.get("GOOGLE_CLOUD_PROJECT")
        )
        if not project:
            raise RuntimeError(
                "Set GCP_PROJECT_ID (or GOOGLE_CLOUD_PROJECT) environment "
                "variable to your GCP project ID. This is the project that "
                "owns the billing-export BigQuery dataset."
            )
        return cls(
            gcp_project_id=project,
            bq_billing_dataset=os.environ.get("BQ_BILLING_DATASET", "billing_export"),
            bq_billing_table=os.environ.get("BQ_BILLING_TABLE"),
            llm_usage_db_url=os.environ.get("LLM_USAGE_DB_URL"),
            currency_symbol=os.environ.get("CURRENCY_SYMBOL", "$"),
        )

    @property
    def fully_qualified_table(self) -> str | None:
        if self.bq_billing_table is None:
            return None
        return f"{self.gcp_project_id}.{self.bq_billing_dataset}.{self.bq_billing_table}"
