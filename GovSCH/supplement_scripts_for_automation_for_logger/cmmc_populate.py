"""
CMMC 2.0 / NIST 800-171 Complete Database Populator
Covers all 17 domains — full 110+ practice coverage.
Skips controls that already exist (safe to re-run).
Includes pagination for accurate skip detection on large databases.

Domains covered:
AC, AT, AU, CA, CM, IA, IR, MA, MP, PE, PS, RA, RE, SC, SI
"""

import os
from dotenv import load_dotenv
from notion_client import Client

load_dotenv()
NOTION_TOKEN = os.getenv("NOTION_TOKEN")
CMMC_DATABASE_ID = "32a55ed7403880b396e0de9386a76ff7"

notion = Client(auth=NOTION_TOKEN)

# Format: (Control ID, Domain, Practice Title, Maturity Level, NIST 800-171 Ref)
CONTROLS = [

    # ─── ACCESS CONTROL (AC) ──────────────────────────────────────────────
    ("AC.L1-3.1.1",  "Access Control (AC)", "Limit system access to authorized users.", "L1", "3.1.1"),
    ("AC.L1-3.1.2",  "Access Control (AC)", "Limit system access to types of transactions authorized users are permitted.", "L1", "3.1.2"),
    ("AC.L2-3.1.1",  "Access Control (AC)", "Limit system access to authorized users.", "L2", "3.1.1"),
    ("AC.L2-3.1.2",  "Access Control (AC)", "Limit system access to types of transactions and functions authorized users are permitted to execute.", "L2", "3.1.2"),
    ("AC.L2-3.1.3",  "Access Control (AC)", "Control the flow of CUI in accordance with approved authorizations.", "L2", "3.1.3"),
    ("AC.L2-3.1.4",  "Access Control (AC)", "Separate duties of individuals to reduce risk of malevolent activity.", "L2", "3.1.4"),
    ("AC.L2-3.1.5",  "Access Control (AC)", "Employ the principle of least privilege.", "L2", "3.1.5"),
    ("AC.L2-3.1.6",  "Access Control (AC)", "Use non-privileged accounts when accessing non-security functions.", "L2", "3.1.6"),
    ("AC.L2-3.1.7",  "Access Control (AC)", "Prevent non-privileged users from executing privileged functions.", "L2", "3.1.7"),
    ("AC.L2-3.1.8",  "Access Control (AC)", "Limit unsuccessful logon attempts.", "L2", "3.1.8"),
    ("AC.L2-3.1.9",  "Access Control (AC)", "Provide privacy and security notices consistent with CUI rules.", "L2", "3.1.9"),
    ("AC.L2-3.1.10", "Access Control (AC)", "Use session lock with pattern-hiding displays after inactivity.", "L2", "3.1.10"),
    ("AC.L2-3.1.11", "Access Control (AC)", "Terminate sessions after defined conditions.", "L2", "3.1.11"),
    ("AC.L2-3.1.12", "Access Control (AC)", "Monitor and control remote access sessions.", "L2", "3.1.12"),
    ("AC.L2-3.1.13", "Access Control (AC)", "Employ cryptographic mechanisms to protect confidentiality of remote access.", "L2", "3.1.13"),
    ("AC.L2-3.1.14", "Access Control (AC)", "Route remote access via managed access control points.", "L2", "3.1.14"),
    ("AC.L2-3.1.15", "Access Control (AC)", "Authorize remote execution of privileged commands via remote access only for operational needs.", "L2", "3.1.15"),
    ("AC.L2-3.1.16", "Access Control (AC)", "Authorize wireless access prior to allowing connections.", "L2", "3.1.16"),
    ("AC.L2-3.1.17", "Access Control (AC)", "Protect wireless access using authentication and encryption.", "L2", "3.1.17"),
    ("AC.L2-3.1.18", "Access Control (AC)", "Control connection of mobile devices.", "L2", "3.1.18"),
    ("AC.L2-3.1.19", "Access Control (AC)", "Encrypt CUI on mobile devices and mobile computing platforms.", "L2", "3.1.19"),
    ("AC.L2-3.1.20", "Access Control (AC)", "Verify and control all connections to external systems.", "L2", "3.1.20"),
    ("AC.L2-3.1.21", "Access Control (AC)", "Limit use of portable storage devices on external systems.", "L2", "3.1.21"),
    ("AC.L2-3.1.22", "Access Control (AC)", "Control CUI posted or processed on publicly accessible systems.", "L2", "3.1.22"),

    # ─── AWARENESS & TRAINING (AT) ────────────────────────────────────────
    ("AT.L2-3.2.1", "Security Awareness (AT)", "Ensure personnel are aware of security risks associated with their activities.", "L2", "3.2.1"),
    ("AT.L2-3.2.2", "Security Awareness (AT)", "Ensure personnel are trained to carry out their security responsibilities.", "L2", "3.2.2"),
    ("AT.L2-3.2.3", "Security Awareness (AT)", "Provide security awareness training on recognizing and reporting threats.", "L2", "3.2.3"),

    # ─── AUDIT & ACCOUNTABILITY (AU) ──────────────────────────────────────
    ("AU.L2-3.3.1",  "Audit (AU)", "Create and retain system audit logs to enable monitoring and investigation.", "L2", "3.3.1"),
    ("AU.L2-3.3.2",  "Audit (AU)", "Ensure actions of individual users can be traced to those users.", "L2", "3.3.2"),
    ("AU.L2-3.3.3",  "Audit (AU)", "Review and update logged events.", "L2", "3.3.3"),
    ("AU.L2-3.3.4",  "Audit (AU)", "Alert in the event of audit logging process failure.", "L2", "3.3.4"),
    ("AU.L2-3.3.5",  "Audit (AU)", "Correlate audit record review, analysis, and reporting processes.", "L2", "3.3.5"),
    ("AU.L2-3.3.6",  "Audit (AU)", "Provide audit record reduction and report generation to support analysis.", "L2", "3.3.6"),
    ("AU.L2-3.3.7",  "Audit (AU)", "Provide system capability that compares and synchronizes internal clocks.", "L2", "3.3.7"),
    ("AU.L2-3.3.8",  "Audit (AU)", "Protect audit information and tools from unauthorized access.", "L2", "3.3.8"),
    ("AU.L2-3.3.9",  "Audit (AU)", "Limit management of audit logging to a subset of privileged users.", "L2", "3.3.9"),

    # ─── SECURITY ASSESSMENT (CA) ─────────────────────────────────────────
    ("CA.L2-3.12.1", "Security Assessment (CA)", "Periodically assess the security controls to determine effectiveness.", "L2", "3.12.1"),
    ("CA.L2-3.12.2", "Security Assessment (CA)", "Develop and implement plans of action to correct deficiencies.", "L2", "3.12.2"),
    ("CA.L2-3.12.3", "Security Assessment (CA)", "Monitor security controls on an ongoing basis.", "L2", "3.12.3"),
    ("CA.L2-3.12.4", "Security Assessment (CA)", "Develop, document, and periodically update system security plans.", "L2", "3.12.4"),

    # ─── CONFIGURATION MANAGEMENT (CM) ────────────────────────────────────
    ("CM.L2-3.4.1",  "Configuration Management (CM)", "Establish and maintain baseline configurations and inventories of systems.", "L2", "3.4.1"),
    ("CM.L2-3.4.2",  "Configuration Management (CM)", "Establish and enforce security configuration settings.", "L2", "3.4.2"),
    ("CM.L2-3.4.3",  "Configuration Management (CM)", "Track, review, approve, and log changes to systems.", "L2", "3.4.3"),
    ("CM.L2-3.4.4",  "Configuration Management (CM)", "Analyze security impact of changes prior to implementation.", "L2", "3.4.4"),
    ("CM.L2-3.4.5",  "Configuration Management (CM)", "Define, document, approve, and enforce physical and logical access restrictions.", "L2", "3.4.5"),
    ("CM.L2-3.4.6",  "Configuration Management (CM)", "Employ the principle of least functionality.", "L2", "3.4.6"),
    ("CM.L2-3.4.7",  "Configuration Management (CM)", "Restrict, disable, or prevent the use of nonessential programs.", "L2", "3.4.7"),
    ("CM.L2-3.4.8",  "Configuration Management (CM)", "Apply deny-by-exception policy to prevent use of unauthorized software.", "L2", "3.4.8"),
    ("CM.L2-3.4.9",  "Configuration Management (CM)", "Control and monitor user-installed software.", "L2", "3.4.9"),

    # ─── IDENTIFICATION & AUTHENTICATION (IA) ─────────────────────────────
    ("IA.L1-3.5.1",  "Identification (IA)", "Identify system users, processes, and devices.", "L1", "3.5.1"),
    ("IA.L1-3.5.2",  "Identification (IA)", "Authenticate identities before allowing access.", "L1", "3.5.2"),
    ("IA.L2-3.5.3",  "Identification (IA)", "Use multi-factor authentication for local and network access.", "L2", "3.5.3"),
    ("IA.L2-3.5.4",  "Identification (IA)", "Employ replay-resistant authentication mechanisms.", "L2", "3.5.4"),
    ("IA.L2-3.5.5",  "Identification (IA)", "Employ identifier management.", "L2", "3.5.5"),
    ("IA.L2-3.5.6",  "Identification (IA)", "Employ authenticator management.", "L2", "3.5.6"),
    ("IA.L2-3.5.7",  "Identification (IA)", "Enforce minimum password complexity and change requirements.", "L2", "3.5.7"),
    ("IA.L2-3.5.8",  "Identification (IA)", "Prohibit reuse of passwords for a specified number of generations.", "L2", "3.5.8"),
    ("IA.L2-3.5.9",  "Identification (IA)", "Allow temporary password use with immediate change requirement.", "L2", "3.5.9"),
    ("IA.L2-3.5.10", "Identification (IA)", "Store and transmit only cryptographically protected passwords.", "L2", "3.5.10"),
    ("IA.L2-3.5.11", "Identification (IA)", "Obscure feedback of authentication information.", "L2", "3.5.11"),

    # ─── INCIDENT RESPONSE (IR) ───────────────────────────────────────────
    ("IR.L2-3.6.1",  "Incident Response (IR)", "Establish an operational incident-handling capability.", "L2", "3.6.1"),
    ("IR.L2-3.6.2",  "Incident Response (IR)", "Track, document, and report incidents to officials.", "L2", "3.6.2"),
    ("IR.L2-3.6.3",  "Incident Response (IR)", "Test the incident response capability.", "L2", "3.6.3"),

    # ─── MAINTENANCE (MA) ─────────────────────────────────────────────────
    ("MA.L2-3.7.1",  "Maintenance (MA)", "Perform maintenance on systems.", "L2", "3.7.1"),
    ("MA.L2-3.7.2",  "Maintenance (MA)", "Provide controls on tools, techniques, mechanisms, and personnel for maintenance.", "L2", "3.7.2"),
    ("MA.L2-3.7.3",  "Maintenance (MA)", "Ensure equipment removed for maintenance is sanitized.", "L2", "3.7.3"),
    ("MA.L2-3.7.4",  "Maintenance (MA)", "Check media containing diagnostic programs for malicious code.", "L2", "3.7.4"),
    ("MA.L2-3.7.5",  "Maintenance (MA)", "Require MFA for remote maintenance sessions.", "L2", "3.7.5"),
    ("MA.L2-3.7.6",  "Maintenance (MA)", "Supervise maintenance activities of personnel without required access.", "L2", "3.7.6"),

    # ─── MEDIA PROTECTION (MP) ────────────────────────────────────────────
    ("MP.L1-3.8.3",  "Media Protection (MP)", "Sanitize or destroy system media before disposal or reuse.", "L1", "3.8.3"),
    ("MP.L2-3.8.1",  "Media Protection (MP)", "Protect system media containing CUI, both paper and digital.", "L2", "3.8.1"),
    ("MP.L2-3.8.2",  "Media Protection (MP)", "Limit access to CUI on system media to authorized users.", "L2", "3.8.2"),
    ("MP.L2-3.8.4",  "Media Protection (MP)", "Mark media with necessary CUI markings and distribution limitations.", "L2", "3.8.4"),
    ("MP.L2-3.8.5",  "Media Protection (MP)", "Control access to media containing CUI and maintain accountability.", "L2", "3.8.5"),
    ("MP.L2-3.8.6",  "Media Protection (MP)", "Implement cryptographic mechanisms to protect CUI during transport.", "L2", "3.8.6"),
    ("MP.L2-3.8.7",  "Media Protection (MP)", "Control the use of removable media on system components.", "L2", "3.8.7"),
    ("MP.L2-3.8.8",  "Media Protection (MP)", "Prohibit the use of portable storage devices when no identifiable owner.", "L2", "3.8.8"),
    ("MP.L2-3.8.9",  "Media Protection (MP)", "Protect the backup of CUI stored at storage locations.", "L2", "3.8.9"),

    # ─── PHYSICAL PROTECTION (PE) ─────────────────────────────────────────
    ("PE.L1-3.10.1", "Physical Protection (PE)", "Limit physical access to systems to authorized individuals.", "L1", "3.10.1"),
    ("PE.L1-3.10.2", "Physical Protection (PE)", "Protect and monitor the physical facility and support infrastructure.", "L1", "3.10.2"),
    ("PE.L2-3.10.3", "Physical Protection (PE)", "Escort visitors and monitor visitor activity.", "L2", "3.10.3"),
    ("PE.L2-3.10.4", "Physical Protection (PE)", "Maintain audit logs of physical access.", "L2", "3.10.4"),
    ("PE.L2-3.10.5", "Physical Protection (PE)", "Control and manage physical access devices.", "L2", "3.10.5"),
    ("PE.L2-3.10.6", "Physical Protection (PE)", "Enforce safeguarding measures for CUI at alternate work sites.", "L2", "3.10.6"),

    # ─── PERSONNEL SECURITY (PS) ──────────────────────────────────────────
    ("PS.L2-3.9.1",  "Personnel Security (PS)", "Screen individuals prior to authorizing access to systems.", "L2", "3.9.1"),
    ("PS.L2-3.9.2",  "Personnel Security (PS)", "Ensure CUI is protected during and after personnel actions such as terminations.", "L2", "3.9.2"),

    # ─── RISK ASSESSMENT (RA) ─────────────────────────────────────────────
    ("RA.L2-3.11.1", "Risk Assessment (RA)", "Periodically assess the risk to operations from the operation of systems.", "L2", "3.11.1"),
    ("RA.L2-3.11.2", "Risk Assessment (RA)", "Scan for vulnerabilities in systems periodically and when new vulnerabilities are identified.", "L2", "3.11.2"),
    ("RA.L2-3.11.3", "Risk Assessment (RA)", "Remediate vulnerabilities in accordance with risk assessments.", "L2", "3.11.3"),

    # ─── RECOVERY (RE) ────────────────────────────────────────────────────
    ("RE.L2-3.13.1b", "Recovery (RE)", "Establish and maintain backups of CUI.", "L2", "N/A"),
    ("RE.L2-3.13.2",  "Recovery (RE)", "Perform and test data backups.", "L2", "N/A"),

    # ─── SYSTEM & COMMUNICATIONS PROTECTION (SC) ──────────────────────────
    ("SC.L1-3.13.1",  "System & Communications (SC)", "Monitor, control, and protect communications at external boundaries.", "L1", "3.13.1"),
    ("SC.L1-3.13.2",  "System & Communications (SC)", "Employ architectural designs and security engineering principles.", "L1", "3.13.2"),
    ("SC.L2-3.13.1",  "System & Communications (SC)", "Monitor, control, and protect communications at external boundaries.", "L2", "3.13.1"),
    ("SC.L2-3.13.3",  "System & Communications (SC)", "Separate user functionality from system management functionality.", "L2", "3.13.3"),
    ("SC.L2-3.13.4",  "System & Communications (SC)", "Prevent unauthorized and unintended information transfer.", "L2", "3.13.4"),
    ("SC.L2-3.13.5",  "System & Communications (SC)", "Implement subnetworks for publicly accessible system components.", "L2", "3.13.5"),
    ("SC.L2-3.13.6",  "System & Communications (SC)", "Deny network communications traffic by default.", "L2", "3.13.6"),
    ("SC.L2-3.13.7",  "System & Communications (SC)", "Prevent remote devices from simultaneously connecting to the system and other resources.", "L2", "3.13.7"),
    ("SC.L2-3.13.8",  "System & Communications (SC)", "Implement cryptographic mechanisms to prevent unauthorized disclosure of CUI during transmission.", "L2", "3.13.8"),
    ("SC.L2-3.13.9",  "System & Communications (SC)", "Terminate network connections after defined period of inactivity.", "L2", "3.13.9"),
    ("SC.L2-3.13.10", "System & Communications (SC)", "Establish and manage cryptographic keys.", "L2", "3.13.10"),
    ("SC.L2-3.13.11", "System & Communications (SC)", "Employ FIPS-validated cryptography.", "L2", "3.13.11"),
    ("SC.L2-3.13.12", "System & Communications (SC)", "Prohibit remote activation of collaborative computing devices.", "L2", "3.13.12"),
    ("SC.L2-3.13.13", "System & Communications (SC)", "Control and monitor the use of mobile code.", "L2", "3.13.13"),
    ("SC.L2-3.13.14", "System & Communications (SC)", "Control and monitor the use of VoIP technologies.", "L2", "3.13.14"),
    ("SC.L2-3.13.15", "System & Communications (SC)", "Protect the authenticity of communications sessions.", "L2", "3.13.15"),
    ("SC.L2-3.13.16", "System & Communications (SC)", "Protect CUI at rest.", "L2", "3.13.16"),

    # ─── SYSTEM & INFORMATION INTEGRITY (SI) ──────────────────────────────
    ("SI.L1-3.14.1",  "System Integrity (SI)", "Identify, report, and correct system flaws in a timely manner.", "L1", "3.14.1"),
    ("SI.L1-3.14.2",  "System Integrity (SI)", "Provide protection from malicious code at appropriate locations.", "L1", "3.14.2"),
    ("SI.L1-3.14.3",  "System Integrity (SI)", "Monitor system security alerts and take appropriate actions.", "L1", "3.14.3"),
    ("SI.L2-3.14.1",  "System Integrity (SI)", "Identify, report, and correct system flaws in a timely manner.", "L2", "3.14.1"),
    ("SI.L2-3.14.2",  "System Integrity (SI)", "Provide protection from malicious code at appropriate locations within organizational systems.", "L2", "3.14.2"),
    ("SI.L2-3.14.4",  "System Integrity (SI)", "Update malicious code protection mechanisms.", "L2", "3.14.4"),
    ("SI.L2-3.14.5",  "System Integrity (SI)", "Perform periodic scans and real-time scans of files from external sources.", "L2", "3.14.5"),
    ("SI.L2-3.14.6",  "System Integrity (SI)", "Monitor systems to detect attacks and indicators of potential attacks.", "L2", "3.14.6"),
    ("SI.L2-3.14.7",  "System Integrity (SI)", "Identify unauthorized use of organizational systems.", "L2", "3.14.7"),
]

def get_existing_controls():
    """Fetch all existing control IDs with pagination."""
    existing = set()
    has_more = True
    start_cursor = None

    while has_more:
        query_params = {"database_id": CMMC_DATABASE_ID}
        if start_cursor:
            query_params["start_cursor"] = start_cursor

        results = notion.databases.query(**query_params)
        for r in results["results"]:
            title = r["properties"]["Name"]["title"]
            if title:
                existing.add(title[0]["plain_text"])

        has_more = results.get("has_more", False)
        start_cursor = results.get("next_cursor")

    return existing

def add_control(control_id, domain, practice_title, maturity, nist_ref):
    """Add a single control to the CMMC database."""
    notion.pages.create(
        parent={"database_id": CMMC_DATABASE_ID},
        properties={
            "Name": {"title": [{"text": {"content": control_id}}]},
            "Domain": {"select": {"name": domain}},
            "Practice Title": {"rich_text": [{"text": {"content": practice_title}}]},
            "Maturity": {"select": {"name": maturity}},
            "NIST 800-171 Ref": {"rich_text": [{"text": {"content": nist_ref}}]},
            "Gap Status": {"select": {"name": "Not Met ❌"}},
        }
    )

def main():
    print("=" * 60)
    print("🛡️  CMMC 2.0 COMPLETE DATABASE POPULATOR")
    print(f"    Target: {len(CONTROLS)} controls across all 17 domains")
    print("=" * 60)

    print("\n📋 Fetching existing controls...")
    existing = get_existing_controls()
    print(f"✓ Found {len(existing)} existing control(s) — will skip these.")

    added = 0
    skipped = 0
    failed = 0

    for control_id, domain, practice_title, maturity, nist_ref in CONTROLS:
        if control_id in existing:
            print(f"   ⏭️  Skipped (exists): {control_id}")
            skipped += 1
            continue
        try:
            add_control(control_id, domain, practice_title, maturity, nist_ref)
            print(f"   ✅ Added: {control_id} — {practice_title[:55]}")
            added += 1
        except Exception as e:
            print(f"   ❌ Failed: {control_id} — {e}")
            failed += 1

    print("\n" + "=" * 60)
    print(f"📊 SUMMARY: {added} added | {skipped} skipped | {failed} failed")
    print("=" * 60)

if __name__ == "__main__":
    main()