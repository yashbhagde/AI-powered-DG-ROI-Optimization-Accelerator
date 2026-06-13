import json
import os
from datetime import datetime, timedelta


def generate_ataccama_metadata(num_assets=None):
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
                "rulesPassed": 29,  # 96.6% DQ pass rate
                "profiledDate": (now - timedelta(days=3)).isoformat() + "Z",
            },
            "lineage": {
                "sources": ["ataccama_4002"],  # Fed by raw onboarding forms
                "targets": [],
            },
            "usage": {"reads": 150, "users": 8, "lastRead": (now - timedelta(days=1)).isoformat() + "Z"},
            "sizeBytes": 1024 * 1024 * 12,  # 12 MB
        },
        # 2. Exposed Table Asset: employee_onboarding_raw (Low DQ, No steward, High usage risk)
        {
            "id": "4002",
            "title": "employee_onboarding_raw",
            "type": "Table",
            "description": "Staging area for fresh employee onboarding records, containing SSN numbers, phone numbers, and home addresses.",
            "owner": "",  # Empty owner! (risk!)
            "terms": [],
            "securityClassification": "",  # Empty classification! (PII keyword leakage risk!)
            "dataQuality": {
                "rulesRun": 4,
                "rulesPassed": 1,  # 25.0% pass rate (extreme quality issues)
                "profiledDate": (now - timedelta(days=1)).isoformat() + "Z",
            },
            "lineage": {"sources": [], "targets": ["ataccama_4001"]},
            "usage": {
                "reads": 520,  # High read volume on unsafe data (risk!)
                "users": 24,
                "lastRead": (now - timedelta(hours=2)).isoformat() + "Z",
            },
            "sizeBytes": 1024 * 1024 * 85,  # 85 MB
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
                "rulesPassed": 30,  # 88.2%
                "profiledDate": (now - timedelta(days=1)).isoformat() + "Z",
            },
            "lineage": {"sources": [], "targets": ["ataccama_4002"]},
            "usage": {"reads": 670, "users": 10, "lastRead": (now - timedelta(hours=5)).isoformat() + "Z"},
            "sizeBytes": 1024 * 1024 * 1024 * 97,
        },
        # 4. File Asset
        {
            "id": "4004",
            "title": "raw_employee_onboarding_dump.csv",
            "type": "File",
            "description": "Raw unstructured backup dump of employee personal fields, containing tax files and salary bands.",
            "owner": "hr_stewards@company.com",
            "terms": ["Employee Salary"],
            "securityClassification": "Highly Confidential PII",
            "dataQuality": {"rulesRun": 10, "rulesPassed": 9, "profiledDate": (now - timedelta(days=2)).isoformat() + "Z"},
            "lineage": {"sources": [], "targets": ["ataccama_4001"]},
            "usage": {"reads": 15, "users": 2, "lastRead": (now - timedelta(days=1)).isoformat() + "Z"},
            "sizeBytes": 1024 * 1024 * 250,
        },
        # 5. Dashboard Asset
        {
            "id": "4005",
            "title": "hr_operational_kpi_dashboard",
            "type": "Dashboard",
            "description": "BI dashboard tracking employee onboarding speeds, retention, and departmental compliance scores.",
            "owner": "hr_stewards@company.com",
            "terms": ["HR Domain"],
            "securityClassification": "Confidential",
            "dataQuality": {"rulesRun": 0, "rulesPassed": 0},
            "lineage": {"sources": ["ataccama_4001"], "targets": []},
            "usage": {"reads": 820, "users": 15, "lastRead": (now - timedelta(hours=3)).isoformat() + "Z"},
            "sizeBytes": 0,
        },
        # 6. View Asset
        {
            "id": "4006",
            "title": "active_employees_payroll_view",
            "type": "View",
            "description": "Database view mapping active employees to their latest verified payroll runs.",
            "owner": "hr_stewards@company.com",
            "terms": ["Employee Salary"],
            "securityClassification": "Confidential",
            "dataQuality": {"rulesRun": 5, "rulesPassed": 5, "profiledDate": (now - timedelta(days=1)).isoformat() + "Z"},
            "lineage": {"sources": ["ataccama_4001"], "targets": ["ataccama_4005"]},
            "usage": {"reads": 450, "users": 5, "lastRead": (now - timedelta(hours=1)).isoformat() + "Z"},
            "sizeBytes": 1024 * 1024 * 5,
        },
    ]

    if num_assets and num_assets > len(ataccama_export):
        import random

        target_count = num_assets
        current_id = 4007

        types = ["Table", "Database Catalog", "Data Set", "File", "Dashboard", "View"]
        names_pool = {
            "Table": ["salary_records", "benefit_plans", "training_log", "performance_reviews", "recruiting_pipeline"],
            "Database Catalog": ["talent_acquisition_dw", "benefits_portal_db", "learning_mgmt_sys"],
            "Data Set": ["annual_diversity_report", "contractor_invoices_csv", "attrition_predictions"],
            "File": ["employee_export_v1.json", "resume_dump.zip", "contracts_archive.tar.gz"],
            "Dashboard": ["onboarding_metrics_board", "retention_analytics_report", "compensation_kpi_dashboard"],
            "View": ["employee_details_v", "payroll_runs_v", "benefits_enrollment_v"],
        }
        classifications = ["Highly Confidential PII", "Confidential", "Internal", "Public"]
        glossary_terms = ["Employee Compensation", "Tax Record", "Personal Address", "Job Grade"]

        while len(ataccama_export) < target_count:
            asset_type = random.choice(types)
            name = f"{random.choice(names_pool[asset_type])}_{current_id}"

            is_rot = random.random() < 0.15

            if is_rot:
                reads = random.randint(0, 5)
                users = random.randint(0, 2)
                size_bytes = random.randint(1024 * 1024 * 10, 1024 * 1024 * 1024 * 100)
                last_read = (now - timedelta(days=random.randint(185, 400))).isoformat() + "Z"
            else:
                reads = random.randint(50, 1500)
                users = random.randint(3, 40)
                size_bytes = random.randint(1024 * 1024 * 1, 1024 * 1024 * 1024 * 10)
                last_read = (now - timedelta(days=random.randint(0, 30))).isoformat() + "Z"

            owner = f"steward.{random.randint(1, 5)}@company.com" if random.random() > 0.4 else ""
            classification = random.choice(classifications) if random.random() > 0.3 else ""
            terms = [random.choice(glossary_terms)] if random.random() > 0.5 else []

            rules_run = random.choice([0, 10, 20])
            if rules_run > 0:
                rules_passed = random.randint(int(rules_run * 0.4), rules_run)
                dq = {
                    "rulesRun": rules_run,
                    "rulesPassed": rules_passed,
                    "profiledDate": (now - timedelta(days=random.randint(1, 6))).isoformat() + "Z",
                }
            else:
                dq = {"rulesRun": 0, "rulesPassed": 0}

            asset = {
                "id": str(current_id),
                "title": name,
                "type": asset_type,
                "description": f"Mock Ataccama asset representing {name} for performance tests.",
                "owner": owner,
                "terms": terms,
                "securityClassification": classification,
                "dataQuality": dq,
                "lineage": {"sources": [], "targets": []},
                "usage": {"reads": reads, "users": users, "lastRead": last_read},
                "sizeBytes": size_bytes,
            }

            ataccama_export.append(asset)
            current_id += 1

    return ataccama_export


def main():
    import argparse

    parser = argparse.ArgumentParser(description="Generate Ataccama mock metadata.")
    parser.add_argument("--num-assets", type=int, default=None, help="Total number of assets to generate")
    args = parser.parse_args()

    metadata = generate_ataccama_metadata(args.num_assets)
    output_path = os.path.join(os.path.dirname(__file__), "sample_ataccama_metadata.json")
    with open(output_path, "w") as f:
        json.dump(metadata, f, indent=2)
    print(f"[Ataccama] Mock metadata written to '{output_path}' ({len(metadata)} assets)")


if __name__ == "__main__":
    main()
