import json
import os
from datetime import datetime, timedelta

def generate_purview_metadata(num_assets=None):
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
    
    if num_assets and num_assets > len(purview_export):
        import random
        target_count = num_assets
        current_id = 5004
        
        types = ["powerbi_dashboard", "azure_synapse_table", "azure_sql_table", "azure_blob_file"]
        names_pool = {
            "powerbi_dashboard": ["sales_insights", "inventory_flow", "hr_retention_kpi", "cloud_spending_dashboard"],
            "azure_synapse_table": ["customer_dim", "orders_fact", "web_clicks_archive", "product_catalog"],
            "azure_sql_table": ["users", "orders", "subscription_plans", "payment_receipts"],
            "azure_blob_file": ["raw_events_2025.json", "user_export_temp.csv", "backup_v1.bak"]
        }
        classifications = ["PII", "Financial.Restricted", "MICROSOFT.PERSONAL.US_SOCIAL_SECURITY_NUMBER", "CONFIDENTIAL"]
        meanings = ["Customer", "EBITDA", "Revenue", "Transaction", "Invoice"]
        
        while len(purview_export) < target_count:
            asset_type = random.choice(types)
            name = f"{random.choice(names_pool[asset_type])}_{current_id}"
            
            is_rot = random.random() < 0.15
            
            if is_rot:
                queries = 0
                users = 0
                size_in_bytes = random.randint(1024 * 1024 * 500, 1024 * 1024 * 1024 * 500)
                last_accessed = (now - timedelta(days=random.randint(185, 600))).isoformat() + "Z"
            else:
                queries = random.randint(100, 3000)
                users = random.randint(5, 50)
                size_in_bytes = 0 if asset_type == "powerbi_dashboard" else random.randint(1024 * 1024 * 10, 1024 * 1024 * 1024 * 20)
                last_accessed = (now - timedelta(days=random.randint(0, 30))).isoformat() + "Z"
                
            attributes = {
                "description": f"Mock Purview asset for large-scale tests representing {name}.",
                "qualifiedName": f"{asset_type}://{name}",
                "sizeInBytes": size_in_bytes,
                "createdTime": (now - timedelta(days=random.randint(100, 1000))).isoformat() + "Z"
            }
            
            contacts = {}
            if random.random() > 0.4: # 60% chance of contacts
                contacts["Owner"] = [{"id": f"owner_group_{random.randint(1,5)}", "info": f"steward.{random.randint(1,5)}@company.com"}]
                
            asset_classifications = []
            if random.random() < 0.25:
                asset_classifications.append({"typeName": random.choice(classifications), "validity": "CONFIRMED"})
                
            asset_meanings = []
            if random.random() > 0.5:
                asset_meanings.append({"displayText": random.choice(meanings), "termGuid": f"t_{random.randint(100, 200)}"})
                
            rules_run = random.choice([0, 5, 10])
            if rules_run > 0:
                rules_passed = random.randint(int(rules_run * 0.4), rules_run)
                dq = {
                    "rulesRun": rules_run,
                    "rulesPassed": rules_passed,
                    "lastProfiled": (now - timedelta(days=random.randint(1, 5))).isoformat() + "Z"
                }
            else:
                dq = {
                    "rulesRun": 0,
                    "rulesPassed": 0
                }
                
            asset = {
                "guid": str(current_id),
                "name": name,
                "typeName": asset_type,
                "attributes": attributes,
                "contacts": contacts,
                "classifications": asset_classifications,
                "meanings": asset_meanings,
                "dataQuality": dq,
                "lineage": {
                    "inputs": [],
                    "outputs": []
                },
                "usage": {
                    "queries": queries,
                    "users": users,
                    "lastAccessed": last_accessed
                }
            }
            
            purview_export.append(asset)
            current_id += 1
            
    return purview_export

def main():
    import argparse
    parser = argparse.ArgumentParser(description="Generate Purview mock metadata.")
    parser.add_argument("--num-assets", type=int, default=None, help="Total number of assets to generate")
    args = parser.parse_args()
    
    metadata = generate_purview_metadata(args.num_assets)
    output_path = os.path.join(os.path.dirname(__file__), "sample_purview_metadata.json")
    with open(output_path, "w") as f:
        json.dump(metadata, f, indent=2)
    print(f"[Purview] Mock metadata written to '{output_path}' ({len(metadata)} assets)")

if __name__ == "__main__":
    main()
