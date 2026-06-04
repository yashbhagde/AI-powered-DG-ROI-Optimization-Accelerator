import json
import os
from datetime import datetime, timedelta

def generate_collibra_metadata(num_assets=None):
    now = datetime.utcnow()
    
    # Rich mock data representing a Collibra asset export.
    # Mimics Collibra's relations and attribute types, including tables, schemas, columns, and terms.
    collibra_export = [
        # 1. Database Asset
        {
            "id": "2000",
            "name": "Finance Production CRM Database",
            "type": "Database",
            "attributes": [
                {"type": "Description", "value": "Primary transactional database for global customer relations and billing details."},
                {"type": "Data Classification", "value": "Confidential"}
            ],
            "relations": [
                {"type": "Owned By", "target": "CRM Data Steward Group", "role": "Business Steward", "email": "crm_stewards@company.com"}
            ],
            "dataQuality": {
                "rulesRun": 4,
                "rulesPassed": 4,
                "lastProfiled": (now - timedelta(days=1)).isoformat() + "Z"
            },
            "usage": {
                "queryCount": 1400,
                "userCount": 28,
                "sizeInBytes": 1024 * 1024 * 1024 * 900, # 900 GB
                "lastAccessed": (now - timedelta(minutes=45)).isoformat() + "Z"
            }
        },
        # 2. Table Asset: customer_crm_staging
        {
            "id": "2001",
            "name": "Staging Customer CRM Data",
            "type": "Database Table",
            "attributes": [
                {"type": "Description", "value": "Landing zone table for CRM customer contact details, imported hourly."},
                {"type": "Data Classification", "value": "Confidential"},
                {"type": "Security Level", "value": "Level 3 - Restricted PII"}
            ],
            "relations": [
                {"type": "Owned By", "target": "CRM Data Team", "role": "Technical Owner", "email": "crm_devs@company.com"},
                {"type": "Associated Glossary Term", "target": "Customer Contact"},
                {"type": "Part of Database", "target": "Finance Production CRM Database"},
                {"type": "Feeds upstream of", "target": "alation_101"} # Lineage trace
            ],
            "dataQuality": {
                "rulesRun": 10,
                "rulesPassed": 6, # 60% pass rate (low quality risk)
                "lastProfiled": (now - timedelta(days=1)).isoformat() + "Z"
            },
            "usage": {
                "queryCount": 670,
                "userCount": 15,
                "sizeInBytes": 1024 * 1024 * 1024 * 5, # 5 GB
                "lastAccessed": (now - timedelta(hours=4)).isoformat() + "Z"
            },
            # Real-world Collibra representation of child assets (columns)
            "columns": [
                {
                    "id": "2001_1",
                    "name": "crm_contact_id",
                    "type": "Table Column",
                    "attributes": [
                        {"type": "Description", "value": "Surrogate primary key of CRM contact."}
                    ]
                },
                {
                    "id": "2001_2",
                    "name": "phone_number",
                    "type": "Table Column",
                    "attributes": [
                        {"type": "Description", "value": "Raw mobile/home phone number of client."},
                        {"type": "Data Classification", "value": "Confidential PII"}
                    ]
                },
                {
                    "id": "2001_3",
                    "name": "email_address",
                    "type": "Table Column",
                    "attributes": [
                        {"type": "Description", "value": "Primary customer contact email address."}
                    ]
                }
            ]
        },
        # 3. ROT Table Asset: legacy_marketing_prospects_2021
        {
            "id": "2002",
            "name": "Legacy Marketing Prospects 2021",
            "type": "Database Table",
            "attributes": [
                {"type": "Description", "value": "Old marketing prospect list from 2021 campaigns. Retained for compliance, but inactive."}
            ],
            "relations": [], # Empty relations (no owner/steward - compliance risk!)
            "dataQuality": {
                "rulesRun": 0,
                "rulesPassed": 0
            },
            "usage": {
                "queryCount": 0, # ROT candidate
                "userCount": 0,
                "sizeInBytes": 1024 * 1024 * 1024 * 850, # 850 GB
                "lastAccessed": (now - timedelta(days=365)).isoformat() + "Z"
            }
        },
        # 4. Glossary Term Asset (Business Metadata)
        {
            "id": "2003",
            "name": "Customer Contact",
            "type": "Business Term",
            "attributes": [
                {"type": "Definition", "value": "A representation of the communication endpoints (email, phone, address) used to reach an enterprise customer."},
                {"type": "Status", "value": "Approved"}
            ],
            "relations": [
                {"type": "Owned By", "target": "Sarah Steward", "role": "Business Steward", "email": "sarah.steward@company.com"},
                {"type": "Governs Term", "target": "Staging Customer CRM Data"}
            ],
            "dataQuality": {
                "rulesRun": 0,
                "rulesPassed": 0
            },
            "usage": {
                "queryCount": 200,
                "userCount": 50,
                "sizeInBytes": 0,
                "lastAccessed": (now - timedelta(days=5)).isoformat() + "Z"
            }
        }
    ]
    
    if num_assets and num_assets > len(collibra_export):
        import random
        target_count = num_assets
        current_id = 2004
        
        types = ["Database", "Database Table", "Business Term", "Report"]
        names_pool = {
            "Database": ["Analytics_DB", "HR_Prod_DB", "Inventory_DB", "Compliance_DB"],
            "Database Table": ["billing_history", "user_profiles", "session_metrics", "device_logs", "payroll_adjustments", "supplier_list"],
            "Business Term": ["Billing Date", "Account Balance", "Employee Level", "Risk Score", "Vendor Tier"],
            "Report": ["Monthly Financial Summary", "Operational KPI Dashboard", "Compliance Auditing Log"]
        }
        classifications = ["Confidential", "Internal", "Public", "Highly Restricted"]
        
        while len(collibra_export) < target_count:
            asset_type = random.choice(types)
            name = f"{random.choice(names_pool[asset_type])} {current_id}"
            
            is_rot = random.random() < 0.15
            
            if is_rot:
                query_count = 0
                user_count = 0
                size_in_bytes = random.randint(1024 * 1024 * 500, 1024 * 1024 * 1024 * 300) # 500MB to 300GB
                last_accessed = (now - timedelta(days=random.randint(185, 500))).isoformat() + "Z"
            else:
                query_count = random.randint(50, 2000)
                user_count = random.randint(5, 100)
                size_in_bytes = 0 if asset_type in ["Report", "Business Term"] else random.randint(1024 * 1024 * 20, 1024 * 1024 * 1024 * 50)
                last_accessed = (now - timedelta(days=random.randint(0, 30))).isoformat() + "Z"
                
            attributes = [{"type": "Description", "value": f"Mock Collibra {asset_type} for scaled dataset tests."}]
            
            # PII & Classification
            if random.random() < 0.3:
                classification = random.choice(classifications)
                attributes.append({"type": "Data Classification", "value": classification})
                if classification in ["Confidential", "Highly Restricted"] and random.random() > 0.5:
                    attributes.append({"type": "Security Level", "value": "Restricted PII"})
                    
            relations = []
            if random.random() > 0.4: # 60% chance of owner/steward
                relations.append({
                    "type": "Owned By",
                    "target": f"Steward Group {random.randint(1,5)}",
                    "role": "Business Steward",
                    "email": f"steward.{random.randint(1,5)}@company.com"
                })
                
            rules_run = random.choice([0, 4, 8, 12])
            if rules_run > 0:
                rules_passed = random.randint(int(rules_run * 0.4), rules_run)
                dq = {
                    "rulesRun": rules_run,
                    "rulesPassed": rules_passed,
                    "lastProfiled": (now - timedelta(days=random.randint(1, 7))).isoformat() + "Z"
                }
            else:
                dq = {
                    "rulesRun": 0,
                    "rulesPassed": 0
                }
                
            asset = {
                "id": str(current_id),
                "name": name,
                "type": asset_type,
                "attributes": attributes,
                "relations": relations,
                "dataQuality": dq,
                "usage": {
                    "queryCount": query_count,
                    "userCount": user_count,
                    "sizeInBytes": size_in_bytes,
                    "lastAccessed": last_accessed
                }
            }
            
            collibra_export.append(asset)
            current_id += 1
            
    return collibra_export

def main():
    import argparse
    parser = argparse.ArgumentParser(description="Generate Collibra mock metadata.")
    parser.add_argument("--num-assets", type=int, default=None, help="Total number of assets to generate")
    args = parser.parse_args()
    
    metadata = generate_collibra_metadata(args.num_assets)
    output_path = os.path.join(os.path.dirname(__file__), "sample_collibra_metadata.json")
    with open(output_path, "w") as f:
        json.dump(metadata, f, indent=2)
    print(f"[Collibra] Mock metadata written to '{output_path}' ({len(metadata)} assets)")

if __name__ == "__main__":
    main()
