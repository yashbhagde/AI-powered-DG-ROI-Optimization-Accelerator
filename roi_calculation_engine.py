from typing import List, Dict, Any
import pandas as pd
from datetime import datetime, timedelta, timezone
from canonical_metadata_model import CanonicalAsset

class ROICalculationEngine:
    def __init__(
        self,
        hourly_analyst_rate: float = 75.0,
        hours_saved_per_search: float = 3.5,
        search_ratio: float = 0.10,          # 10% of query volume triggers a discovery/search context
        storage_cost_per_gb_year: float = 0.24, # $0.02/GB/month = $0.24/GB/year
        cost_per_data_breach: float = 150000.0,  # Estimated penalty/cost per unmitigated compliance asset
        breach_probability_ungoverned: float = 0.05,
        breach_probability_governed: float = 0.002,
        cost_per_dq_incident: float = 15000.0   # Dev debug hours + business decision impact cost
    ):
        self.hourly_analyst_rate = hourly_analyst_rate
        self.hours_saved_per_search = hours_saved_per_search
        self.search_ratio = search_ratio
        self.storage_cost_per_gb_year = storage_cost_per_gb_year
        self.cost_per_data_breach = cost_per_data_breach
        self.breach_probability_ungoverned = breach_probability_ungoverned
        self.breach_probability_governed = breach_probability_governed
        self.cost_per_dq_incident = cost_per_dq_incident

        # Default estimated annual costs for running each governance platform (Licenses + Headcount)
        self.platform_costs = {
            "alation": 120000.0,
            "collibra": 200000.0,
            "informatica_idmc": 250000.0,
            "ataccama": 110000.0,
            "purview": 150000.0
        }

    def calculate_asset_roi(self, asset: CanonicalAsset, scores: Dict[str, float]) -> Dict[str, Any]:
        """Calculates realized and opportunity savings for a single asset."""
        # 1. Operational Savings (Data Discovery Efficiency)
        # Annualized query volume = monthly queries * 12
        annual_queries = asset.usage.query_count * 12
        potential_discovery_searches = annual_queries * self.search_ratio
        
        # Realized Operational Savings based on documentation completeness
        doc_score_pct = scores["documentation_score"] / 100.0
        max_possible_discovery_savings = potential_discovery_searches * self.hours_saved_per_search * self.hourly_analyst_rate
        realized_discovery_savings = max_possible_discovery_savings * doc_score_pct
        opportunity_discovery_savings = max_possible_discovery_savings * (1.0 - doc_score_pct)

        # 2. Storage Savings (ROT Decommissioning)
        # Check if asset is Redundant, Obsolete or Trivial (ROT)
        # Criteria: No usage (query count < 5/month), older than 6 months last accessed, and size > 0
        is_rot = False
        now = datetime.now(timezone.utc)
        if asset.usage.size_in_bytes > 0 and asset.usage.query_count < 5:
            if asset.usage.last_accessed:
                time_delta = now - asset.usage.last_accessed
                if time_delta.days > 180:
                    is_rot = True
            else:
                is_rot = True # No access history, assume unused

        size_in_gb = asset.usage.size_in_bytes / (1024 ** 3)
        potential_storage_savings = size_in_gb * self.storage_cost_per_gb_year
        
        # Realized: We only realize storage savings if we ACTUALLY decommission it.
        # But for reporting, we represent ROT assets as 'Opportunity Storage Savings' 
        # (meaning waste reduction we can achieve). Realized storage savings = 0 until acted upon, 
        # but we track it as active storage waste opportunity.
        realized_storage_savings = 0.0
        opportunity_storage_savings = potential_storage_savings if is_rot else 0.0

        # 3. Data Quality incident avoidance savings
        # Baseline incidents: if unmonitored, we assume a baseline of 4 incidents/year.
        # If monitored: scale incidents based on DQ pass rate.
        # DQ Pass >= 95%: 0 incidents/year
        # DQ Pass 80-95%: 2 incidents/year
        # DQ Pass < 80%: 8 incidents/year (due to noisy/broken feeds)
        
        is_active = asset.usage.query_count > 0
        baseline_incidents = 4.0 if is_active else 0.0
        current_incidents = 0.0
        
        if is_active:
            if asset.data_quality.rules_run == 0:
                current_incidents = baseline_incidents
            else:
                pass_rate = asset.data_quality.pass_rate
                if pass_rate >= 0.95:
                    current_incidents = 0.0
                elif pass_rate >= 0.80:
                    current_incidents = 2.0
                else:
                    current_incidents = 8.0

        # Realized DQ Savings: Incidents avoided compared to the unmonitored baseline (if current is lower)
        realized_dq_incidents_avoided = max(0.0, baseline_incidents - current_incidents)
        realized_dq_savings = realized_dq_incidents_avoided * self.cost_per_dq_incident
        
        # Opportunity DQ Savings: Cost of remaining incidents that could be reduced to 0 (by reaching >= 95% pass rate)
        opportunity_dq_savings = current_incidents * self.cost_per_dq_incident

        # 4. Compliance Risk Savings
        # Assess if asset is sensitive
        sensitive_keywords = ["ssn", "payroll", "salary", "bank", "credit", "phone", "email", "address", "tax", "pii", "phi"]
        is_sensitive = False
        for c in asset.classifications:
            if any(term in c.lower() for term in ["pii", "phi", "confidential", "restricted", "sensitive"]):
                is_sensitive = True
                break
        name_desc = (asset.name + " " + asset.description).lower()
        if any(keyword in name_desc for keyword in sensitive_keywords):
            is_sensitive = True

        realized_risk_savings = 0.0
        opportunity_risk_savings = 0.0

        if is_sensitive:
            # Baseline probability of breach/non-compliance on un-governed asset: 5% (0.05)
            # If asset has owners AND classifications, probability drops by 80% (to 1.0%)
            # If also has active DQ rules, probability drops by 96% (to 0.2%)
            has_owner = len(asset.owners) > 0
            has_classification = len(asset.classifications) > 0
            has_dq = asset.data_quality.rules_run > 0
            
            prob_current = self.breach_probability_ungoverned
            if has_owner and has_classification:
                prob_current = 0.01
                if has_dq:
                    prob_current = self.breach_probability_governed
            elif has_owner or has_classification:
                prob_current = 0.03
                
            # Savings realized so far (difference from raw ungoverned risk)
            risk_prob_avoided = self.breach_probability_ungoverned - prob_current
            realized_risk_savings = risk_prob_avoided * self.cost_per_data_breach
            
            # Opportunity: remaining risk that could be minimized by going to full governance (probability = 0.002)
            opportunity_risk_savings = max(0.0, (prob_current - self.breach_probability_governed) * self.cost_per_data_breach)
        
        total_realized_savings = realized_discovery_savings + realized_storage_savings + realized_dq_savings + realized_risk_savings
        total_opportunity_savings = opportunity_discovery_savings + opportunity_storage_savings + opportunity_dq_savings + opportunity_risk_savings

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
            "total_realized_savings": total_realized_savings,
            "total_opportunity_savings": total_opportunity_savings
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
                "governance_health_index": row["governance_health_index"]
            }

        roi_data = []
        for asset in assets:
            scores = asset_scores_map.get(asset.asset_id, {
                "documentation_score": 0.0,
                "data_quality_score": 0.0,
                "lineage_score": 0.0,
                "security_risk_score": 0.0,
                "governance_health_index": 0.0
            })
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
            "compliance_risk": roi_df["realized_risk_savings"].sum()
        }

        opportunity_breakdown = {
            "productivity_discovery": roi_df["opportunity_discovery_savings"].sum(),
            "storage_cost": roi_df["opportunity_storage_savings"].sum(),
            "data_quality_incident": roi_df["opportunity_dq_savings"].sum(),
            "compliance_risk": roi_df["opportunity_risk_savings"].sum()
        }

        # Calculate program cost dynamically for only the active platforms in the ingested data
        active_platforms = roi_df["source_platform"].unique()
        total_program_cost = sum(self.platform_costs.get(plat, 0.0) for plat in active_platforms)
        
        net_realized_roi = total_realized - total_program_cost
        roi_percentage = (net_realized_roi / total_program_cost) * 100.0 if total_program_cost > 0 else 0.0

        return {
            "total_realized_savings": total_realized,
            "total_opportunity_savings": total_opportunity,
            "realized_breakdown": realized_breakdown,
            "opportunity_breakdown": opportunity_breakdown,
            "total_program_cost": total_program_cost,
            "net_realized_roi": net_realized_roi,
            "realized_roi_percentage": roi_percentage
        }

    def generate_platform_roi_report(self, roi_df: pd.DataFrame) -> pd.DataFrame:
        """Generates an ROI breakdown by platform compared to their operating costs."""
        if roi_df.empty:
            return pd.DataFrame()

        platform_agg = roi_df.groupby("source_platform").agg(
            realized_discovery_savings=("realized_discovery_savings", "sum"),
            realized_storage_savings=("realized_storage_savings", "sum"),
            realized_dq_savings=("realized_dq_savings", "sum"),
            realized_risk_savings=("realized_risk_savings", "sum"),
            total_realized_savings=("total_realized_savings", "sum"),
            opportunity_savings=("total_opportunity_savings", "sum")
        ).reset_index()

        # Add operating costs and compute platform net ROI
        platform_agg["operating_cost"] = platform_agg["source_platform"].map(self.platform_costs).fillna(0.0)
        platform_agg["net_realized_value"] = platform_agg["total_realized_savings"] - platform_agg["operating_cost"]
        platform_agg["realized_roi_pct"] = (platform_agg["net_realized_value"] / platform_agg["operating_cost"]) * 100.0
        
        return platform_agg
