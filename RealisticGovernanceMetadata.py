import json
import os
import sys
from datetime import datetime, timedelta

# Import canonical model, scoring, and ROI engines
from canonical_metadata_model import map_raw_to_canonical
from governance_scoring_engine import GovernanceScoringEngine
from roi_calculation_engine import ROICalculationEngine

def generate_sample_raw_metadata():
    now = datetime.utcnow()
    
    # 1. ALATION RAW METADATA
    alation_raw = [
        {
            "id": "1001",
            "name": "corporate_customers",
            "type": "Table",
            "description": "Master table containing verified corporate customer details and credit limits.",
            "stewards": [
                {"username": "sarah.steward@company.com", "email": "sarah.steward@company.com"}
            ],
            "popularity": 95,
            "view_count": 1450,
            "size_in_bytes": 1024 * 1024 * 500, # 500 MB
            "last_accessed": (now - timedelta(days=1)).isoformat() + "Z",
            "custom_fields": {
                "PII": "Yes",
                "Classification": "Confidential",
                "Glossary Term": "Corporate Customer"
            },
            "data_quality": {
                "rules_run": 10,
                "rules_passed": 10,
                "last_profiled": (now - timedelta(days=2)).isoformat() + "Z"
            },
            "lineage": {
                "upstream": ["collibra_2001"],
                "downstream": ["alation_1002"]
            }
        },
        {
            "id": "1002",
            "name": "customer_credit_report",
            "type": "Dashboard",
            "description": "BI report summarizing credit ratings and exposures for corporate clients.",
            "stewards": [],
            "popularity": 80,
            "view_count": 950,
            "size_in_bytes": 0,
            "last_accessed": (now - timedelta(days=2)).isoformat() + "Z",
            "custom_fields": {
                "PII": "No",
                "Classification": "Confidential"
            },
            "data_quality": {
                "rules_run": 0,
                "rules_passed": 0
            },
            "lineage": {
                "upstream": ["alation_1001"],
                "downstream": []
            }
        },
        {
            "id": "1003",
            "name": "temp_customer_export_2024",
            "type": "Table",
            "description": "Temporary sandbox export of customers for audit.",
            "stewards": [],
            "popularity": 2,
            "view_count": 5,
            "size_in_bytes": 1024 * 1024 * 1024 * 120, # 120 GB (ROT Candidate)
            "last_accessed": (now - timedelta(days=185)).isoformat() + "Z",
            "custom_fields": {
                "PII": "Yes",
                "Classification": "Public" # Compliance mismatch
            },
            "data_quality": {
                "rules_run": 0,
                "rules_passed": 0
            },
            "lineage": {
                "upstream": [],
                "downstream": []
            }
        }
    ]

    # 2. COLLIBRA RAW METADATA
    collibra_raw = [
        {
            "id": "2001",
            "name": "Staging Customer CRM Data",
            "type": "Database Table",
            "attributes": [
                {"type": "Description", "value": "Landing zone table for CRM customer contact details."},
                {"type": "Data Classification", "value": "Confidential"}
            ],
            "relations": [
                {"type": "Owned By", "target": "CRM Data Team", "role": "Technical Owner", "email": "crm_devs@company.com"},
                {"type": "Associated Glossary Term", "target": "Customer Contact"}
            ],
            "dataQuality": {
                "rulesRun": 5,
                "rulesPassed": 3, # 60% DQ Pass (Quality Risk)
                "lastProfiled": (now - timedelta(days=1)).isoformat() + "Z"
            },
            "usage": {
                "queryCount": 670,
                "userCount": 15,
                "sizeInBytes": 1024 * 1024 * 1024 * 5, # 5 GB
                "lastAccessed": (now - timedelta(hours=4)).isoformat() + "Z"
            }
        },
        {
            "id": "2002",
            "name": "Legacy Marketing Prospects 2021",
            "type": "Database Table",
            "attributes": [
                {"type": "Description", "value": "Old marketing prospect list from 2021 campaigns."}
            ],
            "relations": [], # Missing owner
            "dataQuality": {
                "rulesRun": 0,
                "rulesPassed": 0
            },
            "usage": {
                "queryCount": 0, # ROT
                "userCount": 0,
                "sizeInBytes": 1024 * 1024 * 1024 * 850, # 850 GB
                "lastAccessed": (now - timedelta(days=365)).isoformat() + "Z"
            }
        }
    ]

    # 3. INFORMATICA IDMC RAW METADATA
    informatica_raw = [
        {
            "assetId": "3001",
            "assetName": "FINANCIAL_TRANSACTIONS_FACT",
            "assetType": "Table",
            "description": "Core ledger transactions fact table. High volume financial records.",
            "owners": [
                {"name": "Robert Miller", "role": "Business Owner", "email": "robert.miller@company.com"},
                {"name": "Cloud Data Team", "role": "Technical Owner", "email": "cloud_data@company.com"}
            ],
            "glossaryAssignments": [
                {"termId": "t_101", "termName": "Transaction"},
                {"termId": "t_102", "termName": "Revenue"}
            ],
            "sensitive": False,
            "classification": "Confidential",
            "dqRulesCount": 25,
            "dqRulesPassed": 24, # 96%
            "dqLastRun": (now - timedelta(hours=12)).isoformat() + "Z",
            "lineageInfo": {
                "upstream": ["informatica_3002"],
                "downstream": ["purview_5001"]
            },
            "usageStats": {
                "readsCount": 8500,
                "usersCount": 110,
                "sizeInBytes": 1024 * 1024 * 1024 * 1024 * 4, # 4 TB
                "lastAccessTime": (now - timedelta(minutes=15)).isoformat() + "Z"
            }
        },
        {
            "assetId": "3002",
            "assetName": "TRANSACTIONS_LOG_ARCHIVE_2023",
            "assetType": "File",
            "description": "Raw JSON backup logs of transactions from 2023.",
            "owners": [], # Missing owner
            "glossaryAssignments": [],
            "sensitive": True, # Unclassified PII risk
            "dqRulesCount": 0,
            "usageStats": {
                "readsCount": 0,
                "usersCount": 0,
                "sizeInBytes": 1024 * 1024 * 1024 * 1024 * 18, # 18 TB (ROT)
                "lastAccessTime": (now - timedelta(days=200)).isoformat() + "Z"
            }
        }
    ]

    # 4. ATACCAMA RAW METADATA
    ataccama_raw = [
        {
            "id": "4001",
            "title": "employee_payroll_records",
            "type": "Table",
            "description": "Active employee salary, tax, and bank account information.",
            "owner": "hr_stewards@company.com",
            "terms": ["Employee Salary", "Bank Details"],
            "securityClassification": "Highly Confidential PII",
            "dataQuality": {
                "rulesRun": 30,
                "rulesPassed": 29, # 96.6%
                "profiledDate": (now - timedelta(days=3)).isoformat() + "Z"
            },
            "lineage": {
                "sources": ["ataccama_4002"],
                "targets": []
            },
            "usage": {
                "reads": 150,
                "users": 8,
                "lastRead": (now - timedelta(days=1)).isoformat() + "Z"
            },
            "sizeBytes": 1024 * 1024 * 12 # 12 MB
        },
        {
            "id": "4002",
            "title": "employee_onboarding_raw",
            "type": "Table",
            "description": "Raw details from applicant onboarding forms containing SSN, phone numbers.",
            "owner": "", # Missing owner!
            "terms": [],
            "securityClassification": "", # Unclassified PII!
            "dataQuality": {
                "rulesRun": 4,
                "rulesPassed": 1, # 25% pass rate (low quality risk)
                "profiledDate": (now - timedelta(days=1)).isoformat() + "Z"
            },
            "lineage": {
                "sources": [],
                "targets": ["ataccama_4001"]
            },
            "usage": {
                "reads": 520, # High usage of unclassified, un-owned, low-quality PII
                "users": 24,
                "lastRead": (now - timedelta(hours=2)).isoformat() + "Z"
            },
            "sizeBytes": 1024 * 1024 * 85 # 85 MB
        }
    ]

    # 5. MICROSOFT PURVIEW RAW METADATA
    purview_raw = [
        {
            "guid": "5001",
            "name": "executive_financial_dashboard",
            "typeName": "powerbi_dashboard",
            "attributes": {
                "description": "Executive dashboard visualizing quarterly profits, EBITDA, and forecasts.",
                "qualifiedName": "powerbi://finance/dashboards/exec_financials",
                "sizeInBytes": 0
            },
            "contacts": {
                "Owner": [{"id": "finance_leadership", "info": "cfo_office@company.com"}],
                "Expert": [{"id": "dan.analyst", "info": "dan.analyst@company.com"}]
            },
            "classifications": [
                {"typeName": "Financial.Restricted", "validity": "CONFIRMED"}
            ],
            "meanings": [
                {"displayText": "EBITDA", "termGuid": "t_ebitda"}
            ],
            "dataQuality": {
                "rulesRun": 8,
                "rulesPassed": 5, # 62.5% DQ pass rate on critical dashboard!
                "lastProfiled": (now - timedelta(days=1)).isoformat() + "Z"
            },
            "lineage": {
                "inputs": ["informatica_3001"],
                "outputs": []
            },
            "usage": {
                "queries": 1200,
                "users": 45,
                "lastAccessed": (now - timedelta(hours=1)).isoformat() + "Z"
            }
        },
        {
            "guid": "5002",
            "name": "archive_backup_database_2020",
            "typeName": "azure_synapse_table",
            "attributes": {
                "description": "Database backup file from old system migration in 2020.",
                "qualifiedName": "synapse://archive/backup_2020",
                "sizeInBytes": 1024 * 1024 * 1024 * 1024 * 45 # 45 TB (ROT)
            },
            "contacts": {},
            "classifications": [],
            "meanings": [],
            "dataQuality": {
                "rulesRun": 0,
                "rulesPassed": 0
            },
            "lineage": {
                "inputs": [],
                "outputs": []
            },
            "usage": {
                "queries": 0,
                "users": 0,
                "lastAccessed": (now - timedelta(days=700)).isoformat() + "Z"
            }
        }
    ]

    return {
        "alation": alation_raw,
        "collibra": collibra_raw,
        "informatica_idmc": informatica_raw,
        "ataccama": ataccama_raw,
        "purview": purview_raw
    }

def run_accelerator_demo():
    print("=" * 80)
    print("      AI GOVERNANCE ROI OPTIMIZATION ACCELERATOR - MVP PERFORMANCE DEMO")
    print("=" * 80)

    # 1. Load Raw Metadata
    print("\n[Step 1] Loading sample vendor-specific raw metadata...")
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
        print(tabulate(scored_df[display_cols], headers='keys', tablefmt='psql', showindex=False))
    except ImportError:
        print(scored_df[["asset_id", "name", "source_platform", "governance_health_index"]])

    # Platform Maturity aggregates
    platform_report = scoring_engine.generate_platform_report(scored_df)
    print("\n--- PLATFORM MATURITY REPORT ---")
    try:
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
        print(tabulate(display_roi_df, headers='keys', tablefmt='psql', showindex=False))
    except ImportError:
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
        print(tabulate(platform_roi_display, headers='keys', tablefmt='psql', showindex=False))
    except ImportError:
        print(platform_roi_display)

    # 5. Optimization Recommendations
    print("\n[Step 5] Extracting Actionable AI-Driven Optimization Opportunities...")
    print("\n  1. Redundant, Obsolete, Trivial (ROT) Data Storage Savings Candidates:")
    rot_assets = roi_df[roi_df["is_rot"] == True]
    for _, row in rot_assets.iterrows():
        print(f"     - [{row['source_platform'].upper()}] {row['name']} : Potential annual storage savings: ${row['opportunity_storage_savings']:,.2f}")

    print("\n  2. Urgent Risk Exposures (High-Usage, Sensitive PII/Confidential Assets with Poor Governance):")
    risky_assets = scored_df[(scored_df["security_risk_score"] > 40)]
    for _, row in risky_assets.iterrows():
        print(f"     - [{row['source_platform'].upper()}] {row['name']} (Risk Score: {row['security_risk_score']:.1f}/100) : High exposure. Action: Assign Steward and run DQ rules.")

    print("\n  3. Business Trust Risk (High-Usage Assets with Low Data Quality / No monitoring):")
    low_dq_assets = scored_df[(scored_df["governance_health_index"] < 60) & (scored_df["data_quality_score"] < 70)]
    for _, row in low_dq_assets.iterrows():
        # Find raw query count to explain popularity
        canon_item = next((x for x in canonical_assets if x.asset_id == row["asset_id"]), None)
        queries = canon_item.usage.query_count if canon_item else 0
        dq_score = row["data_quality_score"]
        print(f"     - [{row['source_platform'].upper()}] {row['name']} (DQ Score: {dq_score:.1f}%, monthly queries: {queries}) : Untrusted dataset. Action: Setup validation pipeline.")
    
    print("\n" + "=" * 80)
    print("                       END OF MVP ACCELERATOR DEMO")
    print("=" * 80)

def main():
    # Save the generated json
    metadata = generate_sample_raw_metadata()
    output_path = os.path.join(os.path.dirname(__file__), "sample_governance_metadata.json")
    with open(output_path, "w") as f:
        json.dump(metadata, f, indent=2)
    print(f"Successfully generated/updated mock raw metadata for 5 platforms in '{output_path}'.")

    # If demo argument is passed, or if run as script directly, trigger demo
    if len(sys.argv) > 1 and sys.argv[1] == "--demo" or True: # default run demo for interactive verification
        run_accelerator_demo()

if __name__ == "__main__":
    main()
