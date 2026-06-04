import json
import os
from datetime import datetime, timedelta

def generate_ataccama_metadata():
    now = datetime.utcnow()
    
    # Rich mock data representing Ataccama assets.
    # Mimics Ataccama's properties: id, title, description, owner, terms, securityClassification,
    # dataQuality, lineage, usage, and sizeBytes.
    ataccama_export = [
        # 1. Active Table Asset: employee_payroll_records
        {
            "id": "4001",
            "title": "employee_payroll_records",
            "type": "Table",
            "description": "Active corporate employee payroll records. Stores monthly salary payments, taxes, bank details, and bonuses.",
            "owner": "hr_stewards@company.com",
            "terms": ["Employee Salary", "Bank Details", "Corporate Compensation"],
            "securityClassification": "Highly Confidential PII",
            "dataQuality": {
                "rulesRun": 30,
                "rulesPassed": 29, # 96.6% DQ pass rate
                "profiledDate": (now - timedelta(days=3)).isoformat() + "Z"
            },
            "lineage": {
                "sources": ["ataccama_4002"], # Fed by raw onboarding forms
                "targets": []
            },
            "usage": {
                "reads": 150,
                "users": 8,
                "lastRead": (now - timedelta(days=1)).isoformat() + "Z"
            },
            "sizeBytes": 1024 * 1024 * 12 # 12 MB
        },
        # 2. Exposed Table Asset: employee_onboarding_raw (Low DQ, No steward, High usage risk)
        {
            "id": "4002",
            "title": "employee_onboarding_raw",
            "type": "Table",
            "description": "Staging area for fresh employee onboarding records, containing SSN numbers, phone numbers, and home addresses.",
            "owner": "", # Empty owner! (risk!)
            "terms": [],
            "securityClassification": "", # Empty classification! (PII keyword leakage risk!)
            "dataQuality": {
                "rulesRun": 4,
                "rulesPassed": 1, # 25.0% pass rate (extreme quality issues)
                "profiledDate": (now - timedelta(days=1)).isoformat() + "Z"
            },
            "lineage": {
                "sources": [],
                "targets": ["ataccama_4001"]
            },
            "usage": {
                "reads": 520, # High read volume on unsafe data (risk!)
                "users": 24,
                "lastRead": (now - timedelta(hours=2)).isoformat() + "Z"
            },
            "sizeBytes": 1024 * 1024 * 85 # 85 MB
        },
        # 3. Schema/Database Asset: HR Database Container
        {
            "id": "4003",
            "title": "hr_database_container",
            "type": "Database Catalog",
            "description": "Logical workspace containing all HR databases, staging logs, and employee registers.",
            "owner": "hr_stewards@company.com",
            "terms": ["HR Domain"],
            "securityClassification": "Confidential",
            "dataQuality": {
                "rulesRun": 34,
                "rulesPassed": 30, # 88.2%
                "profiledDate": (now - timedelta(days=1)).isoformat() + "Z"
            },
            "lineage": {
                "sources": [],
                "targets": ["ataccama_4002"]
            },
            "usage": {
                "reads": 670,
                "users": 10,
                "lastRead": (now - timedelta(hours=5)).isoformat() + "Z"
            },
            "sizeBytes": 1024 * 1024 * 1024 * 97 # 97 GB
        }
    ]
    return ataccama_export

def main():
    metadata = generate_ataccama_metadata()
    output_path = os.path.join(os.path.dirname(__file__), "sample_ataccama_metadata.json")
    with open(output_path, "w") as f:
        json.dump(metadata, f, indent=2)
    print(f"[Ataccama] Mock metadata written to '{output_path}' ({len(metadata)} assets)")

if __name__ == "__main__":
    main()
