import json
import os
from datetime import datetime, timedelta

def generate_informatica_metadata(num_assets=None):
    now = datetime.utcnow()
    
    # Rich mock data representing Informatica IDMC assets.
    # Mimics assetId, assetName, assetType, description, owners, glossaryAssignments, sensitive,
    # classification, dqRulesCount, dqRulesPassed, dqLastRun, lineageInfo, and usageStats.
    informatica_export = [
        # 1. Fact Table Asset: FINANCIAL_TRANSACTIONS_FACT
        {
            "assetId": "3001",
            "assetName": "FINANCIAL_TRANSACTIONS_FACT",
            "assetType": "Table",
            "description": "Core ledger transactions fact table. High volume financial records mapping credit and debit exposures.",
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
            "dqRulesPassed": 24, # 96% pass rate
            "dqLastRun": (now - timedelta(hours=12)).isoformat() + "Z",
            "lineageInfo": {
                "upstream": ["informatica_3003"], # Fed by core database
                "downstream": ["purview_5001"] # Ingested into Purview PowerBI dashboard
            },
            "usageStats": {
                "readsCount": 8500,
                "usersCount": 110,
                "sizeInBytes": 1024 * 1024 * 1024 * 1024 * 4, # 4 TB
                "lastAccessTime": (now - timedelta(minutes=15)).isoformat() + "Z"
            }
        },
        # 2. ROT File Asset: TRANSACTIONS_LOG_ARCHIVE_2023
        {
            "assetId": "3002",
            "assetName": "TRANSACTIONS_LOG_ARCHIVE_2023",
            "assetType": "File",
            "description": "Raw JSON backup logs of payroll and credit transactions from 2023. Restored temporarily for audit, but never deleted.",
            "owners": [], # No owner (risk!)
            "glossaryAssignments": [],
            "sensitive": True, # Sensitive indicators trigger classification risk when unowned
            "dqRulesCount": 0,
            "usageStats": {
                "readsCount": 0, # ROT candidate
                "usersCount": 0,
                "sizeInBytes": 1024 * 1024 * 1024 * 1024 * 18, # 18 TB (huge waste)
                "lastAccessTime": (now - timedelta(days=200)).isoformat() + "Z"
            }
        },
        # 3. Database Schema Asset: CORE_FINANCE_DB
        {
            "assetId": "3003",
            "assetName": "CORE_FINANCE_DB",
            "assetType": "Database Schema",
            "description": "Main Oracle database schema staging financial assets.",
            "owners": [
                {"name": "Robert Miller", "role": "Business Owner", "email": "robert.miller@company.com"}
            ],
            "glossaryAssignments": [],
            "sensitive": False,
            "classification": "Internal",
            "dqRulesCount": 10,
            "dqRulesPassed": 9,
            "dqLastRun": (now - timedelta(days=1)).isoformat() + "Z",
            "lineageInfo": {
                "upstream": [],
                "downstream": ["informatica_3001"]
            },
            "usageStats": {
                "readsCount": 500,
                "usersCount": 5,
                "sizeInBytes": 1024 * 1024 * 1024 * 1024 * 10,
                "lastAccessTime": (now - timedelta(hours=3)).isoformat() + "Z"
            }
        },
        # 4. Dashboard Asset
        {
            "assetId": "3004",
            "assetName": "financial_reconciliations_dashboard",
            "assetType": "Dashboard",
            "description": "BI Dashboard summarizing balance reconciliations, cash flows, and credit card validation summaries.",
            "owners": [
                {"name": "Robert Miller", "role": "Business Owner", "email": "robert.miller@company.com"}
            ],
            "glossaryAssignments": [
                {"termId": "t_103", "termName": "Asset"}
            ],
            "sensitive": False,
            "classification": "Confidential",
            "dqRulesCount": 0,
            "lineageInfo": {
                "upstream": ["informatica_3005"],
                "downstream": []
            },
            "usageStats": {
                "readsCount": 450,
                "usersCount": 12,
                "sizeInBytes": 0,
                "lastAccessTime": (now - timedelta(hours=2)).isoformat() + "Z"
            }
        },
        # 5. View Asset
        {
            "assetId": "3005",
            "assetName": "ledger_balance_summary_view",
            "assetType": "View",
            "description": "Staging View aggregating ledger transactions and balance metrics.",
            "owners": [
                {"name": "Cloud Data Team", "role": "Technical Owner", "email": "cloud_data@company.com"}
            ],
            "glossaryAssignments": [
                {"termId": "t_101", "termName": "Transaction"}
            ],
            "sensitive": False,
            "classification": "Internal",
            "dqRulesCount": 5,
            "dqRulesPassed": 5,
            "dqLastRun": (now - timedelta(days=1)).isoformat() + "Z",
            "lineageInfo": {
                "upstream": ["informatica_3001"],
                "downstream": ["informatica_3004"]
            },
            "usageStats": {
                "readsCount": 1200,
                "usersCount": 8,
                "sizeInBytes": 1024 * 1024 * 18,
                "lastAccessTime": (now - timedelta(hours=1)).isoformat() + "Z"
            }
        }
    ]
    
    if num_assets and num_assets > len(informatica_export):
        import random
        target_count = num_assets
        current_id = 3006
        
        types = ["Table", "File", "Database Schema", "Dashboard", "View"]
        names_pool = {
            "Table": ["ledger_fact", "invoicing_dim", "balance_sheet", "reconciliation_log"],
            "File": ["tax_invoice_dump.json", "payroll_extract.csv", "ledger_backup.zip"],
            "Database Schema": ["GL_ledger_db", "taxation_raw_db", "reconciliations_staging"],
            "Dashboard": ["profitability_metrics_board", "cash_flow_report", "balance_compliance_dashboard"],
            "View": ["ledger_summary_v", "tax_returns_v", "reconciliation_match_v"]
        }
        classifications = ["Confidential", "Internal", "Public"]
        glossary_terms = [("t_101", "Transaction"), ("t_102", "Revenue"), ("t_103", "Asset"), ("t_104", "Liability")]
        
        while len(informatica_export) < target_count:
            asset_type = random.choice(types)
            name = f"{random.choice(names_pool[asset_type])}_{current_id}"
            
            is_rot = random.random() < 0.15
            
            if is_rot:
                reads = 0
                users = 0
                size_in_bytes = random.randint(1024 * 1024 * 100, 1024 * 1024 * 1024 * 1024 * 5) # 100MB to 5TB
                last_access = (now - timedelta(days=random.randint(185, 500))).isoformat() + "Z"
            else:
                reads = random.randint(10, 2000)
                users = random.randint(2, 50)
                size_in_bytes = random.randint(1024 * 1024 * 1, 1024 * 1024 * 1024 * 50)
                last_access = (now - timedelta(days=random.randint(0, 30))).isoformat() + "Z"
                
            owners = []
            if random.random() > 0.4:
                owners.append({
                    "name": f"Steward {random.randint(1,5)}",
                    "role": "Business Owner",
                    "email": f"steward.{random.randint(1,5)}@company.com"
                })
                
            terms = []
            if random.random() > 0.5:
                term = random.choice(glossary_terms)
                terms.append({"termId": term[0], "termName": term[1]})
                
            classification = random.choice(classifications)
            sensitive = random.random() < 0.2
            
            rules_run = random.choice([0, 5, 10, 20])
            if rules_run > 0:
                rules_passed = random.randint(int(rules_run * 0.4), rules_run)
                dq_last_run = (now - timedelta(days=random.randint(1, 5))).isoformat() + "Z"
            else:
                rules_passed = 0
                dq_last_run = ""
                
            asset = {
                "assetId": str(current_id),
                "assetName": name,
                "assetType": asset_type,
                "description": f"Mock Informatica asset representing {name} for performance checking.",
                "owners": owners,
                "glossaryAssignments": terms,
                "sensitive": sensitive,
                "classification": classification,
                "dqRulesCount": rules_run,
                "dqRulesPassed": rules_passed,
                "dqLastRun": dq_last_run,
                "lineageInfo": {
                    "upstream": [],
                    "downstream": []
                },
                "usageStats": {
                    "readsCount": reads,
                    "usersCount": users,
                    "sizeInBytes": size_in_bytes,
                    "lastAccessTime": last_access
                }
            }
            
            informatica_export.append(asset)
            current_id += 1
            
    return informatica_export

def main():
    import argparse
    parser = argparse.ArgumentParser(description="Generate Informatica mock metadata.")
    parser.add_argument("--num-assets", type=int, default=None, help="Total number of assets to generate")
    args = parser.parse_args()
    
    metadata = generate_informatica_metadata(args.num_assets)
    output_path = os.path.join(os.path.dirname(__file__), "sample_informatica_metadata.json")
    with open(output_path, "w") as f:
        json.dump(metadata, f, indent=2)
    print(f"[Informatica] Mock metadata written to '{output_path}' ({len(metadata)} assets)")

if __name__ == "__main__":
    main()
