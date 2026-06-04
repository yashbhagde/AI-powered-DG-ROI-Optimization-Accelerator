import json
import os
from datetime import datetime, timedelta

def generate_purview_metadata():
    now = datetime.utcnow()
    
    # Rich mock data representing Microsoft Purview catalog entities.
    # Mimics guid, attributes, contacts, classifications, meanings, lineage, and dataQuality fields.
    purview_export = [
        # 1. PowerBI Dashboard Asset: executive_financial_dashboard
        {
            "guid": "5001",
            "name": "executive_financial_dashboard",
            "typeName": "powerbi_dashboard",
            "attributes": {
                "description": "Executive dashboard visualizing monthly corporate profits, operating margins, EBITDA, and quarterly forecast data.",
                "qualifiedName": "powerbi://finance/dashboards/exec_financials",
                "sizeInBytes": 0,
                "createdTime": (now - timedelta(days=365)).isoformat() + "Z",
                "lastModifiedTime": (now - timedelta(days=5)).isoformat() + "Z"
            },
            "contacts": {
                "Owner": [{"id": "finance_leadership_group", "info": "cfo_office@company.com"}],
                "Expert": [{"id": "dan.analyst", "info": "dan.analyst@company.com"}]
            },
            "classifications": [
                {"typeName": "Financial.Restricted", "validity": "CONFIRMED"}
            ],
            "meanings": [
                {"displayText": "EBITDA", "termGuid": "t_ebitda"},
                {"displayText": "Revenue", "termGuid": "t_revenue"}
            ],
            "dataQuality": {
                "rulesRun": 8,
                "rulesPassed": 5, # 62.5% DQ pass rate (high impact/bad trust since executive dashboard)
                "lastProfiled": (now - timedelta(days=1)).isoformat() + "Z"
            },
            "lineage": {
                "inputs": ["informatica_3001"], # Ingested from informatica ledger fact table
                "outputs": []
            },
            "usage": {
                "queries": 1200,
                "users": 45,
                "lastAccessed": (now - timedelta(hours=1)).isoformat() + "Z"
            }
        },
        # 2. ROT Table Asset: archive_backup_database_2020
        {
            "guid": "5002",
            "name": "archive_backup_database_2020",
            "typeName": "azure_synapse_table",
            "attributes": {
                "description": "Synapse database backup file from legacy migration back in 2020. Retained post-deprecation.",
                "qualifiedName": "synapse://archive/backup_2020",
                "sizeInBytes": 1024 * 1024 * 1024 * 1024 * 45, # 45 TB (High storage cost ROT candidate)
                "createdTime": (now - timedelta(days=1800)).isoformat() + "Z"
            },
            "contacts": {}, # Missing contacts (risk!)
            "classifications": [], # Unclassified (risk!)
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
        },
        # 3. Azure SQL Table Asset: vendor_billing_info
        {
            "guid": "5003",
            "name": "vendor_billing_info",
            "typeName": "azure_sql_table",
            "attributes": {
                "description": "Table storing global vendor bank routing numbers, addresses, and payment histories.",
                "qualifiedName": "mssql://proddb/finance/vendor_billing_info",
                "sizeInBytes": 1024 * 1024 * 320 # 320 MB
            },
            "contacts": {
                "Owner": [{"id": "ap_stewards", "info": "accounts_payable@company.com"}]
            },
            "classifications": [
                {"typeName": "MICROSOFT.FINANCIAL.CREDIT_CARD_NUMBER", "validity": "CONFIRMED"},
                {"typeName": "PII", "validity": "CONFIRMED"}
            ],
            "meanings": [
                {"displayText": "Vendor Account", "termGuid": "t_vendor_acc"}
            ],
            "dataQuality": {
                "rulesRun": 15,
                "rulesPassed": 15, # 100% data quality pass
                "lastProfiled": (now - timedelta(hours=12)).isoformat() + "Z"
            },
            "lineage": {
                "inputs": [],
                "outputs": ["purview_5001"] # Feeds executive report
            },
            "usage": {
                "queries": 450,
                "users": 12,
                "lastAccessed": (now - timedelta(hours=3)).isoformat() + "Z"
            },
            # Real-world Purview schema columns definition
            "columns": [
                {
                    "guid": "5003_1",
                    "name": "vendor_id",
                    "typeName": "azure_sql_column",
                    "attributes": {"description": "Primary key identifier for vendors."}
                },
                {
                    "guid": "5003_2",
                    "name": "bank_routing_no",
                    "typeName": "azure_sql_column",
                    "attributes": {"description": "ACH bank routing code. Highly sensitive."},
                    "classifications": [{"typeName": "PII"}]
                }
            ]
        }
    ]
    return purview_export

def main():
    metadata = generate_purview_metadata()
    output_path = os.path.join(os.path.dirname(__file__), "sample_purview_metadata.json")
    with open(output_path, "w") as f:
        json.dump(metadata, f, indent=2)
    print(f"[Purview] Mock metadata written to '{output_path}' ({len(metadata)} assets)")

if __name__ == "__main__":
    main()
