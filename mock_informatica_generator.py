import json
import os
from datetime import datetime, timedelta

def generate_informatica_metadata():
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
                "sizeInBytes": 1024 * 1024 * 1024 * 1024 * 10, # 10 TB
                "lastAccessTime": (now - timedelta(hours=3)).isoformat() + "Z"
            }
        }
    ]
    return informatica_export

def main():
    metadata = generate_informatica_metadata()
    output_path = os.path.join(os.path.dirname(__file__), "sample_informatica_metadata.json")
    with open(output_path, "w") as f:
        json.dump(metadata, f, indent=2)
    print(f"[Informatica] Mock metadata written to '{output_path}' ({len(metadata)} assets)")

if __name__ == "__main__":
    main()
