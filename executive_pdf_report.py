import os
import sys
import json
import argparse
from datetime import datetime

from reportlab.lib.pagesizes import letter
from reportlab.lib import colors
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, KeepTogether
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle

from canonical_metadata_model import map_raw_to_canonical
from governance_scoring_engine import GovernanceScoringEngine
from roi_calculation_engine import ROICalculationEngine, calculate_tcs
from maturity_assessment_engine import MaturityAssessmentEngine

def add_page_decorations(canvas, doc):
    canvas.saveState()
    # Draw top accent bar (navy blue)
    canvas.setFillColor(colors.HexColor("#1A365D")) # Navy
    canvas.rect(0, 792 - 10, 612, 10, fill=True, stroke=False)
    
    # Draw footer
    canvas.setFont("Helvetica-Bold", 8)
    canvas.setFillColor(colors.HexColor("#718096")) # Gray text
    canvas.drawString(54, 36, "CONFIDENTIAL - ENTERPRISE DATA GOVERNANCE EXECUTIVE REVIEW")
    canvas.drawRightString(612 - 54, 36, f"Page {doc.page}")
    canvas.restoreState()

def format_currency(val: float) -> str:
    if val >= 1_000_000.0:
        return f"${val / 1_000_000.0:.2f} million"
    return f"${val:,.2f}"

def generate_remediation_csv(platform, canonical_assets, scored_df, roi_df, csv_output_file):
    import csv
    
    # Create lookup dictionaries for scored_df and roi_df by asset_id
    scored_dict = scored_df.set_index("asset_id").to_dict(orient="index")
    roi_dict = roi_df.set_index("asset_id").to_dict(orient="index")
    
    rows = []
    
    for asset in canonical_assets:
        asset_id = asset.asset_id
        scores = scored_dict.get(asset_id, {})
        roi = roi_dict.get(asset_id, {})
        
        # Extract metadata metrics
        doc_score = scores.get("documentation_score", 0.0)
        dq_score = scores.get("data_quality_score", 0.0)
        lineage_score = scores.get("lineage_score", 0.0)
        risk_score = scores.get("security_risk_score", 0.0)
        
        is_sensitive = roi.get("is_sensitive", False)
        is_rot = roi.get("is_rot", False)
        
        # Check owners and stewards
        owner_names = [o.name for o in asset.owners if "owner" in o.role.lower() or o.role == ""]
        steward_names = [o.name for o in asset.owners if "steward" in o.role.lower()]
        
        owner_str = ", ".join(owner_names) if owner_names else "UNASSIGNED"
        steward_str = ", ".join(steward_names) if steward_names else "UNASSIGNED"
        
        # Construct dynamic deep link URL
        catalog_url = f"https://{platform}.company.com/catalog/asset/{asset.source_id}"
        
        # 1. PII exposure without owner
        if is_sensitive and not owner_names:
            opportunity_risk_savings = roi.get("opportunity_risk_savings", 0.0)
            rows.append({
                "Asset_ID": asset_id,
                "Asset_Name": asset.name,
                "Asset_Type": asset.asset_type,
                "Source_Platform": platform,
                "Remediation_Category": "PII_EXPOSURE",
                "Priority": "CRITICAL",
                "Financial_Opportunity": f"${opportunity_risk_savings:,.2f}",
                "Usage_Frequency": f"{asset.usage.query_count} queries/mo",
                "Owner": owner_str,
                "Steward": steward_str,
                "Action_Required": "Contains sensitive classification (PII/Confidential) but has NO owner assigned. Assign a Business Owner immediately.",
                "Catalog_URL": catalog_url
            })
            
        # PII Classification Mismatch: PII flagged as Public
        has_pii = any("pii" in c.lower() for c in asset.classifications)
        has_public = any("public" in c.lower() for c in asset.classifications)
        if has_pii and has_public:
            opportunity_risk_savings = roi.get("opportunity_risk_savings", 0.0)
            rows.append({
                "Asset_ID": asset_id,
                "Asset_Name": asset.name,
                "Asset_Type": asset.asset_type,
                "Source_Platform": platform,
                "Remediation_Category": "PII_CLASSIFICATION_MISMATCH",
                "Priority": "CRITICAL",
                "Financial_Opportunity": f"${opportunity_risk_savings:,.2f}",
                "Usage_Frequency": f"{asset.usage.query_count} queries/mo",
                "Owner": owner_str,
                "Steward": steward_str,
                "Action_Required": "CRITICAL RISK: Contains sensitive PII classification but is also flagged as 'Public'. Correct the classification to 'Confidential' or 'Restricted' immediately.",
                "Catalog_URL": catalog_url
            })
            
        # 2. Missing steward
        if not steward_names:
            rows.append({
                "Asset_ID": asset_id,
                "Asset_Name": asset.name,
                "Asset_Type": asset.asset_type,
                "Source_Platform": platform,
                "Remediation_Category": "MISSING_STEWARD",
                "Priority": "HIGH",
                "Financial_Opportunity": "N/A",
                "Usage_Frequency": f"{asset.usage.query_count} queries/mo",
                "Owner": owner_str,
                "Steward": steward_str,
                "Action_Required": "No Data Steward assigned to catalog metadata. Recruit/assign a steward.",
                "Catalog_URL": catalog_url
            })
            
        # 3. Storage ROT
        if is_rot:
            opportunity_storage_savings = roi.get("opportunity_storage_savings", 0.0)
            rows.append({
                "Asset_ID": asset_id,
                "Asset_Name": asset.name,
                "Asset_Type": asset.asset_type,
                "Source_Platform": platform,
                "Remediation_Category": "STORAGE_ROT",
                "Priority": "LOW",
                "Financial_Opportunity": f"${opportunity_storage_savings:,.2f}",
                "Usage_Frequency": f"{asset.usage.query_count} queries/mo",
                "Owner": owner_str,
                "Steward": steward_str,
                "Action_Required": "Asset is inactive (>180 days since last access) with low usage. Initiate decommissioning/archiving check to recover storage.",
                "Catalog_URL": catalog_url
            })
            
        # 4. Zero DQ rules configured on active asset
        if asset.usage.query_count > 0 and asset.data_quality.rules_run == 0:
            opportunity_dq_savings = roi.get("opportunity_dq_savings", 0.0)
            rows.append({
                "Asset_ID": asset_id,
                "Asset_Name": asset.name,
                "Asset_Type": asset.asset_type,
                "Source_Platform": platform,
                "Remediation_Category": "ZERO_DQ_RULES",
                "Priority": "HIGH",
                "Financial_Opportunity": f"${opportunity_dq_savings:,.2f}",
                "Usage_Frequency": f"{asset.usage.query_count} queries/mo",
                "Owner": owner_str,
                "Steward": steward_str,
                "Action_Required": "Asset is queried actively but has NO Data Quality rules run. Configure baseline profiling and validation monitors.",
                "Catalog_URL": catalog_url
            })
            
        # 5. Low DQ Pass Rate (Failing Rules)
        elif asset.data_quality.rules_run > 0 and asset.data_quality.pass_rate < 0.95:
            opportunity_dq_savings = roi.get("opportunity_dq_savings", 0.0)
            rows.append({
                "Asset_ID": asset_id,
                "Asset_Name": asset.name,
                "Asset_Type": asset.asset_type,
                "Source_Platform": platform,
                "Remediation_Category": "FAILING_DQ_RULES",
                "Priority": "HIGH",
                "Financial_Opportunity": f"${opportunity_dq_savings:,.2f}",
                "Usage_Frequency": f"{asset.usage.query_count} queries/mo",
                "Owner": owner_str,
                "Steward": steward_str,
                "Action_Required": f"Data Quality rules are failing (pass rate: {asset.data_quality.pass_rate * 100:.1f}%). Audit source pipeline data.",
                "Catalog_URL": catalog_url
            })
            
        # 6. Missing Lineage
        if lineage_score == 0.0 and asset.usage.query_count > 10:
            opportunity_rca_savings = roi.get("opportunity_rca_savings", 0.0)
            rows.append({
                "Asset_ID": asset_id,
                "Asset_Name": asset.name,
                "Asset_Type": asset.asset_type,
                "Source_Platform": platform,
                "Remediation_Category": "MISSING_LINEAGE",
                "Priority": "MEDIUM",
                "Financial_Opportunity": f"${opportunity_rca_savings:,.2f}",
                "Usage_Frequency": f"{asset.usage.query_count} queries/mo",
                "Owner": owner_str,
                "Steward": steward_str,
                "Action_Required": "Asset has high usage but zero upstream/downstream lineage. Setup automated ETL lineage harvest.",
                "Catalog_URL": catalog_url
            })
            
        # 7. Poor Documentation
        if doc_score < 70.0:
            opportunity_discovery_savings = roi.get("opportunity_discovery_savings", 0.0)
            rows.append({
                "Asset_ID": asset_id,
                "Asset_Name": asset.name,
                "Asset_Type": asset.asset_type,
                "Source_Platform": platform,
                "Remediation_Category": "POOR_DOCUMENTATION",
                "Priority": "MEDIUM",
                "Financial_Opportunity": f"${opportunity_discovery_savings:,.2f}",
                "Usage_Frequency": f"{asset.usage.query_count} queries/mo",
                "Owner": owner_str,
                "Steward": steward_str,
                "Action_Required": f"Asset description is empty or too short (documentation score: {doc_score:.0f}%). Author standard business descriptions.",
                "Catalog_URL": catalog_url
            })
        
    # Write to CSV file
    fieldnames = [
        "Asset_ID", "Asset_Name", "Asset_Type", "Source_Platform",
        "Remediation_Category", "Priority", "Financial_Opportunity",
        "Usage_Frequency", "Owner", "Steward", "Action_Required", "Catalog_URL"
    ]
    
    with open(csv_output_file, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)
        
    print(f"Successfully generated Remediation Task Registry CSV at '{csv_output_file}'")

def build_pdf_report(platform, input_file, output_file):
    # 1. Load and parse raw metadata
    if not os.path.exists(input_file):
        print(f"Error: Input file '{input_file}' not found.")
        sys.exit(1)
        
    with open(input_file, "r") as f:
        raw_data = json.load(f)
        
    if isinstance(raw_data, dict):
        if platform in raw_data:
            raw_assets = raw_data[platform]
        else:
            raw_assets = [raw_data]
    elif isinstance(raw_data, list):
        raw_assets = raw_data
    else:
        print("Error: Input JSON must be a list of assets or a nested platform dict.")
        sys.exit(1)
        
    # Map to Canonical Model
    canonical_assets = []
    for asset in raw_assets:
        try:
            canonical_asset = map_raw_to_canonical(platform, asset)
            canonical_assets.append(canonical_asset)
        except Exception as e:
            # Skip invalid assets
            continue
            
    if not canonical_assets:
        print(f"Error: No assets mapped to canonical model for platform '{platform}'.")
        sys.exit(1)
        
    # Run Scoring
    scoring_engine = GovernanceScoringEngine()
    scored_df = scoring_engine.score_all_assets(canonical_assets)
    
    # Run ROI
    roi_engine = ROICalculationEngine()
    roi_df = roi_engine.calculate_catalog_roi(canonical_assets, scored_df)
    
    # Compute Telemetry Confidence Score
    tcs_result = calculate_tcs(canonical_assets)

    # Run Maturity Assessment Engine
    maturity_engine = MaturityAssessmentEngine()
    maturity_results = maturity_engine.assess_maturity(canonical_assets)
    reco_results = maturity_engine.generate_recommendations_and_gaps(maturity_results)
    discipline_details = maturity_engine.generate_discipline_details(maturity_results)
    
    # Aggregated calculations
    total_assets = len(canonical_assets)
    
    # Calculate asset type breakdown for the summary (bulleted list)
    type_counts = {}
    for asset in canonical_assets:
        type_counts[asset.asset_type] = type_counts.get(asset.asset_type, 0) + 1
    sorted_types = sorted(type_counts.items(), key=lambda x: x[1], reverse=True)
    bullet_parts = []
    for t_name, t_count in sorted_types:
        suffix = "s" if not t_name.endswith("s") else ""
        bullet_parts.append(f"&nbsp;&nbsp;&bull;&nbsp;<b>{t_count}</b> {t_name}{suffix}")
    bullet_list_str = "<br/>" + "<br/>".join(bullet_parts) if bullet_parts else ""

    avg_doc = scored_df["documentation_score"].mean()
    avg_dq = scored_df["data_quality_score"].mean()
    avg_lineage = scored_df["lineage_score"].mean()
    avg_risk = scored_df["security_risk_score"].mean()
    avg_ghi = scored_df["governance_health_index"].mean()
    
    total_realized_savings = roi_df["total_realized_savings"].sum()
    total_opportunity_savings = roi_df["total_opportunity_savings"].sum()
    operating_cost = roi_engine.platform_costs.get(platform, 0.0)
    net_realized_roi = total_realized_savings - operating_cost
    roi_percentage = (net_realized_roi / operating_cost) * 100.0 if operating_cost > 0 else 0.0
    
    metadata_maturity = maturity_results["disciplines"].get("metadata_management", {}).get("score", 0.0)
    dq_maturity = maturity_results["disciplines"].get("data_quality", {}).get("score", 0.0)
    overall_maturity = maturity_results["overall_maturity_score"]
    
    # Build Document
    doc = SimpleDocTemplate(
        output_file,
        pagesize=letter,
        leftMargin=54,
        rightMargin=54,
        topMargin=54,
        bottomMargin=54
    )
    
    styles = getSampleStyleSheet()
    
    # Custom styles
    title_style = ParagraphStyle(
        'DocTitle',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=20,
        leading=24,
        textColor=colors.HexColor("#1A365D"),
        spaceAfter=4
    )
    
    subtitle_style = ParagraphStyle(
        'DocSubtitle',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=11,
        leading=15,
        textColor=colors.HexColor("#4A5568"),
        spaceAfter=15
    )
    
    heading_style = ParagraphStyle(
        'Heading2',
        parent=styles['Heading2'],
        fontName='Helvetica-Bold',
        fontSize=12,
        leading=16,
        textColor=colors.HexColor("#1A365D"),
        spaceBefore=14,
        spaceAfter=6,
        keepWithNext=True
    )
    
    body_style = ParagraphStyle(
        'BodyTextCustom',
        parent=styles['BodyText'],
        fontName='Helvetica',
        fontSize=9.5,
        leading=13.5,
        textColor=colors.HexColor("#2D3748")
    )
    
    th_style = ParagraphStyle(
        'TableHeader',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=9,
        leading=12,
        textColor=colors.white
    )
    
    td_style = ParagraphStyle(
        'TableCell',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=9,
        leading=12,
        textColor=colors.HexColor("#2D3748")
    )
    
    td_indented_style = ParagraphStyle(
        'TableCellIndented',
        parent=td_style,
        leftIndent=12
    )
    
    td_bold_style = ParagraphStyle(
        'TableCellBold',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=9,
        leading=12,
        textColor=colors.HexColor("#1A365D")
    )
    
    td_def_style = ParagraphStyle(
        'TableCellDefinition',
        parent=styles['Normal'],
        fontName='Helvetica-Oblique',
        fontSize=8,
        leading=10,
        textColor=colors.HexColor("#718096"),
        leftIndent=20
    )

    bullet_style = ParagraphStyle(
        'BulletCustom',
        parent=styles['BodyText'],
        fontName='Helvetica',
        fontSize=9,
        leading=12,
        textColor=colors.HexColor("#2D3748"),
        leftIndent=15
    )
    
    story = []
    
    # 1. Header Section
    story.append(Paragraph("DATA GOVERNANCE MATURITY & ROI EXECUTIVE REPORT", title_style))
    story.append(Paragraph(f"Platform: <b>{platform.upper()}</b> | Scope: Enterprise Implementation | Evaluation Date: {datetime.now().strftime('%Y-%m-%d')}", subtitle_style))
    
    # 2. Executive Summary Box
    summary_text = (
        f"<b>Executive Summary:</b> An automated audit-ready maturity assessment was conducted on "
        f"<b>{total_assets}</b> data assets managed by {platform.title()} with the following inventory breakdown:"
        f"{bullet_list_str}<br/><br/>"
        f"The implementation achieves a <b>Maturity Score of {overall_maturity:.2f}/5.0</b> (Documentation Health: {avg_doc:.1f}%, DQ Pass Rate: {maturity_results['audit_trail']['raw_metrics']['pass_rate']:.1f}%). "
        f"Financially, the program has generated <b>{format_currency(total_realized_savings)}</b> in realized business value "
        f"against an estimated annual operating cost of "
        f"<b>{format_currency(operating_cost)}</b>, yielding a net realized value of <b>{format_currency(net_realized_roi)}</b>. "
        f"Additionally, the engine has identified <b>{format_currency(total_opportunity_savings)}</b> in unrealized, actionable opportunity savings "
        f"that can be unlocked through targeted remediation efforts."
    )
    
    summary_table = Table([[Paragraph(summary_text, ParagraphStyle('SummaryText', parent=body_style, textColor=colors.HexColor("#2C5282")))]], colWidths=[504])
    summary_table.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,-1), colors.HexColor("#EBF8FF")), # Light blue box
        ('PADDING', (0,0), (-1,-1), 12),
        ('BOX', (0,0), (-1,-1), 1, colors.HexColor("#BEE3F8")),
    ]))
    story.append(summary_table)
    story.append(Spacer(1, 15))
    
    # 3. Governance Maturity Scores Section
    story.append(Paragraph("I. Discipline-Level Data Governance Maturity Dashboard", heading_style))
    story.append(Paragraph("Scores are computed across critical governance disciplines mapped directly from catalog metadata using transparent, auditable rules. Health indicators are nested under their respective disciplines:", body_style))
    story.append(Spacer(1, 6))
    
    def get_maturity_status(score):
        if score >= 4.0:
            return "Optimized", "#48BB78"  # Green
        elif score >= 2.5:
            return "Amber", "#D69E2E"  # Amber/Dark Yellow
        else:
            return "Action Needed", "#F56565"  # Red
            
    def get_indicator_status(val, thresholds):
        if val >= thresholds[3]:
            return "Green", "#48BB78"
        elif val >= thresholds[1]:
            return "Amber", "#D69E2E"
        else:
            return "Red", "#F56565"

    consolidated_dashboard_data = [
        [
            Paragraph("Governance Discipline / Health Indicator", th_style), 
            Paragraph("Weight", th_style), 
            Paragraph("Raw Value / Score", th_style), 
            Paragraph("Status", th_style)
        ]
    ]
    
    table_styles = [
        ('BACKGROUND', (0,0), (-1,0), colors.HexColor("#1A365D")), # Dark navy header
        ('ALIGN', (0,0), (-1,-1), 'LEFT'),
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
        ('GRID', (0,0), (-1,-1), 0.5, colors.HexColor("#E2E8F0")),
        ('PADDING', (0,0), (-1,-1), 5),
    ]

    row_idx = 1
    for disp_key, disp_data in maturity_results["disciplines"].items():
        disp_name = disp_data["name"]
        disp_score = disp_data["score"]
        disp_weight = disp_data["weight"]
        disp_status, disp_color = get_maturity_status(disp_score)
        
        # Add discipline row
        consolidated_dashboard_data.append([
            Paragraph(f"<b>{disp_name}</b>", td_bold_style),
            Paragraph(f"<b>{disp_weight * 100:.0f}%</b>", td_bold_style),
            Paragraph(f"<b>{disp_score:.2f} / 5.0</b>", td_bold_style),
            Paragraph(f"<font color='{disp_color}'><b>{disp_status}</b></font>", td_bold_style)
        ])
        table_styles.append(('BACKGROUND', (0, row_idx), (-1, row_idx), colors.HexColor("#EBF8FF")))
        row_idx += 1
        
        indicator_descriptions = {
            "documentation_coverage": "Definition: Percentage of cataloged assets with active business descriptions.",
            "ownership_coverage": "Definition: Percentage of assets with an assigned business or technical owner.",
            "glossary_linkage": "Definition: Percentage of assets mapped to standardized glossary terms.",
            "classification_coverage": "Definition: Percentage of fields with security/governance classification tags.",
            "rule_coverage": "Definition: Percentage of critical assets with active data quality rules.",
            "pass_rate": "Definition: Percentage of executed data quality checks that passed successfully.",
            "sensitive_data_governance": "Definition: Percentage of sensitive assets with active owners and security tags.",
            "role_access_control": "Definition: Percentage of assets with both owner and classification tags assigned.",
            "stewardship_assignment": "Definition: Percentage of assets with an assigned data steward.",
            "lineage_coverage": "Definition: Percentage of assets with mapped lineage relationships.",
            "rot_identification": "Definition: Percentage of cataloged storage assets that are active (non-ROT).",
            "storage_tier_optimization": "Definition: Percentage of cold storage assets on cost-optimized tiers."
        }

        # Add indicators under this discipline
        for ind_key, ind_data in disp_data["indicators"].items():
            ind_name = ind_data["name"]
            raw_val = ind_data["raw_percentage"]
            ind_score = ind_data["score"]
            ind_weight = ind_data["weight"]
            thresholds = ind_data["thresholds"]
            
            ind_status, ind_color = get_indicator_status(raw_val, thresholds)
            
            consolidated_dashboard_data.append([
                Paragraph(f"↳ {ind_name}", td_indented_style),
                Paragraph(f"{ind_weight * 100:.0f}%", td_style),
                Paragraph(f"{raw_val:.1f}% (Score: {ind_score:.1f})", td_style),
                Paragraph(f"<font color='{ind_color}'><b>{ind_status}</b></font>", td_bold_style)
            ])
            row_idx += 1

            desc = indicator_descriptions.get(ind_key, "")
            if desc:
                consolidated_dashboard_data.append([
                    Paragraph(desc, td_def_style),
                    "", "", ""
                ])
                table_styles.append(('SPAN', (0, row_idx), (-1, row_idx)))
                table_styles.append(('TOPPADDING', (0, row_idx), (-1, row_idx), 0))
                table_styles.append(('BOTTOMPADDING', (0, row_idx), (-1, row_idx), 6))
                row_idx += 1
            
    # Add Overall Maturity row
    overall_status, overall_color = get_maturity_status(overall_maturity)
    consolidated_dashboard_data.append([
        Paragraph("<b>Overall Maturity Index</b>", td_bold_style),
        Paragraph("<b>100%</b>", td_bold_style),
        Paragraph(f"<b>{overall_maturity:.2f} / 5.0</b>", td_bold_style),
        Paragraph(f"<font color='{overall_color}'><b>{overall_status}</b></font>", td_bold_style)
    ])
    table_styles.append(('BACKGROUND', (0, row_idx), (-1, row_idx), colors.HexColor("#EDF2F7")))
    
    t_consolidated = Table(consolidated_dashboard_data, colWidths=[220, 60, 120, 104])
    t_consolidated.setStyle(TableStyle(table_styles))
    
    # Legend box for Status and Colors
    legend_style = ParagraphStyle(
        'LegendStyle',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=8,
        leading=10,
        textColor=colors.HexColor("#4A5568")
    )
    legend_data = [
        [
            Paragraph("<b>Pillar Status Legend:</b>", legend_style),
            Paragraph("<font color='#48BB78'>■</font> <b>Optimized</b> (Score &ge; 4.0)", legend_style),
            Paragraph("<font color='#D69E2E'>■</font> <b>Amber</b> (Score 2.5 - 3.9)", legend_style),
            Paragraph("<font color='#F56565'>■</font> <b>Action Needed</b> (Score &lt; 2.5)", legend_style)
        ],
        [
            Paragraph("<b>Indicator Status Legend:</b>", legend_style),
            Paragraph("<font color='#48BB78'>■</font> <b>Green</b> (Target Met)", legend_style),
            Paragraph("<font color='#D69E2E'>■</font> <b>Amber</b> (Warning)", legend_style),
            Paragraph("<font color='#F56565'>■</font> <b>Red</b> (Critical Gap)", legend_style)
        ]
    ]
    t_legend = Table(legend_data, colWidths=[120, 128, 128, 128])
    t_legend.setStyle(TableStyle([
        ('ALIGN', (0,0), (-1,-1), 'LEFT'),
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
        ('BACKGROUND', (0,0), (-1,-1), colors.HexColor("#F7FAFC")),
        ('PADDING', (0,0), (-1,-1), 5),
        ('BOX', (0,0), (-1,-1), 0.5, colors.HexColor("#E2E8F0")),
    ]))
    
    story.append(KeepTogether([t_consolidated, Spacer(1, 8), t_legend]))
    story.append(Spacer(1, 15))
    
    # 4. Program Financial Performance Section
    # ── TCS-gated section header ──────────────────────────────────────────────
    tcs_badge_styles = {
        "high":   ("#276749", "#C6F6D5", "#9AE6B4"),  # green text, bg, border
        "medium": ("#744210", "#FEFCBF", "#F6E05E"),  # amber
        "low":    ("#822727", "#FFF5F5", "#FEB2B2"),  # red
    }
    tcs_text_color, tcs_bg_color, tcs_border_color = tcs_badge_styles[tcs_result.tier]

    if tcs_result.tier == "high":
        fin_section_subtitle = (
            f"<font color='{tcs_text_color}'><b>&#10003; High-Confidence Audited Metrics</b></font> — "
            f"<b>Telemetry Confidence Score (TCS): {tcs_result.display_pct}</b> ({tcs_result.complete_assets}/{tcs_result.total_assets} assets have complete telemetry).<br/><br/>"
            f"The Telemetry Confidence Score (TCS) represents the verified coverage of metadata and telemetry logs harvested from our data infrastructure. It serves as an auditability safeguard, ensuring that all reported financial ROI calculations are backed by concrete logs rather than speculative estimations. "
            f"All ROI figures below are fully supported by infrastructure telemetry."
        )
    elif tcs_result.tier == "medium":
        fin_section_subtitle = (
            f"<font color='{tcs_text_color}'><b>&#9888; Conservative Estimates</b></font> — "
            f"<b>Telemetry Confidence Score (TCS): {tcs_result.display_pct}</b> ({tcs_result.complete_assets}/{tcs_result.total_assets} assets have complete telemetry).<br/><br/>"
            f"The Telemetry Confidence Score (TCS) represents the verified coverage of metadata and telemetry logs harvested from our data infrastructure. It serves as an auditability safeguard, ensuring that all reported financial ROI calculations are backed by concrete logs rather than speculative estimations. "
            f"Currently, complete infrastructure telemetry is missing for <b>{tcs_result.missing_display_pct}</b> of assets, meaning ROI figures marked * are conservative projections."
        )
    else:
        fin_section_subtitle = (
            f"<font color='{tcs_text_color}'><b>&#9888; ROI Calculations Suspended</b></font> — "
            f"<b>Telemetry Confidence Score (TCS): {tcs_result.display_pct}</b> ({tcs_result.complete_assets}/{tcs_result.total_assets} assets have complete telemetry).<br/><br/>"
            f"The Telemetry Confidence Score (TCS) represents the verified coverage of metadata and telemetry logs harvested from our data infrastructure. It serves as an auditability safeguard, ensuring that all reported financial ROI calculations are backed by concrete logs rather than speculative estimations. "
            f"Financial metrics require &ge;50% telemetry completeness to be meaningful and are suspended to prevent misleading decisions."
        )

    # Append component-specific coverage details
    size_cov = tcs_result.size_coverage * 100.0
    query_cov = tcs_result.query_coverage * 100.0
    owner_cov = tcs_result.owner_coverage * 100.0
    lineage_cov = tcs_result.lineage_coverage * 100.0
    steward_cov = maturity_results.get("audit_trail", {}).get("raw_metrics", {}).get("stewardship_assignment", 0.0)
    doc_cov = maturity_results.get("audit_trail", {}).get("raw_metrics", {}).get("documentation_coverage", 0.0)
    dq_cov = maturity_results.get("audit_trail", {}).get("raw_metrics", {}).get("rule_coverage", 0.0)
    glossary_cov = maturity_results.get("audit_trail", {}).get("raw_metrics", {}).get("glossary_linkage", 0.0)
    class_cov = maturity_results.get("audit_trail", {}).get("raw_metrics", {}).get("classification_coverage", 0.0)

    fin_section_subtitle += (
        f"<br/><br/><b>Telemetry & Metadata Coverage Breakdown:</b><br/>"
        f"&bull; <b>Size Coverage ({size_cov:.1f}%):</b> Measures assets with populated physical size (drives storage optimization/ROT savings).<br/>"
        f"&bull; <b>Query Logs ({query_cov:.1f}%):</b> Measures assets with active query history (drives data discovery productivity and compute optimization).<br/>"
        f"&bull; <b>Owner Assignment ({owner_cov:.1f}%):</b> Measures assets with defined technical/business owners (drives compliance and risk savings).<br/>"
        f"&bull; <b>Lineage Trace ({lineage_cov:.1f}%):</b> Measures assets with mapped lineage relationships (drives Root Cause Analysis time savings).<br/>"
        f"&bull; <b>Stewardship Assignment ({steward_cov:.1f}%):</b> Measures assets with actively assigned data stewards (drives daily metadata upkeep).<br/>"
        f"&bull; <b>Documentation Coverage ({doc_cov:.1f}%):</b> Measures assets with robust description text (drives catalog search and discovery speed).<br/>"
        f"&bull; <b>DQ Rule Coverage ({dq_cov:.1f}%):</b> Measures assets with active data quality profile runs (drives DQ incident avoidance savings).<br/>"
        f"&bull; <b>Glossary Linkage ({glossary_cov:.1f}%):</b> Measures assets mapped to business glossary terms (drives semantic search accuracy).<br/>"
        f"&bull; <b>Classification Coverage ({class_cov:.1f}%):</b> Measures assets carrying active classifications (drives sensitive data compliance)."
    )

    story.append(Paragraph("II. Program Financial Performance & ROI Analysis", heading_style))

    tcs_banner_style = ParagraphStyle(
        'TCSBanner',
        parent=body_style,
        textColor=colors.HexColor(tcs_text_color),
    )
    tcs_banner_table = Table(
        [[Paragraph(fin_section_subtitle, tcs_banner_style)]],
        colWidths=[504]
    )
    tcs_banner_table.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,-1), colors.HexColor(tcs_bg_color)),
        ('PADDING', (0,0), (-1,-1), 10),
        ('BOX', (0,0), (-1,-1), 1, colors.HexColor(tcs_border_color)),
    ]))
    story.append(tcs_banner_table)
    story.append(Spacer(1, 8))

    # ── Render financial table (suppressed for TCS < 50%) ────────────────────
    if tcs_result.tier == "low":
        suspended_text = (
            "<b>ROI Calculations suspended due to missing infrastructure metadata.</b><br/><br/>"
            f"Only <b>{tcs_result.display_pct}</b> of cataloged assets provide the four required telemetry signals "
            f"(Size, Query Logs, Lineage, Owners). Financial ROI projections drawn from incomplete data carry "
            f"an unacceptable margin of error and are withheld to prevent misleading executive decisions.<br/><br/>"
            f"<b>Recommended action:</b> Focus on completing metadata ingest. Target indicators to resolve first:<br/>"
            f"&nbsp;&nbsp;&bull;&nbsp;Assign owners to all unowned assets (see Remediation Registry, category MISSING_STEWARD)<br/>"
            f"&nbsp;&nbsp;&bull;&nbsp;Register physical size for all storage assets<br/>"
            f"&nbsp;&nbsp;&bull;&nbsp;Enable query log integration on the catalog connector<br/>"
            f"&nbsp;&nbsp;&bull;&nbsp;Configure automated lineage harvest for active pipelines<br/><br/>"
            f"ROI calculations will activate automatically once TCS exceeds 50%."
        )
        suspended_table = Table(
            [[Paragraph(suspended_text, ParagraphStyle('Suspended', parent=body_style, textColor=colors.HexColor("#822727")))]],
            colWidths=[504]
        )
        suspended_table.setStyle(TableStyle([
            ('BACKGROUND', (0,0), (-1,-1), colors.HexColor("#FFF5F5")),
            ('PADDING', (0,0), (-1,-1), 14),
            ('BOX', (0,0), (-1,-1), 1.5, colors.HexColor("#FC8181")),
            ('LINELEFT', (0,0), (0,-1), 4, colors.HexColor("#E53E3E")),
        ]))
        story.append(suspended_table)
    else:
        story.append(Paragraph(
            "The value realized through metadata-driven automation and risk mitigation compared to software licensing and overhead operating costs:",
            body_style
        ))
        story.append(Spacer(1, 4))

        # Asterisk suffix applied to monetary cells when TCS is medium
        amt_suffix = " *" if tcs_result.tier == "medium" else ""

        financial_data = [
            [Paragraph("Financial Metric Category", th_style), Paragraph("Amount ($)", th_style), Paragraph("Value Explanation", th_style)],
            [
                Paragraph("Annual Operating Cost", td_style),
                Paragraph(f"{format_currency(operating_cost)}", td_bold_style),
                Paragraph("Fixed software licensing and support overhead cost.", td_style)
            ],
            [
                Paragraph("Realized Discovery Savings", td_style),
                Paragraph(f"{format_currency(roi_df['realized_discovery_savings'].sum())}{amt_suffix}", td_bold_style),
                Paragraph("Productivity savings from faster data discovery.", td_style)
            ],
            [
                Paragraph("Realized DQ Incident Avoidance", td_style),
                Paragraph(f"{format_currency(roi_df['realized_dq_savings'].sum())}{amt_suffix}", td_bold_style),
                Paragraph("Savings from avoiding pipeline failures and business downtime.", td_style)
            ],
            [
                Paragraph("Realized Risk Avoidance", td_style),
                Paragraph(f"{format_currency(roi_df['realized_risk_savings'].sum())}{amt_suffix}", td_bold_style),
                Paragraph("Mitigated risk of security breaches and regulatory non-compliance.", td_style)
            ],
            [
                Paragraph("Realized Compute Optimization", td_style),
                Paragraph(f"{format_currency(roi_df['realized_compute_savings'].sum())}{amt_suffix}", td_bold_style),
                Paragraph("Warehouse credit waste avoided via data quality monitoring.", td_style)
            ],
            [
                Paragraph("Realized Root Cause Analysis (RCA) Savings", td_style),
                Paragraph(f"{format_currency(roi_df['realized_rca_savings'].sum())}{amt_suffix}", td_bold_style),
                Paragraph("Developer hours saved tracing pipeline failures using lineage.", td_style)
            ],
            [
                Paragraph("<b>Net Realized Program Value</b>", td_bold_style),
                Paragraph(f"<b>{format_currency(net_realized_roi)}{amt_suffix}</b>", td_bold_style),
                Paragraph("<b>Net financial return of the program.</b>", td_bold_style)
            ],
            [
                Paragraph("<b>Return on Investment (ROI)</b>", td_bold_style),
                Paragraph(f"<b>{roi_percentage:.2f}%{amt_suffix}</b>", td_bold_style),
                Paragraph("<b>Program efficiency ratio.</b>", td_bold_style)
            ],
            [
                Paragraph("Unrealized Opportunity Value", td_style),
                Paragraph(f"{format_currency(total_opportunity_savings)}{amt_suffix}", td_bold_style),
                Paragraph("Value pipeline achievable through remediation tasks.", td_style)
            ]
        ]

        t_financial = Table(financial_data, colWidths=[180, 100, 224])
        t_financial.setStyle(TableStyle([
            ('BACKGROUND', (0,0), (-1,0), colors.HexColor("#1A365D")),
            ('ALIGN', (0,0), (-1,-1), 'LEFT'),
            ('PADDING', (0,0), (-1,-1), 5),
            ('GRID', (0,0), (-1,-1), 0.5, colors.HexColor("#E2E8F0")),
            ('ROWBACKGROUNDS', (0,1), (-1,-2), [colors.white, colors.HexColor("#F7FAFC")]),
            ('BACKGROUND', (0,7), (-1,8), colors.HexColor("#EBF8FF")),
        ]))
        story.append(KeepTogether(t_financial))

        if tcs_result.tier == "medium":
            warning_text = (
                f"* <b>Conservative estimate:</b> Complete infrastructure telemetry is missing for "
                f"<b>{tcs_result.missing_display_pct}</b> of assets. "
                f"Figures above represent a lower-bound projection. Improve telemetry coverage to unlock full ROI visibility."
            )
            warning_table = Table(
                [[Paragraph(warning_text, ParagraphStyle('WarningNote', parent=body_style, textColor=colors.HexColor("#744210")))]],
                colWidths=[504]
            )
            warning_table.setStyle(TableStyle([
                ('BACKGROUND', (0,0), (-1,-1), colors.HexColor("#FEFCBF")),
                ('PADDING', (0,0), (-1,-1), 8),
                ('BOX', (0,0), (-1,-1), 1, colors.HexColor("#F6E05E")),
                ('LINELEFT', (0,0), (0,-1), 3, colors.HexColor("#D69E2E")),
            ]))
            story.append(Spacer(1, 6))
            story.append(warning_table)

    story.append(Spacer(1, 15))
    
    # Define styles for the Domain Detail Section
    subheading_style = ParagraphStyle(
        'SubheadingCustom',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=11,
        leading=14,
        textColor=colors.HexColor("#1A365D"),
    )
    score_style = ParagraphStyle(
        'ScoreCustom',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=11,
        leading=14,
        alignment=2 # Right aligned
    )
    col_header_style = ParagraphStyle(
        'ColHeader',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=8,
        leading=10,
        textColor=colors.HexColor("#718096"),
        spaceAfter=4
    )
    col_body_style = ParagraphStyle(
        'ColBody',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=8.5,
        leading=12,
        textColor=colors.HexColor("#2D3748")
    )

    def create_pill_box(text, bg_color_hex):
        p_style = ParagraphStyle(
            'PillText',
            parent=styles['Normal'],
            fontName='Helvetica',
            fontSize=8,
            leading=11,
            textColor=colors.HexColor("#2D3748") # Dark gray/black text
        )
        p = Paragraph(text, p_style)
        t = Table([[p]], colWidths=[155])
        t.setStyle(TableStyle([
            ('BACKGROUND', (0,0), (-1,-1), colors.HexColor(bg_color_hex)),
            ('BOTTOMPADDING', (0,0), (-1,-1), 4),
            ('TOPPADDING', (0,0), (-1,-1), 4),
            ('LEFTPADDING', (0,0), (-1,-1), 6),
            ('RIGHTPADDING', (0,0), (-1,-1), 6),
            ('BOX', (0,0), (-1,-1), 0.5, colors.HexColor(bg_color_hex)),
        ]))
        return t

    # 5. Domain Detail Section
    story.append(Paragraph("III. Discipline-Level Domain Detail", heading_style))
    story.append(Spacer(1, 4))
    
    for idx, (disp_key, disp_info) in enumerate(discipline_details.items(), 1):
        disp_name = maturity_results["disciplines"].get(disp_key, {}).get("name", disp_key.replace("_", " ").title())
        score_val = maturity_results["disciplines"].get(disp_key, {}).get("score", 0.0)
        
        # Decide score color
        if score_val >= 4.0:
            score_color = "#48BB78" # Green
        elif score_val >= 2.5:
            score_color = "#D69E2E" # Amber
        else:
            score_color = "#C53030" # Red
            
        header_table_data = [
            [
                Paragraph(f"{idx} · {disp_name}", subheading_style),
                Paragraph(f"<font color='{score_color}'>Score: {score_val:.1f} / 5</font>", score_style)
            ]
        ]
        t_header = Table(header_table_data, colWidths=[300, 204])
        t_header.setStyle(TableStyle([
            ('ALIGN', (0,0), (-1,-1), 'LEFT'),
            ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
            ('BOTTOMPADDING', (0,0), (-1,-1), 4),
            ('TOPPADDING', (0,0), (-1,-1), 0),
            ('LEFTPADDING', (0,0), (-1,-1), 0),
            ('RIGHTPADDING', (0,0), (-1,-1), 0),
        ]))
        
        # 2-column detail table for strengths & gaps
        s_flowables = []
        for s in disp_info["strengths"]:
            s_flowables.append(create_pill_box(f"• {s}", "#E6F4EA")) # Light green
            s_flowables.append(Spacer(1, 4))
        if s_flowables:
            s_flowables.pop()
            
        g_flowables = []
        for g in disp_info["gaps"]:
            g_flowables.append(create_pill_box(f"• {g}", "#FCE8E6")) # Light red
            g_flowables.append(Spacer(1, 4))
        if g_flowables:
            g_flowables.pop()

        actions_text = "<br/>".join(disp_info["actions"])
        
        p_reasoning_header = Paragraph("REASONING & CONTEXT", col_header_style)
        p_reasoning_body = Paragraph(disp_info["reasoning"], col_body_style)
        
        sg_data = [
            [
                Paragraph("STRENGTHS", col_header_style),
                Paragraph("KEY GAPS / RISKS", col_header_style)
            ],
            [
                s_flowables if s_flowables else Paragraph("None identified", col_body_style),
                g_flowables if g_flowables else Paragraph("None identified", col_body_style)
            ]
        ]
        t_sg = Table(sg_data, colWidths=[248, 248])
        t_sg.setStyle(TableStyle([
            ('VALIGN', (0,0), (-1,-1), 'TOP'),
            ('LEFTPADDING', (0,0), (-1,-1), 0),
            ('RIGHTPADDING', (0,0), (-1,-1), 8),
            ('TOPPADDING', (0,0), (-1,-1), 2),
            ('BOTTOMPADDING', (0,0), (-1,-1), 6),
        ]))
        
        p_actions_header = Paragraph("RECOMMENDED REMEDIATION ACTIONS", col_header_style)
        p_actions_body = Paragraph(actions_text, col_body_style)
        
        # Keep header and reasoning together to prevent orphan headers
        story.append(KeepTogether([
            t_header,
            Spacer(1, 4),
            p_reasoning_header,
            Spacer(1, 2),
            p_reasoning_body,
            Spacer(1, 6)
        ]))
        
        story.append(t_sg)
        story.append(Spacer(1, 4))
        

        # Keep actions header and actions text together
        story.append(KeepTogether([
            p_actions_header,
            Spacer(1, 2),
            p_actions_body,
            Spacer(1, 12)
        ]))

    # Top 3 Recommendations Section
    story.append(Paragraph("IV. Prioritized Action Plan & Recommendations", heading_style))
    story.append(Paragraph("Actionable remediation roadmap to accelerate maturity and unlock business value:", body_style))
    story.append(Spacer(1, 6))

    for i, reco in enumerate(reco_results["recommendations"], 1):
        reco_text = (
            f"<b>Recommendation {i}: {reco['recommendation']}</b><br/>"
            f"<i>Rationale:</i> {reco['rationale']}<br/>"
            f"<i>Business Impact:</i> {reco['expected_business_impact']}<br/>"
            f"<i>Maturity Improvement:</i> {reco['expected_maturity_improvement']}"
        )
        reco_table = Table([[Paragraph(reco_text, body_style)]], colWidths=[504])
        reco_table.setStyle(TableStyle([
            ('BACKGROUND', (0,0), (-1,-1), colors.HexColor("#F7FAFC")),
            ('PADDING', (0,0), (-1,-1), 8),
            ('BOX', (0,0), (-1,-1), 0.5, colors.HexColor("#E2E8F0")),
            ('LINELEFT', (0,0), (0,-1), 3, colors.HexColor("#3182CE")), # Blue accent left line
        ]))
        story.append(reco_table)
        story.append(Spacer(1, 6))
        
    # 6. Appendix: ROI Methodology & Assumptions
    from reportlab.platypus import PageBreak
    story.append(PageBreak())
    
    story.append(Paragraph("APPENDIX: ROI METHODOLOGY & ASSUMPTIONS", heading_style))
    story.append(Paragraph(
        "To ensure auditability, the calculations in this executive assessment are based on the "
        "following models and parameter mappings. These baselines are grounded in industry studies "
        "conducted by Gartner, Forrester, IBM Security, and standard cloud platform metrics.",
        body_style
    ))
    story.append(Spacer(1, 10))
    
    # Parameters table
    story.append(Paragraph("<b>Model Baseline Constants & Citation Sources</b>", ParagraphStyle('SubheadingAppendix', parent=body_style, fontName='Helvetica-Bold', spaceAfter=2)))
    params_data = [
        [Paragraph("Parameter Constants", th_style), Paragraph("Value", th_style), Paragraph("Research Context / Citation Source", th_style)],
        [Paragraph(f"TCO ({platform.upper()})", td_style), Paragraph(f"{format_currency(operating_cost)}/yr", td_style), Paragraph(f"Estimated annual operating cost (licensing + administration headcount support).", td_style)],
        [Paragraph("Loaded Analyst Rate", td_style), Paragraph(f"${roi_engine.hourly_analyst_rate:.2f}/hr", td_style), Paragraph("U.S. Labor Bureau senior loaded rate averages (1.35x multiplier).", td_style)],
        [Paragraph("Hours Saved per Search", td_style), Paragraph(f"{roi_engine.hours_saved_per_search:.1f} hrs", td_style), Paragraph("Forrester TEI data catalog productivity metrics.", td_style)],
        [Paragraph("Search/Discovery Ratio", td_style), Paragraph(f"{roi_engine.search_ratio * 100:.1f}%", td_style), Paragraph("Manual human query proportion versus scheduled pipeline queries.", td_style)],
        [Paragraph("Annual Storage Cost / GB", td_style), Paragraph(f"${roi_engine.storage_cost_per_gb_year:.2f}", td_style), Paragraph("Standard hot cloud object tier blended averages (AWS, Azure).", td_style)],
        [Paragraph("Data Quality Error Cost", td_style), Paragraph(f"${roi_engine.cost_per_dq_incident:,.2f}", td_style), Paragraph("Gartner & Monte Carlo operational cost studies.", td_style)],
        [Paragraph("Compliance Breach Penalty", td_style), Paragraph(f"${roi_engine.cost_per_data_breach:,.2f}", td_style), Paragraph("IBM Cost of Data Breach localized/tier-1 infraction fine.", td_style)]
    ]
    t_params = Table(params_data, colWidths=[150, 80, 274])
    t_params.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), colors.HexColor("#1A365D")),
        ('ALIGN', (0,0), (-1,-1), 'LEFT'),
        ('PADDING', (0,0), (-1,-1), 5),
        ('GRID', (0,0), (-1,-1), 0.5, colors.HexColor("#E2E8F0")),
        ('ROWBACKGROUNDS', (0,1), (-1,-1), [colors.white, colors.HexColor("#F7FAFC")]),
    ]))
    story.append(KeepTogether(t_params))
    story.append(Spacer(1, 10))
    
    # Formulas Explanation
    story.append(Paragraph("<b>Equations & Derivations</b>", ParagraphStyle('SubheadingAppendix2', parent=body_style, fontName='Helvetica-Bold', spaceAfter=2)))
    story.append(Paragraph("1. <b>Productivity Savings</b>: (Annual Queries * 0.05% search ratio) * 3.5 hrs saved * Analyst loaded rate * (Doc Score / 100). Grounded in Forrester's TEI frameworks.", bullet_style))
    story.append(Paragraph("2. <b>ROT Decommissioning</b>: Identified as size > 0, queries < 5/mo, and last accessed > 180 days. Savings = GB Size * $0.24/yr. Grounded in AWS/Azure storage tiers.", bullet_style))
    story.append(Paragraph("3. <b>DQ Incident Avoidance</b>: (Unmonitored baseline [5.0% probability] - Current probability) * $15k cost. Active DQ profiling drops current probability to 2.0% (for DQ >= 80%) or 0.0% (for DQ >= 95%). Grounded in Gartner data quality impact surveys.", bullet_style))
    story.append(Paragraph("4. <b>Risk Avoidance</b>: (Baseline breach prob. [5.0%] - Current prob.) * $150k breach penalty. Controls (ownership and classification) reduce probability to 1.0% (0.2% with active DQ checks). Grounded in IBM Security breach statistics and DAMA DMBOK principles.", bullet_style))
    story.append(Paragraph("5. <b>Compute Optimization</b>: Snowflake credit waste avoided on bad/unoptimized queries, calculated based on the active warehouse sizes, average credit rates ($3.00/credit), and active DQ monitoring rules.", bullet_style))
    story.append(Paragraph("6. <b>Net Program Value</b>: Net Value = Total Realized Savings - Annual Operating Cost.", bullet_style))
    story.append(Paragraph("7. <b>Return on Investment (ROI) %</b>: ROI % = (Net Realized Program Value / Annual Operating Cost) * 100.", bullet_style))
    story.append(Paragraph("8. <b>Unrealized Opportunity Value</b>: Sum of remaining discovery opportunity + DQ opportunity + Risk mitigation + ROT storage decommissioning savings.", bullet_style))
    story.append(Spacer(1, 10))
    
    # Governance Maturity Scoring Formulas
    story.append(Paragraph("<b>Discipline Maturity & Indicator Assessment Formulas</b>", ParagraphStyle('SubheadingAppendix3', parent=body_style, fontName='Helvetica-Bold', spaceAfter=2)))
    story.append(Paragraph("• <b>Documentation Coverage %</b>: (Assets with description >= 50 characters / Total Assets) * 100. Thresholds: [40, 60, 75, 90]%.", bullet_style))
    story.append(Paragraph("• <b>Ownership Assignment %</b>: (Assets with >= 1 owner / Total Assets) * 100. Thresholds: [40, 60, 75, 90]%.", bullet_style))
    story.append(Paragraph("• <b>Glossary Linkage %</b>: (Assets with >= 1 glossary term / Total Assets) * 100. Thresholds: [40, 60, 75, 90]%.", bullet_style))
    story.append(Paragraph("• <b>Classification Coverage %</b>: (Assets with >= 1 classification / Total Assets) * 100. Thresholds: [40, 60, 75, 90]%.", bullet_style))
    story.append(Paragraph("• <b>DQ Rule Coverage %</b>: (Assets with >= 1 DQ rules run / Total Assets) * 100. Thresholds: [25, 50, 70, 85]%.", bullet_style))
    story.append(Paragraph("• <b>DQ Pass Rate %</b>: (Total rules passed / Total rules run) * 100. Thresholds: [70, 80, 90, 95]%.", bullet_style))
    story.append(Paragraph("• <b>Maturity Scoring Step-mapping</b>: Raw percentages map to 1-5 levels based on the thresholds: Score = 1.0 (if &lt; thresholds[0]), 2.0 (if &lt; thresholds[1]), 3.0 (if &lt; thresholds[2]), 4.0 (if &lt; thresholds[3]), 5.0 (if &gt;= thresholds[3]).", bullet_style))
    story.append(Paragraph("• <b>Metadata Management Maturity</b>: Weighted average of its indicators: Documentation (30%), Ownership (30%), Glossary Linkage (20%), and Classification (20%).", bullet_style))
    story.append(Paragraph("• <b>Data Quality Maturity</b>: Weighted average of its indicators: Rule Coverage (40%) and Pass Rate (60%).", bullet_style))
    story.append(Paragraph("• <b>Overall Maturity Index</b>: Weighted rollup of Metadata Management (50%) and Data Quality (50%).", bullet_style))
    story.append(Paragraph("• <b>Telemetry Confidence Score (TCS)</b>: Blended average of size, query, owner, and lineage coverages: TCS % = (Size Coverage + Query Coverage + Owner Coverage + Lineage Coverage) / 4.", bullet_style))
    story.append(Paragraph("• <b>Size Coverage %</b>: (Assets with storage size &gt; 0 bytes / Total Assets) * 100.", bullet_style))
    story.append(Paragraph("• <b>Query Coverage %</b>: (Assets with query count &gt; 0 / Total Assets) * 100.", bullet_style))
    story.append(Paragraph("• <b>Owner Coverage %</b>: (Assets with technical or business ownership &ge; 1 / Total Assets) * 100.", bullet_style))
    story.append(Paragraph("• <b>Lineage Coverage %</b>: (Assets with mapped upstream or downstream lineage relations / Total Assets) * 100.", bullet_style))
    
    # Build Document PDF
    doc.build(story, onFirstPage=add_page_decorations, onLaterPages=add_page_decorations)
    print(f"Successfully generated PDF report at '{output_file}'")
    
    # Generate CSV Remediation Task Registry
    csv_output_file = os.path.splitext(output_file)[0] + "_remediation_registry.csv"
    generate_remediation_csv(platform, canonical_assets, scored_df, roi_df, csv_output_file)

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Generate Executive Data Governance PDF Report.")
    parser.add_argument("--platform", type=str, default="alation", help="Platform name (e.g. alation)")
    parser.add_argument("--input", type=str, default="alation/sample_alation_metadata.json", help="Input JSON file containing platform mock metadata")
    parser.add_argument("--output", type=str, default=None, help="Output PDF report path. If omitted, saves dynamically in 'reports/' with timestamp.")
    args = parser.parse_args()
    
    # Resolve output path
    reports_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "reports")
    os.makedirs(reports_dir, exist_ok=True)
    
    if args.output is None:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_file = os.path.join(reports_dir, f"{args.platform}_executive_report_{timestamp}.pdf")
    else:
        # If user provided a path, check if it's absolute or relative to reports
        if os.path.isabs(args.output):
            output_file = args.output
        else:
            output_file = os.path.join(reports_dir, args.output)
            
    build_pdf_report(args.platform, args.input, output_file)
