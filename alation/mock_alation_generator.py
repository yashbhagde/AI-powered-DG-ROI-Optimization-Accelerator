import json
import os
from datetime import datetime, timedelta

def generate_alation_metadata():
    now = datetime.utcnow()
    
    # Rich mock data representing an Alation catalog export.
    # Mimics real-world Alation schema with custom fields, nested columns, and lineage.
    alation_export = [
        # 1. Schema Asset
        {
            "id": "100",
            "name": "sales_dw_schema",
            "type": "Schema",
            "description": "Enterprise Sales Data Warehouse containing raw transactional and customer dimension data.",
            "stewards": [
                {"username": "steward.mark@company.com", "email": "steward.mark@company.com"}
            ],
            "popularity": 90,
            "view_count": 820,
            "size_in_bytes": 1024 * 1024 * 1024 * 150, # 150 GB
            "last_accessed": (now - timedelta(hours=2)).isoformat() + "Z",
            "custom_fields": {
                "Classification": "Internal",
                "Glossary Term": "Sales Domain",
                "Data Owner": "sales_analytics_leads@company.com"
            },
            "data_quality": {
                "rules_run": 5,
                "rules_passed": 5,
                "last_profiled": (now - timedelta(days=1)).isoformat() + "Z"
            },
            "lineage": {
                "upstream": [],
                "downstream": ["alation_101", "alation_102"]
            }
        },
        # 2. Table Asset: corporate_customers
        {
            "id": "101",
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
                "Glossary Term": "Corporate Customer",
                "Subject Area": "Customer MDM"
            },
            "data_quality": {
                "rules_run": 10,
                "rules_passed": 10,
                "last_profiled": (now - timedelta(days=2)).isoformat() + "Z",
                "dq_metrics": {
                    "null_count": 0,
                    "uniqueness_pct": 100.0,
                    "completeness_pct": 100.0
                }
            },
            "lineage": {
                "upstream": ["collibra_2001"], # Ingestion lineage
                "downstream": ["alation_103", "purview_5001"]
            },
            # Rich Column Details (realistic nesting)
            "columns": [
                {
                    "column_id": "101_1",
                    "name": "customer_id",
                    "data_type": "VARCHAR(50)",
                    "description": "Unique identifier for the corporate client.",
                    "is_primary_key": True,
                    "custom_fields": {
                        "PII": "No",
                        "Glossary Term": "Customer Identifier"
                    }
                },
                {
                    "column_id": "101_2",
                    "name": "tax_id_ssn",
                    "data_type": "VARCHAR(15)",
                    "description": "Tax Identification or SSN number for credit checks.",
                    "is_primary_key": False,
                    "custom_fields": {
                        "PII": "Yes",
                        "Classification": "Confidential PII",
                        "Glossary Term": "Tax Identifier"
                    }
                },
                {
                    "column_id": "101_3",
                    "name": "credit_limit",
                    "data_type": "DECIMAL(15,2)",
                    "description": "Approved credit threshold for corporate transactions.",
                    "is_primary_key": False,
                    "custom_fields": {
                        "PII": "No",
                        "Glossary Term": "Credit Limit"
                    }
                }
            ]
        },
        # 3. Table Asset: transactions_fact
        {
            "id": "102",
            "name": "transactions_fact",
            "type": "Table",
            "description": "Fact table recording daily corporate sales transactions and order status.",
            "stewards": [
                {"username": "sarah.steward@company.com", "email": "sarah.steward@company.com"}
            ],
            "popularity": 85,
            "view_count": 1100,
            "size_in_bytes": 1024 * 1024 * 1024 * 85, # 85 GB
            "last_accessed": (now - timedelta(hours=1)).isoformat() + "Z",
            "custom_fields": {
                "PII": "No",
                "Classification": "Internal",
                "Glossary Term": "Sales Transaction"
            },
            "data_quality": {
                "rules_run": 8,
                "rules_passed": 7, # 87.5% pass rate
                "last_profiled": (now - timedelta(days=1)).isoformat() + "Z"
            },
            "lineage": {
                "upstream": ["alation_100"],
                "downstream": ["alation_103"]
            },
            "columns": [
                {
                    "column_id": "102_1",
                    "name": "transaction_id",
                    "data_type": "VARCHAR(64)",
                    "description": "Globally unique order hash.",
                    "is_primary_key": True
                },
                {
                    "column_id": "102_2",
                    "name": "customer_id",
                    "data_type": "VARCHAR(50)",
                    "description": "Foreign key referencing corporate_customers.customer_id."
                },
                {
                    "column_id": "102_3",
                    "name": "amount_usd",
                    "data_type": "NUMERIC(18,4)",
                    "description": "Total order amount in USD."
                }
            ]
        },
        # 4. BI Dashboard Asset: customer_credit_report
        {
            "id": "103",
            "name": "customer_credit_report",
            "type": "Dashboard",
            "description": "Executive BI report summarizing credit ratings, transactional volumes, and exposures.",
            "stewards": [
                {"username": "steward.mark@company.com", "email": "steward.mark@company.com"}
            ],
            "popularity": 80,
            "view_count": 950,
            "size_in_bytes": 0,
            "last_accessed": (now - timedelta(days=2)).isoformat() + "Z",
            "custom_fields": {
                "PII": "No",
                "Classification": "Confidential",
                "Glossary Term": "Credit Summary Dashboard"
            },
            "data_quality": {
                "rules_run": 0,
                "rules_passed": 0
            },
            "lineage": {
                "upstream": ["alation_101", "alation_102"],
                "downstream": []
            }
        },
        # 5. ROT Table Asset: temp_customer_export_2024
        {
            "id": "104",
            "name": "temp_customer_export_2024",
            "type": "Table",
            "description": "Temporary sandbox export of customers containing SSN and credit ratings for a one-off audit.",
            "stewards": [],
            "popularity": 1,
            "view_count": 3,
            "size_in_bytes": 1024 * 1024 * 1024 * 120, # 120 GB
            "last_accessed": (now - timedelta(days=190)).isoformat() + "Z",
            "custom_fields": {
                "PII": "Yes",
                "Classification": "Public" # COMPLIANCE RISK: Contains PII but classified as Public!
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
    return alation_export

def main():
    metadata = generate_alation_metadata()
    output_path = os.path.join(os.path.dirname(__file__), "sample_alation_metadata.json")
    with open(output_path, "w") as f:
        json.dump(metadata, f, indent=2)
    print(f"[Alation] Mock metadata written to '{output_path}' ({len(metadata)} assets)")

if __name__ == "__main__":
    main()
