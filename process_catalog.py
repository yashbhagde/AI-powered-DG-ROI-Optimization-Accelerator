import argparse
import json
import os
import sys
import pandas as pd
from tabulate import tabulate

from canonical_metadata_model import map_raw_to_canonical
from governance_scoring_engine import GovernanceScoringEngine
from roi_calculation_engine import ROICalculationEngine

def main():
    parser = argparse.ArgumentParser(
        description="Process raw data governance metadata from a single platform, map to canonical model, and run scoring & ROI analysis."
    )
    parser.add_argument(
        "--platform",
        type=str,
        required=True,
        choices=["alation", "collibra", "informatica_idmc", "ataccama", "purview"],
        help="The source platform/vendor of the metadata (e.g., alation, collibra)."
    )
    parser.add_argument(
        "--input",
        type=str,
        required=True,
        help="Path to the JSON file containing the raw metadata (a list of asset objects or a single asset object)."
    )
    parser.add_argument(
        "--output-dir",
        type=str,
        default=None,
        help="Directory to save the analysis reports (scores.csv and roi.csv). If not specified, reports won't be saved."
    )
    
    args = parser.parse_args()

    # 1. Load Raw JSON Metadata
    if not os.path.exists(args.input):
        print(f"Error: Input file '{args.input}' does not exist.", file=sys.stderr)
        sys.exit(1)
        
    try:
        with open(args.input, "r") as f:
            raw_data = json.load(f)
    except json.JSONDecodeError as e:
        print(f"Error: Failed to parse input file '{args.input}' as JSON. Details: {e}", file=sys.stderr)
        sys.exit(1)

    # Standardize input to list of dicts
    if isinstance(raw_data, dict):
        # Check if they nested it under a platform key or if it's a single asset
        if args.platform in raw_data and isinstance(raw_data[args.platform], list):
            raw_assets = raw_data[args.platform]
        elif "results" in raw_data and isinstance(raw_data["results"], list):
            raw_assets = raw_data["results"]
        else:
            raw_assets = [raw_data]

    elif isinstance(raw_data, list):
        raw_assets = raw_data
    else:
        print("Error: Input JSON must be either a list of assets or a single asset object.", file=sys.stderr)
        sys.exit(1)

    print("=" * 80)
    print(f"Processing {len(raw_assets)} assets from platform: '{args.platform.upper()}'")
    print("=" * 80)

    # 2. Map to Canonical Model
    canonical_assets = []
    failed_mappings = 0
    for idx, raw_asset in enumerate(raw_assets):
        try:
            canonical_asset = map_raw_to_canonical(args.platform, raw_asset)
            canonical_assets.append(canonical_asset)
        except Exception as e:
            failed_mappings += 1
            print(f"Warning: Failed to map asset at index {idx}. Error: {e}", file=sys.stderr)

    if not canonical_assets:
        print("Error: No assets were successfully mapped to the canonical model. Exiting.", file=sys.stderr)
        sys.exit(1)

    print(f"Successfully mapped {len(canonical_assets)} assets to CanonicalAsset model (failed: {failed_mappings}).")

    # 3. Governance Scoring
    print("\nCalculating Governance Health and Risk Scores...")
    scoring_engine = GovernanceScoringEngine()
    scored_df = scoring_engine.score_all_assets(canonical_assets)

    # Display Scores
    print("\n--- GOVERNANCE SCORES & RISK PROFILE ---")
    score_cols = ["asset_id", "name", "documentation_score", "data_quality_score", "security_risk_score", "governance_health_index"]
    try:
        print(tabulate(scored_df[score_cols], headers='keys', tablefmt='psql', showindex=False))
    except ImportError:
        print(scored_df[score_cols])

    # 4. ROI Financial Calculations
    print("\nCalculating Financial ROI and Opportunity Savings...")
    roi_engine = ROICalculationEngine()
    
    # Customize cost for single platform if we want, or use defaults
    roi_df = roi_engine.calculate_catalog_roi(canonical_assets, scored_df)

    # Display ROI table
    print("\n--- FINANCIAL SAVINGS BREAKDOWN ---")
    roi_cols = ["asset_id", "name", "is_rot", "is_sensitive", "realized_discovery_savings", "realized_dq_savings", "realized_risk_savings", "realized_compute_savings", "total_realized_savings", "total_opportunity_savings"]
    display_roi_df = roi_df[roi_cols].copy()
    
    # Format currency for print
    for col in ["realized_discovery_savings", "realized_dq_savings", "realized_risk_savings", "realized_compute_savings", "total_realized_savings", "total_opportunity_savings"]:
        display_roi_df[col] = display_roi_df[col].apply(lambda x: f"${x:,.2f}")
        
    try:
        print(tabulate(display_roi_df, headers='keys', tablefmt='psql', showindex=False))
    except ImportError:
        print(display_roi_df)

    # Single-platform Summary
    total_realized = roi_df["total_realized_savings"].sum()
    total_opportunity = roi_df["total_opportunity_savings"].sum()
    operating_cost = roi_engine.platform_costs.get(args.platform, 0.0)
    net_realized = total_realized - operating_cost
    roi_pct = (net_realized / operating_cost * 100.0) if operating_cost > 0 else 0.0

    print("\n" + "=" * 80)
    print(f"                     {args.platform.upper()} GOVERNANCE FINANCIAL SUMMARY")
    print("=" * 80)
    print(f"Annual Operating cost (License + Headcount): ${operating_cost:,.2f}")
    print(f"Total Realized Governance Value:             ${total_realized:,.2f}")
    print(f"--------------------------------------------------------------------------------")
    print(f"NET REALIZED PROGRAM VALUE (ROI):            ${net_realized:,.2f}")
    print(f"REALIZED PROGRAM ROI PERCENTAGE:             {roi_pct:.2f}%")
    print(f"================================================================================")
    print(f"Unrealized Opportunity Value:                ${total_opportunity:,.2f}")
    print("================================================================================")

    # 5. Save Outputs
    if args.output_dir:
        os.makedirs(args.output_dir, exist_ok=True)
        scores_csv = os.path.join(args.output_dir, f"{args.platform}_governance_scores.csv")
        roi_csv = os.path.join(args.output_dir, f"{args.platform}_governance_roi.csv")
        
        scored_df.to_csv(scores_csv, index=False)
        roi_df.to_csv(roi_csv, index=False)
        
        print(f"\n[Saved] Governance scores saved to: {scores_csv}")
        print(f"[Saved] ROI calculations saved to: {roi_csv}")
    print("=" * 80)

if __name__ == "__main__":
    main()
