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
        f"<b>Executive Summary:</b> An automated maturity assessment was conducted on "
        f"<b>{total_assets}</b> data assets managed by {platform.title()}. The implementation achieves a "
        f"<b>Governance Health Index (GHI) of {avg_ghi:.2f}%</b>, reflecting moderate governance execution. "
        f"Financially, the program has generated <b>${total_realized_savings:,.2f}</b> in realized business value "
        f"(productivity savings, incident avoidance, and compliance risk mitigation) against an estimated annual cost of "
        f"<b>${operating_cost:,.2f}</b>. This yields an outstanding net realized value of <b>${net_realized_roi:,.2f}</b>. "
        f"Additionally, the engine has identified <b>${total_opportunity_savings:,.2f}</b> in unrealized, actionable opportunity savings "
        f"that can be unlocked through targeted remediation efforts (such as decommissioning ROT storage and securing un-owned PII)."
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
    story.append(Paragraph("1. Governance Implementation Maturity Breakdown", heading_style))
    story.append(Paragraph("Maturity is assessed across four key pillars mapped from raw vendor metadata:", body_style))
    story.append(Spacer(1, 4))
    
    # Maturity Table
    def get_status(score, is_risk=False):
        if is_risk:
            if score > 50: return "Critical Risk"
            if score > 20: return "Moderate Risk"
            return "Low Risk"
        else:
            if score >= 80: return "Optimized"
            if score >= 50: return "Adequate"
            return "Action Needed"
            
    # Maturity Table
    def get_status(score, is_risk=False):
        if is_risk:
            if score > 50: return "Critical Risk"
            if score > 20: return "Moderate Risk"
            return "Low Risk"
        else:
            if score >= 80: return "Optimized"
            if score >= 50: return "Adequate"
            return "Action Needed"
            
    maturity_data = [
        [Paragraph("Pillar Parameter", th_style), Paragraph("Weight", th_style), Paragraph("Score", th_style), Paragraph("Calculation Formula & Variables Mapped", th_style), Paragraph("Status", th_style)],
        [
            Paragraph("Documentation Completeness", td_style), 
            Paragraph("30%", td_style), 
            Paragraph(f"{avg_doc:.2f}%", td_bold_style), 
            Paragraph("Avg of: 40 (description) + 10 (length > 50) + 30 (owner) + 20 (terms)", td_style), 
            Paragraph(get_status(avg_doc), td_bold_style)
        ],
        [
            Paragraph("Data Quality Coverage", td_style), 
            Paragraph("40%", td_style), 
            Paragraph(f"{avg_dq:.2f}%", td_bold_style), 
            Paragraph("Avg of: pass_rate * 100 (0.0% if unmonitored/no DQ rules)", td_style), 
            Paragraph(get_status(avg_dq), td_bold_style)
        ],
        [
            Paragraph("Lineage Transparency", td_style), 
            Paragraph("20%", td_style), 
            Paragraph(f"{avg_lineage:.2f}%", td_bold_style), 
            Paragraph("Avg of: 50 (upstream lineage) + 50 (downstream lineage)", td_style), 
            Paragraph(get_status(avg_lineage), td_bold_style)
        ],
        [
            Paragraph("Security & Policy Risk", td_style), 
            Paragraph("10%", td_style), 
            Paragraph(f"{avg_risk:.2f}%", td_bold_style), 
            Paragraph("Avg of: 20 (sensitive) + 40 (unowned) + 20 (untagged) + 20 (0 DQ)", td_style), 
            Paragraph(get_status(avg_risk, True), td_bold_style)
        ],
        [
            Paragraph("<b>Governance Health Index</b>", td_bold_style), 
            Paragraph("<b>100%</b>", td_bold_style), 
            Paragraph(f"<b>{avg_ghi:.2f}%</b>", td_bold_style), 
            Paragraph("<b>GHI = (Doc*0.3) + (DQ*0.4) + (Lineage*0.2) + ((100-Risk)*0.1)</b>", td_bold_style), 
            Paragraph("<b>Active</b>", td_bold_style)
        ]
    ]
    
    t_maturity = Table(maturity_data, colWidths=[120, 45, 55, 200, 84])
    t_maturity.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), colors.HexColor("#1A365D")), # Dark navy header
        ('ALIGN', (0,0), (-1,-1), 'LEFT'),
        ('PADDING', (0,0), (-1,-1), 5),
        ('GRID', (0,0), (-1,-1), 0.5, colors.HexColor("#E2E8F0")),
        ('ROWBACKGROUNDS', (0,1), (-1,-2), [colors.white, colors.HexColor("#F7FAFC")]),
        ('BACKGROUND', (0,-1), (-1,-1), colors.HexColor("#EDF2F7")), # Gray row for composite GHI
    ]))
    story.append(t_maturity)
    story.append(Spacer(1, 15))
    
    # 4. Program Financial Performance Section
    story.append(Paragraph("2. Program Financial Performance & ROI Analysis", heading_style))
    story.append(Paragraph("The value realized through metadata-driven automation and risk mitigation compared to software licensing and overhead operating costs:", body_style))
    story.append(Spacer(1, 4))
    
    financial_data = [
        [Paragraph("Financial Metric Category", th_style), Paragraph("Amount ($)", th_style), Paragraph("Calculation Formula & Constant Assumptions", th_style), Paragraph("Value Explanation", th_style)],
        [
            Paragraph("Annual Operating Cost", td_style), 
            Paragraph(f"${operating_cost:,.2f}", td_bold_style), 
            Paragraph("Constant platform licensing & support headcount budget", td_style),
            Paragraph("Fixed software cost", td_style)
        ],
        [
            Paragraph("Realized Discovery Savings", td_style), 
            Paragraph(f"${total_realized_savings:,.2f}", td_bold_style), 
            Paragraph("Sum of: (Annual Queries * 10% * 3.5 hrs saved * $75/hr) * Doc Score%", td_style),
            Paragraph("Productivity savings", td_style)
        ],
        [
            Paragraph("Realized DQ Incident Avoidance", td_style), 
            Paragraph(f"${roi_df['realized_dq_savings'].sum():,.2f}", td_bold_style), 
            Paragraph("Sum of: (4.0 baseline incidents - current incidents) * $15k per incident", td_style),
            Paragraph("DQ debug savings", td_style)
        ],
        [
            Paragraph("Realized Risk Avoidance", td_style), 
            Paragraph(f"${roi_df['realized_risk_savings'].sum():,.2f}", td_bold_style), 
            Paragraph("Sum of: (5% baseline breach probability - current probability) * $150k cost", td_style),
            Paragraph("Risk mitigation", td_style)
        ],
        [
            Paragraph("<b>Net Realized Program Value</b>", td_bold_style), 
            Paragraph(f"<b>${net_realized_roi:,.2f}</b>", td_bold_style), 
            Paragraph("<b>Net Value = Total Realized Savings - Annual Operating Cost</b>", td_bold_style),
            Paragraph("<b>Net dollar return</b>", td_bold_style)
        ],
        [
            Paragraph("<b>Return on Investment (ROI)</b>", td_bold_style), 
            Paragraph(f"<b>{roi_percentage:.2f}%</b>", td_bold_style), 
            Paragraph("<b>ROI % = (Net Realized Program Value / Annual Operating Cost) * 100</b>", td_bold_style),
            Paragraph("<b>Efficiency score</b>", td_bold_style)
        ],
        [
            Paragraph("Unrealized Opportunity Value", td_style), 
            Paragraph(f"${total_opportunity_savings:,.2f}", td_bold_style), 
            Paragraph("Sum of: remaining discovery opportunity + DQ opportunity + Risk + ROT storage", td_style),
            Paragraph("Unrealized pipeline", td_style)
        ]
    ]
    
    t_financial = Table(financial_data, colWidths=[120, 80, 214, 90])
    t_financial.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), colors.HexColor("#1A365D")),
        ('ALIGN', (0,0), (-1,-1), 'LEFT'),
        ('PADDING', (0,0), (-1,-1), 5),
        ('GRID', (0,0), (-1,-1), 0.5, colors.HexColor("#E2E8F0")),
        ('ROWBACKGROUNDS', (0,1), (-1,-2), [colors.white, colors.HexColor("#F7FAFC")]),
        ('BACKGROUND', (0,5), (-1,6), colors.HexColor("#EBF8FF")), # Blue row for Net Value and ROI
    ]))
    story.append(t_financial)
    story.append(Spacer(1, 15))
    
    # 5. Remediation Opportunities Section
    story.append(Paragraph("3. Executive Action Plan & Remediation Pipeline", heading_style))
    story.append(Paragraph("The engine has identified key prioritized actions to reduce costs and secure sensitive corporate data:", body_style))
    story.append(Spacer(1, 6))
    
    # Sub-sections
    story.append(Paragraph("<b>Category A: Storage Cost Optimization (Obsolete/ROT Data Decommissioning)</b>", ParagraphStyle('Subheading', parent=body_style, fontName='Helvetica-Bold', spaceAfter=2)))
    story.append(Paragraph("Decommissioning the following zero-usage datasets yields direct cloud storage savings:", body_style))
    
    rot_assets = roi_df[roi_df["is_rot"] == True].sort_values("opportunity_storage_savings", ascending=False).head(3)
    if not rot_assets.empty:
        for idx, (_, row) in enumerate(rot_assets.iterrows(), 1):
            canon_asset = next((x for x in canonical_assets if x.asset_id == row["asset_id"]), None)
            size_gb = (canon_asset.usage.size_in_bytes / (1024**3)) if canon_asset else 0.0
            last_acc_days = ""
            if canon_asset and canon_asset.usage.last_accessed:
                delta = datetime.now() - canon_asset.usage.last_accessed.replace(tzinfo=None)
                last_acc_days = f" (stale for {delta.days} days)"
            
            story.append(Paragraph(f"• <b>{row['name']}</b> : Size: <b>{size_gb:.1f} GB</b>{last_acc_days}. Action: Decommission or archive. Potential annual savings: <b>${row['opportunity_storage_savings']:,.2f}</b>", bullet_style))
    else:
        story.append(Paragraph("• No outstanding ROT storage issues detected.", bullet_style))
        
    story.append(Spacer(1, 8))
    
    story.append(Paragraph("<b>Category B: Compliance & Exposure Mitigation (Sensitive Unowned PII/Confidential Assets)</b>", ParagraphStyle('Subheading2', parent=body_style, fontName='Helvetica-Bold', spaceAfter=2)))
    story.append(Paragraph("High-exposure datasets containing sensitive tags or keywords that are missing technical owners:", body_style))
    
    risky_assets = scored_df[scored_df["security_risk_score"] > 40].sort_values("security_risk_score", ascending=False).head(3)
    if not risky_assets.empty:
        for idx, (_, row) in enumerate(risky_assets.iterrows(), 1):
            canon_asset = next((x for x in canonical_assets if x.asset_id == row["asset_id"]), None)
            queries = canon_asset.usage.query_count if canon_asset else 0
            story.append(Paragraph(f"• <b>{row['name']}</b> (Risk: <b>{row['security_risk_score']:.1f}/100</b>) : Read queries: <b>{queries}/month</b>. Action: Assign Steward and apply classification tags to avoid compliance penalty risk.", bullet_style))
    else:
        story.append(Paragraph("• No high-risk compliance exposures detected.", bullet_style))
        
    story.append(Spacer(1, 8))
    
    story.append(Paragraph("<b>Category C: Business Decision Quality (High-Usage Reporting with Poor Monitoring)</b>", ParagraphStyle('Subheading3', parent=body_style, fontName='Helvetica-Bold', spaceAfter=2)))
    story.append(Paragraph("Critical dashboards and datasets used extensively by the business that have failing/unmonitored data quality rules:", body_style))
    
    untrusted_assets = scored_df[(scored_df["governance_health_index"] < 60) & (scored_df["data_quality_score"] < 70)].sort_values("governance_health_index").head(3)
    if not untrusted_assets.empty:
        for idx, (_, row) in enumerate(untrusted_assets.iterrows(), 1):
            canon_asset = next((x for x in canonical_assets if x.asset_id == row["asset_id"]), None)
            queries = canon_asset.usage.query_count if canon_asset else 0
            dq_pct = row["data_quality_score"]
            story.append(Paragraph(f"• <b>{row['name']}</b> : Monthly queries: <b>{queries}</b> | DQ Pass Rate: <b>{dq_pct:.1f}%</b>. Action: Build data quality verification checks in data pipeline.", bullet_style))
    else:
        story.append(Paragraph("• No untrusted high-usage datasets detected.", bullet_style))
        
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
