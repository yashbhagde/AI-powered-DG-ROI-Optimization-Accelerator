import json
import os
import sys
from datetime import datetime, timedelta

# Import canonical model, scoring, and ROI engines
from canonical_metadata_model import map_raw_to_canonical
from governance_scoring_engine import GovernanceScoringEngine
from roi_calculation_engine import ROICalculationEngine

def generate_sample_raw_metadata(num_assets=None):
    # Delegate to the vendor-specific generator modules
    from alation.mock_alation_generator import generate_alation_metadata
    from collibra.mock_collibra_generator import generate_collibra_metadata
    from purview.mock_purview_generator import generate_purview_metadata
    from ataccama.mock_ataccama_generator import generate_ataccama_metadata
    from informatica.mock_informatica_generator import generate_informatica_metadata
    
    return {
        "alation": generate_alation_metadata(num_assets),
        "collibra": generate_collibra_metadata(num_assets),
        "informatica_idmc": generate_informatica_metadata(num_assets),
        "ataccama": generate_ataccama_metadata(num_assets),
        "purview": generate_purview_metadata(num_assets)
    }

def run_accelerator_demo(raw_metadata=None):
    print("=" * 80)
    print("      AI GOVERNANCE ROI OPTIMIZATION ACCELERATOR - MVP PERFORMANCE DEMO")
    print("=" * 80)

    # 1. Load Raw Metadata
    print("\n[Step 1] Loading sample vendor-specific raw metadata...")
    if raw_metadata is None:
        raw_metadata = generate_sample_raw_metadata()
    print("  Source platforms detected: " + ", ".join(raw_metadata.keys()))
    
    # 2. Map raw to Canonical model
    print("\n[Step 2] Mapping vendor-specific structures to Canonical Metadata Model...")
    canonical_assets = []
    for platform, assets in raw_metadata.items():
        for asset in assets:
            canonical_asset = map_raw_to_canonical(platform, asset)
            canonical_assets.append(canonical_asset)
    print(f"  Successfully ingested and mapped {len(canonical_assets)} assets to vendor-agnostic CanonicalAsset schemas.")

    # 3. Governance Scoring
    print("\n[Step 3] Running Governance Health and Maturity Scoring Engine...")
    scoring_engine = GovernanceScoringEngine()
    scored_df = scoring_engine.score_all_assets(canonical_assets)
    
    # Display individual assets
    try:
        from tabulate import tabulate
        print("\n--- INDIVIDUAL ASSET GOVERNANCE SCORES ---")
        display_cols = ["asset_id", "name", "source_platform", "documentation_score", "data_quality_score", "security_risk_score", "governance_health_index"]
        # Limit rows printed if scaled to prevent console flooding
        if len(scored_df) > 20:
            print(f"Showing top 20 of {len(scored_df)} assets:")
            print(tabulate(scored_df[display_cols].head(20), headers='keys', tablefmt='psql', showindex=False))
        else:
            print(tabulate(scored_df[display_cols], headers='keys', tablefmt='psql', showindex=False))
    except ImportError:
        if len(scored_df) > 20:
            print(scored_df[["asset_id", "name", "source_platform", "governance_health_index"]].head(20))
        else:
            print(scored_df[["asset_id", "name", "source_platform", "governance_health_index"]])

    # Platform Maturity aggregates
    platform_report = scoring_engine.generate_platform_report(scored_df)
    print("\n--- PLATFORM MATURITY REPORT ---")
    try:
        from tabulate import tabulate
        print(tabulate(platform_report, headers='keys', tablefmt='psql', showindex=False))
    except ImportError:
        print(platform_report)

    # 4. ROI Financial Calculations
    print("\n[Step 4] Performing Financial Calculations using the ROI Optimization Engine...")
    roi_engine = ROICalculationEngine()
    roi_df = roi_engine.calculate_catalog_roi(canonical_assets, scored_df)
    
    # Display detailed ROI items
    print("\n--- ASSET FINANCIAL ROI CALCULATIONS ---")
    roi_display_cols = ["asset_id", "name", "source_platform", "is_rot", "is_sensitive", "realized_discovery_savings", "realized_dq_savings", "realized_risk_savings", "total_realized_savings"]
    # Format dollars for display
    display_roi_df = roi_df[roi_display_cols].copy()
    for col in ["realized_discovery_savings", "realized_dq_savings", "realized_risk_savings", "total_realized_savings"]:
        display_roi_df[col] = display_roi_df[col].apply(lambda x: f"${x:,.2f}")
    try:
        from tabulate import tabulate
        if len(display_roi_df) > 20:
            print(f"Showing top 20 of {len(display_roi_df)} assets:")
            print(tabulate(display_roi_df.head(20), headers='keys', tablefmt='psql', showindex=False))
        else:
            print(tabulate(display_roi_df, headers='keys', tablefmt='psql', showindex=False))
    except ImportError:
        if len(display_roi_df) > 20:
            print(display_roi_df.head(20))
        else:
            print(display_roi_df)

    # Program ROI summary
    roi_summary = roi_engine.generate_roi_summary(roi_df)
    print("\n================================================================================")
    print("                     ENTERPRISE GOVERNANCE ROI SUMMARY REPORT")
    print("================================================================================")
    print(f"Total Operating Program Cost:      ${roi_summary['total_program_cost']:,.2f}")
    print(f"Total Realized Governance Value:   ${roi_summary['total_realized_savings']:,.2f}")
    print(f"--------------------------------------------------------------------------------")
    print(f"NET REALIZED PROGRAM VALUE (ROI):  ${roi_summary['net_realized_roi']:,.2f}")
    print(f"REALIZED PROGRAM ROI PERCENTAGE:   {roi_summary['realized_roi_percentage']:.2f}%")
    print(f"================================================================================")
    print(f"Unrealized Opportunity Value:      ${roi_summary['total_opportunity_savings']:,.2f}  <-- Actionable DG Pipeline Potential!")
    print("================================================================================")

    # Platform-by-platform ROI breakdown
    platform_roi_df = roi_engine.generate_platform_roi_report(roi_df)
    print("\n--- PLATFORM FINANCIAL PERFORMANCE BREAKDOWN ---")
    platform_roi_display = platform_roi_df[["source_platform", "total_realized_savings", "opportunity_savings", "operating_cost", "net_realized_value", "realized_roi_pct"]].copy()
    for col in ["total_realized_savings", "opportunity_savings", "operating_cost", "net_realized_value"]:
        platform_roi_display[col] = platform_roi_display[col].apply(lambda x: f"${x:,.2f}")
    platform_roi_display["realized_roi_pct"] = platform_roi_display["realized_roi_pct"].apply(lambda x: f"{x:.2f}%")
    try:
        from tabulate import tabulate
        print(tabulate(platform_roi_display, headers='keys', tablefmt='psql', showindex=False))
    except ImportError:
        print(platform_roi_display)

    # 5. Optimization Recommendations
    print("\n[Step 5] Extracting Actionable AI-Driven Optimization Opportunities...")
    print("\n  1. Redundant, Obsolete, Trivial (ROT) Data Storage Savings Candidates:")
    rot_assets = roi_df[roi_df["is_rot"] == True]
    # Limit print count to prevent console flooding
    rot_show = rot_assets.head(5) if len(rot_assets) > 5 else rot_assets
    for _, row in rot_show.iterrows():
        print(f"     - [{row['source_platform'].upper()}] {row['name']} : Potential annual storage savings: ${row['opportunity_storage_savings']:,.2f}")
    if len(rot_assets) > 5:
        print(f"     ... and {len(rot_assets) - 5} more ROT assets.")

    print("\n  2. Urgent Risk Exposures (High-Usage, Sensitive PII/Confidential Assets with Poor Governance):")
    risky_assets = scored_df[(scored_df["security_risk_score"] > 40)]
    risky_show = risky_assets.head(5) if len(risky_assets) > 5 else risky_assets
    for _, row in risky_show.iterrows():
        print(f"     - [{row['source_platform'].upper()}] {row['name']} (Risk Score: {row['security_risk_score']:.1f}/100) : High exposure. Action: Assign Steward and run DQ rules.")
    if len(risky_assets) > 5:
        print(f"     ... and {len(risky_assets) - 5} more high-risk exposures.")

    print("\n  3. Business Trust Risk (High-Usage Assets with Low Data Quality / No monitoring):")
    low_dq_assets = scored_df[(scored_df["governance_health_index"] < 60) & (scored_df["data_quality_score"] < 70)]
    low_dq_show = low_dq_assets.head(5) if len(low_dq_assets) > 5 else low_dq_assets
    for _, row in low_dq_show.iterrows():
        # Find raw query count to explain popularity
        canon_item = next((x for x in canonical_assets if x.asset_id == row["asset_id"]), None)
        queries = canon_item.usage.query_count if canon_item else 0
        dq_score = row["data_quality_score"]
        print(f"     - [{row['source_platform'].upper()}] {row['name']} (DQ Score: {dq_score:.1f}%, monthly queries: {queries}) : Untrusted dataset. Action: Setup validation pipeline.")
    if len(low_dq_assets) > 5:
        print(f"     ... and {len(low_dq_assets) - 5} more untrusted datasets.")
    
    print("\n" + "=" * 80)
    print("                       END OF MVP ACCELERATOR DEMO")
    print("=" * 80)

def main():
    import argparse
    parser = argparse.ArgumentParser(description="AI Governance ROI Optimization Accelerator - Demo Runner")
    parser.add_argument("--num-assets", type=int, default=None, help="Scale the mock datasets to this number of assets per vendor.")
    args = parser.parse_args()

    # Save the generated json
    metadata = generate_sample_raw_metadata(args.num_assets)
    output_path = os.path.join(os.path.dirname(__file__), "sample_governance_metadata.json")
    with open(output_path, "w") as f:
        json.dump(metadata, f, indent=2)
    print(f"Successfully generated/updated mock raw metadata for 5 platforms in '{output_path}'.")

    # Always trigger demo
    run_accelerator_demo(metadata)

if __name__ == "__main__":
    main()
