#!/usr/bin/env python3
"""
Generate sample risk register Excel file for testing.

Run this script to create sample data files in the data/sample directory.
"""

from pathlib import Path

import pandas as pd


def create_sample_risk_register():
    """Create a sample risk register Excel file."""
    data = {
        "Risk ID": [
            "R001", "R002", "R003", "R004", "R005",
            "R006", "R007", "R008", "R009", "R010"
        ],
        "Title": [
            "Key Resource Unavailability",
            "Technical Integration Failure",
            "Permit Approval Delays",
            "Material Cost Escalation",
            "Weather Impact on Construction",
            "Vendor Delivery Delays",
            "Scope Creep",
            "Cybersecurity Threats",
            "Stakeholder Resistance",
            "Budget Overrun"
        ],
        "Description": [
            "Critical project team members may become unavailable due to competing priorities, illness, or turnover during key project phases",
            "Integration between legacy systems and new platform may fail or require significant rework due to undocumented APIs or data inconsistencies",
            "Environmental and building permits may take longer than planned due to regulatory backlog or additional requirements",
            "Raw material and equipment costs may increase significantly due to supply chain disruptions and market volatility",
            "Adverse weather conditions including storms, extreme temperatures, or flooding may delay outdoor construction activities",
            "Key equipment and material vendors may fail to deliver on schedule due to production issues or logistics problems",
            "Uncontrolled changes or continuous growth in project scope may exceed the original project objectives and budget",
            "Project systems and data may be vulnerable to cyber attacks, data breaches, or ransomware during implementation",
            "Key stakeholders may resist changes or fail to provide timely decisions, delaying project progress",
            "Project may exceed approved budget due to unforeseen costs, change orders, or estimation errors"
        ],
        "Category": [
            "Resource", "Technical", "Schedule", "Cost", "External",
            "External", "Management", "Technical", "Organizational", "Cost"
        ],
        "Status": [
            "Open", "Mitigating", "Monitoring", "Open", "Open",
            "Open", "Mitigating", "Monitoring", "Open", "Open"
        ],
        "Probability": [0.6, 0.4, 0.7, 0.5, 0.3, 0.4, 0.6, 0.3, 0.5, 0.4],
        "Impact Score": [4, 5, 3, 4, 3, 4, 4, 5, 3, 5],
        "Cost Impact": [
            75000, 200000, 50000, 150000, 100000,
            80000, 120000, 250000, 40000, 180000
        ],
        "Schedule Impact": [20, 30, 45, 15, 25, 20, 35, 10, 15, 25],
        "Response Type": [
            "Mitigate", "Avoid", "Accept", "Transfer", "Mitigate",
            "Mitigate", "Mitigate", "Mitigate", "Mitigate", "Mitigate"
        ],
        "Mitigation Plan": [
            "Cross-train team members, maintain resource buffer, establish relationships with contractors",
            "Conduct early proof of concept, maintain fallback architecture, involve vendor support",
            "Start permit applications early, maintain relationships with regulators, prepare comprehensive documentation",
            "Lock in prices through long-term contracts, identify alternative suppliers, maintain material buffer",
            "Build weather contingency into schedule, plan indoor work alternatives, monitor forecasts",
            "Qualify multiple vendors, maintain safety stock, include penalty clauses in contracts",
            "Implement formal change control process, regular scope reviews, maintain requirements traceability",
            "Implement security best practices, conduct penetration testing, maintain incident response plan",
            "Develop stakeholder engagement plan, regular communication, executive sponsorship",
            "Implement cost monitoring system, maintain contingency reserve, regular budget reviews"
        ],
        "Owner": [
            "Project Manager", "Technical Lead", "Project Manager", "Procurement Lead",
            "Site Manager", "Procurement Lead", "Project Manager", "IT Security Lead",
            "Project Manager", "Finance Manager"
        ],
        "Due Date": [
            "2024-02-15", "2024-02-28", "2024-03-15", "2024-02-01",
            "2024-01-31", "2024-02-28", "2024-03-01", "2024-02-15",
            "2024-02-28", "2024-03-15"
        ],
        "Related Activities": [
            "A2000, A3010, A3020",
            "A3010, A3020, A3030",
            "A3000",
            "A3000, A3010",
            "A3010, A3020",
            "A3000",
            "A2000, A2020",
            "A3020, A3050",
            "A1010, A2000",
            "A3000, A3010, A3020"
        ],
        "Trigger Conditions": [
            "Staff turnover rate increases, competing projects announced",
            "Initial integration tests fail, vendor documentation gaps identified",
            "Regulatory agency backlogs reported, additional requirements emerge",
            "Commodity prices rise >10%, supplier announces price increases",
            "Weather forecasts predict adverse conditions, seasonal patterns",
            "Vendor reports production issues, logistics disruptions occur",
            "Change request volume increases, stakeholder requests expand",
            "Security alerts increase, vulnerabilities discovered",
            "Stakeholder feedback is delayed, resistance in meetings",
            "Actual costs exceed estimates by >5%, change orders increase"
        ],
        "Notes": [
            "Monitor weekly, escalate if >2 resources become unavailable",
            "POC scheduled for next sprint, vendor engaged",
            "Pre-application meeting scheduled with regulators",
            "Negotiating with 3 suppliers for fixed-price contracts",
            "Contingency plan developed for indoor work shift",
            "Backup vendors identified and pre-qualified",
            "Change control board established, meeting weekly",
            "Security audit scheduled for next month",
            "Stakeholder workshop planned for next week",
            "Monthly budget reviews with finance team"
        ]
    }

    df = pd.DataFrame(data)
    return df


def main():
    """Generate all sample data files."""
    # Ensure output directory exists
    output_dir = Path(__file__).parent.parent / "data" / "sample"
    output_dir.mkdir(parents=True, exist_ok=True)

    # Generate risk register
    risk_df = create_sample_risk_register()
    risk_path = output_dir / "sample_risk_register.xlsx"
    risk_df.to_excel(risk_path, index=False, sheet_name="Risk Register")
    print(f"Created: {risk_path}")

    # Also create a CSV version for easy viewing
    csv_path = output_dir / "sample_risk_register.csv"
    risk_df.to_csv(csv_path, index=False)
    print(f"Created: {csv_path}")

    print("\nSample data generation complete!")
    print(f"\nFiles created in: {output_dir}")
    print("- sample_schedule.xer (P6 schedule)")
    print("- sample_risk_register.xlsx (Risk register)")
    print("- sample_risk_register.csv (Risk register CSV)")


if __name__ == "__main__":
    main()
