import os
import sys
import json
import argparse
from datetime import datetime

from reportlab.lib.pagesizes import letter
from reportlab.lib import colors
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle

from canonical_metadata_model import map_raw_to_canonical
from governance_scoring_engine import GovernanceScoringEngine
from roi_calculation_engine import ROICalculationEngine
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
    
    # Run Maturity Assessment Engine
    maturity_engine = MaturityAssessmentEngine()
    maturity_results = maturity_engine.assess_maturity(canonical_assets)
    reco_results = maturity_engine.generate_recommendations_and_gaps(maturity_results)
    
    # Aggregated calculations
    total_assets = len(canonical_assets)
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
    
    metadata_maturity = maturity_results["disciplines"]["metadata_management"]["score"]
    dq_maturity = maturity_results["disciplines"]["data_quality"]["score"]
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
        f"<b>{total_assets}</b> data assets managed by {platform.title()}. The implementation achieves a "
        f"<b>Maturity Score of {overall_maturity:.2f}/5.0</b> (Documentation Health: {avg_doc:.1f}%, DQ Pass Rate: {maturity_results['audit_trail']['raw_metrics']['pass_rate']:.1f}%). "
        f"Financially, the program has generated <b>${total_realized_savings:,.2f}</b> in realized business value "
        f"against an estimated annual operating cost of "
        f"<b>${operating_cost:,.2f}</b>, yielding a net realized value of <b>${net_realized_roi:,.2f}</b>. "
        f"Additionally, the engine has identified <b>${total_opportunity_savings:,.2f}</b> in unrealized, actionable opportunity savings "
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
    story.append(Paragraph("1. Discipline-Level Data Governance Maturity Dashboard", heading_style))
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
    story.append(t_consolidated)
    story.append(Spacer(1, 15))
    
    # 4. Program Financial Performance Section
    story.append(Paragraph("2. Program Financial Performance & ROI Analysis", heading_style))
    story.append(Paragraph("The value realized through metadata-driven automation and risk mitigation compared to software licensing and overhead operating costs:", body_style))
    story.append(Spacer(1, 4))
    
    financial_data = [
        [Paragraph("Financial Metric Category", th_style), Paragraph("Amount ($)", th_style), Paragraph("Value Explanation", th_style)],
        [
            Paragraph("Annual Operating Cost", td_style), 
            Paragraph(f"${operating_cost:,.2f}", td_bold_style), 
            Paragraph("Fixed software licensing and support overhead cost.", td_style)
        ],
        [
            Paragraph("Realized Discovery Savings", td_style), 
            Paragraph(f"${roi_df['realized_discovery_savings'].sum():,.2f}", td_bold_style), 
            Paragraph("Productivity savings from faster data discovery.", td_style)
        ],
        [
            Paragraph("Realized DQ Incident Avoidance", td_style), 
            Paragraph(f"${roi_df['realized_dq_savings'].sum():,.2f}", td_bold_style), 
            Paragraph("Savings from avoiding pipeline failures and business downtime.", td_style)
        ],
        [
            Paragraph("Realized Risk Avoidance", td_style), 
            Paragraph(f"${roi_df['realized_risk_savings'].sum():,.2f}", td_bold_style), 
            Paragraph("Mitigated risk of security breaches and regulatory non-compliance.", td_style)
        ],
        [
            Paragraph("Realized Compute Optimization", td_style), 
            Paragraph(f"${roi_df['realized_compute_savings'].sum():,.2f}", td_bold_style), 
            Paragraph("Warehouse credit waste avoided via data quality monitoring.", td_style)
        ],
        [
            Paragraph("<b>Net Realized Program Value</b>", td_bold_style), 
            Paragraph(f"<b>${net_realized_roi:,.2f}</b>", td_bold_style), 
            Paragraph("<b>Net financial return of the program.</b>", td_bold_style)
        ],
        [
            Paragraph("<b>Return on Investment (ROI)</b>", td_bold_style), 
            Paragraph(f"<b>{roi_percentage:.2f}%</b>", td_bold_style), 
            Paragraph("<b>Program efficiency ratio.</b>", td_bold_style)
        ],
        [
            Paragraph("Unrealized Opportunity Value", td_style), 
            Paragraph(f"${total_opportunity_savings:,.2f}", td_bold_style), 
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
        ('BACKGROUND', (0,6), (-1,7), colors.HexColor("#EBF8FF")), # Blue row for Net Value and ROI
    ]))
    story.append(t_financial)
    story.append(Spacer(1, 15))
    
    # 5. Remediation Opportunities Section
    story.append(Paragraph("3. Executive Action Plan & Remediation Pipeline", heading_style))
    story.append(Paragraph("The engine has identified key prioritized actions to reduce costs and secure sensitive corporate data:", body_style))
    story.append(Spacer(1, 6))
    
    remediation_table_data = [
        [
            Paragraph("Category", th_style), 
            Paragraph("Asset Name", th_style), 
            Paragraph("Risk / Telemetry Details", th_style), 
            Paragraph("Recommended Action", th_style), 
            Paragraph("Value Impact", th_style)
        ]
    ]
    
    # 1. ROT Assets (Storage Cost Optimization)
    rot_assets = roi_df[roi_df["is_rot"] == True].sort_values("opportunity_storage_savings", ascending=False).head(3)
    for _, row in rot_assets.iterrows():
        canon_asset = next((x for x in canonical_assets if x.asset_id == row["asset_id"]), None)
        size_gb = (canon_asset.usage.size_in_bytes / (1024**3)) if canon_asset else 0.0
        last_acc_days = ""
        if canon_asset and canon_asset.usage.last_accessed:
            delta = datetime.now() - canon_asset.usage.last_accessed.replace(tzinfo=None)
            last_acc_days = f" ({delta.days}d stale)"
        
        remediation_table_data.append([
            Paragraph("Storage / ROT", td_style),
            Paragraph(f"<b>{row['name']}</b>", td_style),
            Paragraph(f"Size: {size_gb:.1f} GB{last_acc_days}", td_style),
            Paragraph("Decommission or archive storage", td_style),
            Paragraph(f"Saves ${row['opportunity_storage_savings']:,.2f}/yr", td_bold_style)
        ])
        
    # 2. Compliance Exposure (Sensitive unowned PII)
    risky_assets = scored_df[scored_df["security_risk_score"] > 40].sort_values("security_risk_score", ascending=False).head(3)
    for _, row in risky_assets.iterrows():
        canon_asset = next((x for x in canonical_assets if x.asset_id == row["asset_id"]), None)
        queries = canon_asset.usage.query_count if canon_asset else 0
        remediation_table_data.append([
            Paragraph("Compliance / PII", td_style),
            Paragraph(f"<b>{row['name']}</b>", td_style),
            Paragraph(f"Risk: {row['security_risk_score']:.1f}/100<br/>Queries: {queries}/mo", td_style),
            Paragraph("Assign Steward & classification tags", td_style),
            Paragraph(f"Mitigates ${row['security_risk_score']*1500:,.2f} risk", td_bold_style)
        ])
        
    # 3. Business Decision Quality (Low DQ)
    untrusted_assets = scored_df[(scored_df["governance_health_index"] < 60) & (scored_df["data_quality_score"] < 70)].sort_values("governance_health_index").head(3)
    for _, row in untrusted_assets.iterrows():
        canon_asset = next((x for x in canonical_assets if x.asset_id == row["asset_id"]), None)
        queries = canon_asset.usage.query_count if canon_asset else 0
        dq_pct = row["data_quality_score"]
        remediation_table_data.append([
            Paragraph("Trust / Low DQ", td_style),
            Paragraph(f"<b>{row['name']}</b>", td_style),
            Paragraph(f"DQ Pass Rate: {dq_pct:.1f}%<br/>Queries: {queries}/mo", td_style),
            Paragraph("Implement validation rules in pipeline", td_style),
            Paragraph("Avoids debug costs", td_bold_style)
        ])
        
    if len(remediation_table_data) == 1:
        remediation_table_data.append([
            Paragraph("None", td_style),
            Paragraph("No actions required", td_style),
            Paragraph("-", td_style),
            Paragraph("No actions required", td_style),
            Paragraph("-", td_style)
        ])
        
    t_remediation = Table(remediation_table_data, colWidths=[90, 110, 120, 110, 74])
    t_remediation.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), colors.HexColor("#1A365D")),
        ('ALIGN', (0,0), (-1,-1), 'LEFT'),
        ('VALIGN', (0,0), (-1,-1), 'TOP'),
        ('PADDING', (0,0), (-1,-1), 5),
        ('GRID', (0,0), (-1,-1), 0.5, colors.HexColor("#E2E8F0")),
        ('ROWBACKGROUNDS', (0,1), (-1,-1), [colors.white, colors.HexColor("#F7FAFC")]),
    ]))
    story.append(t_remediation)
    story.append(Spacer(1, 15))

    # Strengths and Gaps Section
    story.append(Paragraph("4. Maturity Assessment Strengths & Gaps", heading_style))
    story.append(Paragraph("<b>Key Governance Strengths (Green):</b>", td_bold_style))
    for strength in reco_results["strengths"]:
        story.append(Paragraph(f"• {strength}", bullet_style))
    story.append(Spacer(1, 5))
    
    story.append(Paragraph("<b>Identified Governance Gaps (Amber/Red):</b>", td_bold_style))
    for gap in reco_results["gaps"]:
        story.append(Paragraph(f"• {gap}", bullet_style))
    story.append(Spacer(1, 15))

    # Top 3 Recommendations Section
    story.append(Paragraph("5. Prioritized Action Plan & Recommendations", heading_style))
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
        [Paragraph("Loaded Analyst Rate", td_style), Paragraph(f"${roi_engine.hourly_analyst_rate:.2f}/hr", td_style), Paragraph("U.S. Labor Bureau senior loaded rate averages (1.35x multiplier).", td_style)],
        [Paragraph("Hours Saved per Search", td_style), Paragraph(f"{roi_engine.hours_saved_per_search:.1f} hrs", td_style), Paragraph("Forrester TEI data catalog productivity metrics.", td_style)],
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
    story.append(t_params)
    story.append(Spacer(1, 10))
    
    # Formulas Explanation
    story.append(Paragraph("<b>Equations & Derivations</b>", ParagraphStyle('SubheadingAppendix2', parent=body_style, fontName='Helvetica-Bold', spaceAfter=2)))
    story.append(Paragraph("1. <b>Productivity Savings</b>: (Annual Queries * 10% search ratio) * 3.5 hrs saved * Analyst loaded rate * (Doc Score / 100). Grounded in Forrester's TEI frameworks.", bullet_style))
    story.append(Paragraph("2. <b>ROT Decommissioning</b>: Identified as size > 0, queries < 5/mo, and last accessed > 180 days. Savings = GB Size * $0.24/yr. Grounded in AWS/Azure storage tiers.", bullet_style))
    story.append(Paragraph("3. <b>DQ Incident Avoidance</b>: (Unmonitored baseline [4.0] - Current incidents) * $15k cost. Active DQ profiling drops current errors to 2.0 (for DQ >= 80%) or 0.0 (for DQ >= 95%). Grounded in Gartner data quality impact surveys.", bullet_style))
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
    
    # Build Document PDF
    doc.build(story, onFirstPage=add_page_decorations, onLaterPages=add_page_decorations)
    print(f"Successfully generated PDF report at '{output_file}'")

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
