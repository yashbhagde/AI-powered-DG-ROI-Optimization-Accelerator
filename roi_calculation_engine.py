from typing import List, Dict, Any
from dataclasses import dataclass
import pandas as pd
from datetime import datetime, timedelta, timezone
from canonical_metadata_model import CanonicalAsset


@dataclass
class TelemetryConfidenceResult:
    total_assets: int
    complete_assets: int
    score: float  # 0.0–1.0 (blended average)
    tier: str  # "high" | "medium" | "low"
    missing_pct: float  # 0–100 float for display
    size_coverage: float
    query_coverage: float
    lineage_coverage: float
    owner_coverage: float

    @property
    def display_pct(self) -> str:
        return f"{self.score * 100:.1f}%"

    @property
    def missing_display_pct(self) -> str:
        return f"{self.missing_pct:.1f}%"


def calculate_tcs(assets: List[CanonicalAsset]) -> TelemetryConfidenceResult:
    """
    Telemetry Confidence Score: blended average of telemetry component coverages across assets.
    An asset has complete telemetry when it has size, query logs, lineage, and at least one owner.
    """
    if not assets:
        return TelemetryConfidenceResult(0, 0, 0.0, "low", 100.0, 0.0, 0.0, 0.0, 0.0)

    complete = 0
    size_ok = 0
    queries_ok = 0
    lineage_ok = 0
    owners_ok = 0

    for asset in assets:
        has_size = asset.usage is not None and asset.usage.size_in_bytes > 0
        has_queries = asset.usage is not None and asset.usage.query_count > 0
        has_lineage = asset.lineage is not None and (
            len(asset.lineage.upstream_assets) > 0 or len(asset.lineage.downstream_assets) > 0
        )
        has_owners = len(asset.owners) > 0

        if has_size:
            size_ok += 1
        if has_queries:
            queries_ok += 1
        if has_lineage:
            lineage_ok += 1
        if has_owners:
            owners_ok += 1

        if has_size and has_queries and has_lineage and has_owners:
            complete += 1

    total = len(assets)
    size_cov = size_ok / total
    queries_cov = queries_ok / total
    lineage_cov = lineage_ok / total
    owners_cov = owners_ok / total

    score = (size_cov + queries_cov + lineage_cov + owners_cov) / 4.0
    missing_pct = (1.0 - score) * 100.0

    if score >= 0.90:
        tier = "high"
    elif score >= 0.50:
        tier = "medium"
    else:
        tier = "low"

    return TelemetryConfidenceResult(
        total_assets=total,
        complete_assets=complete,
        score=score,
        tier=tier,
        missing_pct=missing_pct,
        size_coverage=size_cov,
        query_coverage=queries_cov,
        lineage_coverage=lineage_cov,
        owner_coverage=owners_cov,
    )


class AssetCapabilityEvaluator:
    def __init__(self, asset: CanonicalAsset):
        self.asset = asset

    @property
    def has_usage_telemetry(self) -> bool:
        return self.asset.usage is not None and self.asset.usage.query_count is not None and self.asset.usage.query_count >= 0

    @property
    def has_storage_telemetry(self) -> bool:
        return (
            self.asset.usage is not None and self.asset.usage.size_in_bytes is not None and self.asset.usage.size_in_bytes >= 0
        )

    @property
    def has_dq_telemetry(self) -> bool:
        return (
            self.asset.data_quality is not None
            and self.asset.data_quality.rules_run is not None
            and self.asset.data_quality.rules_run >= 0
        )

    @property
    def has_lineage_telemetry(self) -> bool:
        return self.asset.lineage is not None and (
            self.asset.lineage.upstream_assets is not None or self.asset.lineage.downstream_assets is not None
        )


class ROICalculationEngine:
    def __init__(
        self,
        hourly_analyst_rate: float = 75.0,
        hours_saved_per_search: float = 3.5,
        search_ratio: float = 0.0005,  # 0.05% of query volume triggers a discovery/search context
        storage_cost_per_gb_year: float = 0.24,  # $0.02/GB/month = $0.24/GB/year
        cost_per_data_breach: float = 150000.0,  # Estimated penalty/cost per unmitigated compliance asset
        breach_probability_ungoverned: float = 0.05,
        breach_probability_governed: float = 0.002,
        cost_per_dq_incident: float = 15000.0,  # Dev debug hours + business decision impact cost
        hours_saved_per_rca: float = 6.5,
    ):
        self.hourly_analyst_rate = hourly_analyst_rate
        self.hours_saved_per_search = hours_saved_per_search
        self.search_ratio = search_ratio
        self.storage_cost_per_gb_year = storage_cost_per_gb_year
        self.cost_per_data_breach = cost_per_data_breach
        self.breach_probability_ungoverned = breach_probability_ungoverned
        self.breach_probability_governed = breach_probability_governed
        self.cost_per_dq_incident = cost_per_dq_incident
        self.hours_saved_per_rca = hours_saved_per_rca

        # Default estimated annual costs for running each governance platform (Licenses + Headcount)
        self.platform_costs = {
            "alation": 120000.0,
            "collibra": 200000.0,
            "informatica_idmc": 250000.0,
            "ataccama": 110000.0,
            "purview": 150000.0,
        }

    def calculate_asset_roi(self, asset: CanonicalAsset, scores: Dict[str, float]) -> Dict[str, Any]:
        """Calculates realized and opportunity savings for a single asset with tiered capability checks."""
        evaluator = AssetCapabilityEvaluator(asset)

        # 1. Operational Savings (Data Discovery Efficiency)
        realized_discovery_savings = 0.0
        opportunity_discovery_savings = 0.0
        if evaluator.has_usage_telemetry:
            annual_queries = asset.usage.query_count * 12
            potential_discovery_searches = annual_queries * self.search_ratio
            doc_score_pct = scores.get("documentation_score", 0.0) / 100.0
            max_possible_discovery_savings = (
                potential_discovery_searches * self.hours_saved_per_search * self.hourly_analyst_rate
            )
            realized_discovery_savings = max_possible_discovery_savings * doc_score_pct
            opportunity_discovery_savings = max_possible_discovery_savings * (1.0 - doc_score_pct)

        # 2. Storage Savings (ROT Decommissioning with Dynamic Cloud Storage Tiers)
        is_rot = False
        realized_storage_savings = 0.0
        opportunity_storage_savings = 0.0
        if evaluator.has_storage_telemetry and evaluator.has_usage_telemetry:
            now = datetime.now(timezone.utc)
            if asset.usage.size_in_bytes > 0 and asset.usage.query_count < 5:
                if asset.usage.last_accessed:
                    last_acc = asset.usage.last_accessed
                    if last_acc.tzinfo is None:
                        last_acc = last_acc.replace(tzinfo=timezone.utc)
                    time_delta = now - last_acc
                    if time_delta.days > 180:
                        is_rot = True
                else:
                    is_rot = True

            # Precise storage cost based on cloud storage tier
            tier_pricing = {
                "standard": 0.023 * 12,
                "standard-ia": 0.0125 * 12,
                "glacier": 0.004 * 12,
                "deeparchive": 0.00099 * 12,
            }
            tier_lower = (asset.usage.storage_tier or "standard").lower().replace(" ", "").replace("_", "")
            storage_rate = tier_pricing.get(tier_lower, self.storage_cost_per_gb_year)

            size_in_gb = asset.usage.size_in_bytes / (1024**3)
            potential_storage_savings = size_in_gb * storage_rate
            opportunity_storage_savings = potential_storage_savings if is_rot else 0.0

        # 3. Data Quality incident avoidance savings
        realized_dq_savings = 0.0
        opportunity_dq_savings = 0.0
        is_active = evaluator.has_usage_telemetry and asset.usage.query_count > 0
        baseline_incidents = 0.05 if is_active else 0.0
        current_incidents = 0.0

        if is_active and evaluator.has_dq_telemetry:
            if asset.data_quality.rules_run == 0:
                current_incidents = baseline_incidents
            else:
                pass_rate = asset.data_quality.pass_rate
                if pass_rate >= 0.95:
                    current_incidents = 0.0
                elif pass_rate >= 0.80:
                    current_incidents = 0.02
                else:
                    current_incidents = 0.10

            realized_dq_incidents_avoided = max(0.0, baseline_incidents - current_incidents)
            realized_dq_savings = realized_dq_incidents_avoided * self.cost_per_dq_incident
            opportunity_dq_savings = current_incidents * self.cost_per_dq_incident
        elif is_active:  # Has usage but missing DQ rule telemetry entirely
            opportunity_dq_savings = baseline_incidents * self.cost_per_dq_incident

        # 4. Compliance Risk Savings
        is_sensitive = False
        realized_risk_savings = 0.0
        opportunity_risk_savings = 0.0
        sensitive_keywords = ["ssn", "payroll", "salary", "bank", "credit", "phone", "email", "address", "tax", "pii", "phi"]
        classifications = asset.classifications or []
        for c in classifications:
            if any(term in c.lower() for term in ["pii", "phi", "confidential", "restricted", "sensitive"]):
                is_sensitive = True
                break
        name_desc = ((asset.name or "") + " " + (asset.description or "")).lower()
        if any(keyword in name_desc for keyword in sensitive_keywords):
            is_sensitive = True

        if is_sensitive:
            has_owner = len(asset.owners or []) > 0
            has_classification = len(classifications) > 0
            has_dq = evaluator.has_dq_telemetry and asset.data_quality.rules_run > 0

            prob_current = self.breach_probability_ungoverned
            if has_owner and has_classification:
                prob_current = 0.01
                if has_dq:
                    prob_current = self.breach_probability_governed
            elif has_owner or has_classification:
                prob_current = 0.03

            risk_prob_avoided = self.breach_probability_ungoverned - prob_current
            realized_risk_savings = risk_prob_avoided * self.cost_per_data_breach
            opportunity_risk_savings = max(0.0, (prob_current - self.breach_probability_governed) * self.cost_per_data_breach)

        # 5. Precise Compute Cost Integration (Warehouse credit rates & compute hours)
        realized_compute_savings = 0.0
        opportunity_compute_savings = 0.0
        if evaluator.has_usage_telemetry and asset.usage.query_compute_hours is not None:
            wh_credits = {"x-small": 1.0, "small": 2.0, "medium": 4.0, "large": 8.0, "x-large": 16.0}
            wh_size_lower = (asset.usage.data_warehouse_size or "x-small").lower().replace(" ", "").replace("_", "")
            credits_rate = wh_credits.get(wh_size_lower, 1.0)
            credit_cost = 3.00

            annual_compute_cost = (asset.usage.query_compute_hours or 0.0) * credits_rate * credit_cost * 12
            dq_pass_rate = (
                asset.data_quality.pass_rate if (evaluator.has_dq_telemetry and asset.data_quality.rules_run > 0) else 0.85
            )
            wasted_compute = annual_compute_cost * (1.0 - dq_pass_rate)

            if evaluator.has_dq_telemetry and asset.data_quality.rules_run > 0 and asset.data_quality.pass_rate >= 0.95:
                realized_compute_savings = annual_compute_cost * 0.15
            elif evaluator.has_dq_telemetry and asset.data_quality.rules_run > 0:
                opportunity_compute_savings = wasted_compute
            else:
                opportunity_compute_savings = annual_compute_cost * 0.15

        # 6. Lineage-Driven Root Cause Analysis (RCA) Savings
        realized_rca_savings = 0.0
        opportunity_rca_savings = 0.0
        if evaluator.has_lineage_telemetry:
            has_lineage = asset.lineage and (
                len(asset.lineage.upstream_assets or []) > 0 or len(asset.lineage.downstream_assets or []) > 0
            )
            potential_rca_incidents = current_incidents if current_incidents > 0 else baseline_incidents
            max_possible_rca_savings = potential_rca_incidents * self.hours_saved_per_rca * self.hourly_analyst_rate

            if has_lineage:
                realized_rca_savings = max_possible_rca_savings
            else:
                opportunity_rca_savings = max_possible_rca_savings

        total_realized_savings = (
            realized_discovery_savings
            + realized_storage_savings
            + realized_dq_savings
            + realized_risk_savings
            + realized_compute_savings
            + realized_rca_savings
        )
        total_opportunity_savings = (
            opportunity_discovery_savings
            + opportunity_storage_savings
            + opportunity_dq_savings
            + opportunity_risk_savings
            + opportunity_compute_savings
            + opportunity_rca_savings
        )

        return {
            "asset_id": asset.asset_id,
            "name": asset.name,
            "source_platform": asset.source_platform,
            "is_rot": is_rot,
            "is_sensitive": is_sensitive,
            "realized_discovery_savings": realized_discovery_savings,
            "opportunity_discovery_savings": opportunity_discovery_savings,
            "realized_storage_savings": realized_storage_savings,
            "opportunity_storage_savings": opportunity_storage_savings,
            "realized_dq_savings": realized_dq_savings,
            "opportunity_dq_savings": opportunity_dq_savings,
            "realized_risk_savings": realized_risk_savings,
            "opportunity_risk_savings": opportunity_risk_savings,
            "realized_compute_savings": realized_compute_savings,
            "opportunity_compute_savings": opportunity_compute_savings,
            "realized_rca_savings": realized_rca_savings,
            "opportunity_rca_savings": opportunity_rca_savings,
            "total_realized_savings": total_realized_savings,
            "total_opportunity_savings": total_opportunity_savings,
        }

    def calculate_catalog_roi(self, assets: List[CanonicalAsset], scored_df: pd.DataFrame) -> pd.DataFrame:
        """Calculates ROI metrics for the entire asset catalog."""
        asset_scores_map = {}
        for _, row in scored_df.iterrows():
            asset_scores_map[row["asset_id"]] = {
                "documentation_score": row["documentation_score"],
                "data_quality_score": row["data_quality_score"],
                "lineage_score": row["lineage_score"],
                "security_risk_score": row["security_risk_score"],
                "governance_health_index": row["governance_health_index"],
            }

        roi_data = []
        for asset in assets:
            scores = asset_scores_map.get(
                asset.asset_id,
                {
                    "documentation_score": 0.0,
                    "data_quality_score": 0.0,
                    "lineage_score": 0.0,
                    "security_risk_score": 0.0,
                    "governance_health_index": 0.0,
                },
            )
            roi_data.append(self.calculate_asset_roi(asset, scores))

        return pd.DataFrame(roi_data)

    def generate_roi_summary(self, roi_df: pd.DataFrame) -> Dict[str, Any]:
        """Generates a high-level summary of realized and opportunity savings across the enterprise."""
        if roi_df.empty:
            return {}

        total_realized = roi_df["total_realized_savings"].sum()
        total_opportunity = roi_df["total_opportunity_savings"].sum()

        realized_breakdown = {
            "productivity_discovery": roi_df["realized_discovery_savings"].sum(),
            "storage_cost": roi_df["realized_storage_savings"].sum(),
            "data_quality_incident": roi_df["realized_dq_savings"].sum(),
            "compliance_risk": roi_df["realized_risk_savings"].sum(),
            "compute_optimization": roi_df["realized_compute_savings"].sum(),
        }

        opportunity_breakdown = {
            "productivity_discovery": roi_df["opportunity_discovery_savings"].sum(),
            "storage_cost": roi_df["opportunity_storage_savings"].sum(),
            "data_quality_incident": roi_df["opportunity_dq_savings"].sum(),
            "compliance_risk": roi_df["opportunity_risk_savings"].sum(),
            "compute_optimization": roi_df["opportunity_compute_savings"].sum(),
        }

        # Calculate program cost dynamically for only the active platforms in the ingested data
        active_platforms = roi_df["source_platform"].unique()
        total_program_cost = sum(self.platform_costs.get(plat.lower(), 150000.0) for plat in active_platforms)

        net_realized_roi = total_realized - total_program_cost
        roi_percentage = (net_realized_roi / total_program_cost) * 100.0 if total_program_cost > 0 else 0.0

        return {
            "total_realized_savings": total_realized,
            "total_opportunity_savings": total_opportunity,
            "realized_breakdown": realized_breakdown,
            "opportunity_breakdown": opportunity_breakdown,
            "total_program_cost": total_program_cost,
            "net_realized_roi": net_realized_roi,
            "realized_roi_percentage": roi_percentage,
        }

    def generate_platform_roi_report(self, roi_df: pd.DataFrame) -> pd.DataFrame:
        """Generates an ROI breakdown by platform compared to their operating costs."""
        if roi_df.empty:
            return pd.DataFrame()

        platform_agg = (
            roi_df.groupby("source_platform")
            .agg(
                realized_discovery_savings=("realized_discovery_savings", "sum"),
                realized_storage_savings=("realized_storage_savings", "sum"),
                realized_dq_savings=("realized_dq_savings", "sum"),
                realized_risk_savings=("realized_risk_savings", "sum"),
                realized_compute_savings=("realized_compute_savings", "sum"),
                total_realized_savings=("total_realized_savings", "sum"),
                opportunity_savings=("total_opportunity_savings", "sum"),
            )
            .reset_index()
        )

        # Add operating costs and compute platform net ROI
        platform_agg["operating_cost"] = platform_agg["source_platform"].map(
            lambda x: self.platform_costs.get(x.lower(), 150000.0)
        )
        platform_agg["net_realized_value"] = platform_agg["total_realized_savings"] - platform_agg["operating_cost"]
        platform_agg["realized_roi_pct"] = (platform_agg["net_realized_value"] / platform_agg["operating_cost"]) * 100.0

        return platform_agg
