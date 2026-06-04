from typing import List, Dict, Any, Optional
import pandas as pd
from canonical_metadata_model import CanonicalAsset

class GovernanceScoringEngine:
    def __init__(self, doc_weight: float = 0.3, dq_weight: float = 0.4, lineage_weight: float = 0.2, risk_weight: float = 0.1):
        self.doc_weight = doc_weight
        self.dq_weight = dq_weight
        self.lineage_weight = lineage_weight
        self.risk_weight = risk_weight
        
        # Verify weights sum to 1.0 (approximately)
        assert abs(doc_weight + dq_weight + lineage_weight + risk_weight - 1.0) < 1e-5, "Weights must sum to 1.0"

    def calculate_documentation_score(self, asset: CanonicalAsset) -> float:
        """
        Calculates documentation score between 0 and 100.
        - Has description: +40 points
        - Description length > 50 chars: +10 points (rich documentation)
        - Has owner(s): +30 points
        - Has glossary terms: +20 points
        """
        score = 0.0
        if asset.description and asset.description.strip():
            score += 40.0
            if len(asset.description.strip()) > 50:
                score += 10.0
                
        if asset.owners:
            score += 30.0
            
        if asset.glossary_terms:
            score += 20.0
            
        return score

    def calculate_data_quality_score(self, asset: CanonicalAsset) -> float:
        """
        Calculates data quality score between 0 and 100.
        - If no DQ rules are run: returns 0.0 (Unmonitored)
        - If DQ rules are run: returns pass rate * 100
        """
        if asset.data_quality.rules_run == 0:
            return 0.0
        return asset.data_quality.pass_rate * 100.0

    def calculate_lineage_score(self, asset: CanonicalAsset) -> float:
        """
        Calculates lineage transparency score between 0 and 100.
        - Has upstream lineage: +50 points
        - Has downstream lineage: +50 points
        """
        score = 0.0
        if asset.lineage.upstream_assets:
            score += 50.0
        if asset.lineage.downstream_assets:
            score += 50.0
        return score

    def calculate_security_risk_score(self, asset: CanonicalAsset) -> float:
        """
        Calculates a security/policy risk score between 0 and 100 (where 100 is highest risk).
        Risk is triggered by:
        - Sensitive data indicator (has classification PII/PHI/Confidential or sensitive keywords)
        - If sensitive:
          - No owner: +40 risk points
          - No classification tag (but keywords present): +30 risk points
          - No DQ rules run (blind spot on sensitive data): +30 risk points
          - DQ pass rate < 80%: +20 risk points
        - If not sensitive:
          - No owner: +15 risk points
          - No DQ rules run: +10 risk points
        """
        sensitive_keywords = ["ssn", "payroll", "salary", "bank", "credit", "phone", "email", "address", "tax", "pii", "phi"]
        
        # Check if asset is explicitly classified as sensitive or contains sensitive keywords in description/name
        is_sensitive = False
        for c in asset.classifications:
            if any(term in c.lower() for term in ["pii", "phi", "confidential", "restricted", "sensitive"]):
                is_sensitive = True
                break
                
        name_desc = (asset.name + " " + asset.description).lower()
        if any(keyword in name_desc for keyword in sensitive_keywords):
            is_sensitive = True
            
        risk = 0.0
        if is_sensitive:
            risk += 20.0  # Base risk for holding sensitive data
            
            if not asset.owners:
                risk += 40.0
                
            # Check if it has explicit tags. If it has sensitive keywords but empty classifications list
            if not asset.classifications:
                risk += 20.0
                
            if asset.data_quality.rules_run == 0:
                risk += 20.0
            elif asset.data_quality.pass_rate < 0.8:
                risk += 15.0
        else:
            # Non-sensitive asset risk
            if not asset.owners:
                risk += 15.0
            if asset.data_quality.rules_run == 0:
                risk += 10.0
                
        return min(risk, 100.0)

    def calculate_governance_health_index(self, doc_score: float, dq_score: float, lineage_score: float, risk_score: float) -> float:
        """
        Calculates the unified Governance Health Index (GHI) from 0 to 100.
        GHI = (Doc * W_doc) + (DQ * W_dq) + (Lineage * W_lineage) + ((100 - Risk) * W_risk)
        """
        inverted_risk = 100.0 - risk_score
        ghi = (doc_score * self.doc_weight +
               dq_score * self.dq_weight +
               lineage_score * self.lineage_weight +
               inverted_risk * self.risk_weight)
        return ghi

    def score_asset(self, asset: CanonicalAsset) -> Dict[str, Any]:
        """Scores a single canonical asset and returns a dictionary of scores."""
        doc_score = self.calculate_documentation_score(asset)
        dq_score = self.calculate_data_quality_score(asset)
        lineage_score = self.calculate_lineage_score(asset)
        risk_score = self.calculate_security_risk_score(asset)
        ghi = self.calculate_governance_health_index(doc_score, dq_score, lineage_score, risk_score)
        
        return {
            "asset_id": asset.asset_id,
            "name": asset.name,
            "asset_type": asset.asset_type,
            "source_platform": asset.source_platform,
            "documentation_score": doc_score,
            "data_quality_score": dq_score,
            "lineage_score": lineage_score,
            "security_risk_score": risk_score,
            "governance_health_index": ghi
        }

    def score_all_assets(self, assets: List[CanonicalAsset]) -> pd.DataFrame:
        """Scores a list of assets and returns a pandas DataFrame of results."""
        scored_data = [self.score_asset(asset) for asset in assets]
        return pd.DataFrame(scored_data)

    def generate_platform_report(self, scored_df: pd.DataFrame) -> pd.DataFrame:
        """Aggregates scores by source platform."""
        if scored_df.empty:
            return pd.DataFrame()
            
        platform_report = scored_df.groupby("source_platform").agg(
            total_assets=("asset_id", "count"),
            avg_documentation=("documentation_score", "mean"),
            avg_data_quality=("data_quality_score", "mean"),
            avg_lineage=("lineage_score", "mean"),
            avg_security_risk=("security_risk_score", "mean"),
            avg_ghi=("governance_health_index", "mean")
        ).reset_index()
        
        return platform_report
