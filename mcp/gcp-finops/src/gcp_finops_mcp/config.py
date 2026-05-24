import os
import re
from dataclasses import dataclass

# BigQuery project / dataset / table identifiers can contain letters, digits,
# underscores, and hyphens — and start with a letter or underscore. We restrict
# to this set so identifiers are safe to interpolate as table references in
# query strings (they cannot be passed as BigQuery query parameters).
_IDENT_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_-]{0,1023}$")


def _valid_ident(value: str | None, name: str) -> str | None:
    """Validate a BigQuery identifier. Returns the value unchanged or raises
    ValueError. `None` passes through (means 'not configured')."""
    if value is None:
        return None
    if not _IDENT_RE.match(value):
        raise ValueError(
            f"Invalid {name}: {value!r}. Must match {_IDENT_RE.pattern} "
            "(letters, digits, underscore, hyphen; starts with letter/underscore)."
        )
    return value


@dataclass(frozen=True)
class Config:
    gcp_project_id: str
    bq_billing_dataset: str
    bq_billing_table: str | None
    llm_usage_db_url: str | None
    currency_symbol: str = "$"

    def __post_init__(self):
        # Validate identifiers on every Config construction (not just from_env).
        # This is defense-in-depth: even if a future caller builds Config()
        # directly with attacker-controlled values, identifiers are checked
        # before they reach a query string.
        _valid_ident(self.gcp_project_id, "gcp_project_id")
        _valid_ident(self.bq_billing_dataset, "bq_billing_dataset")
        _valid_ident(self.bq_billing_table, "bq_billing_table")

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
