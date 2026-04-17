#!/usr/bin/env python3
"""Generate sample February 2026 ticket data for KHD Gov Ticket Report Builder."""

import csv
import random
from datetime import datetime, timedelta

random.seed(2026_02)

NUM_TICKETS = 500

# ── Companies (weighted) ──────────────────────────────────────────────
# Different top companies from March, but same Parent Account CyberTek MSSP
COMPANIES_WEIGHTED = [
    ("CyberTek MSSP", 60),
    ("Lifespan", 30),
    ("Crestline:Kimpton Alton Hotel", 22),
    ("Garden of The Gods Resort & Club", 20),
    ("PG:The Merrill Hotel, Muscatine, a Tribute Portfolio Hotel", 18),
    ("Nobu", 16),
    ("Crestline:Phoenix Park Hotel", 14),
    ("Kidney Care Consultants", 14),
    ("Crestline:San Francisco Marriott Fisherman's Wharf", 12),
    ("Aperture Hotels:Hilton Garden Inn Columbus", 12),
    ("Crestline:Hotel Spero", 10),
    ("Venza Group", 10),
    ("Mainsail Central LLC", 10),
    ("Crestline:CY/RI Washington Downtown/Convention Center", 9),
    ("Crestline:The Chemists Club Hotel", 8),
    ("Peachtree Group - Primary", 8),
    ("Premier Flooring", 8),
    ("Crestline:El Prado Hotel", 7),
    ("Crestline:Ohio University Inn & Conference Center", 7),
    ("Aperture Hotels:Hotel Indigo Atlanta Vinings", 7),
    ("Crestline:Hotel 24 South", 6),
    ("Crestline:Aloft Portland", 6),
    ("Norstam Veneers, Inc", 6),
    ("Crestline:Waldorf Towers Hotel", 5),
    ("Crestline:The Golden Hotel Ascend Collection", 5),
    ("Mainsail:Luminary", 5),
    ("Crestline", 5),
    ("Aperture Hotels", 5),
    ("Young Lind Endres & Kraft", 4),
    ("Crestline:The Delphi", 4),
    ("PG:Home2 Suites by Hilton St Augustine", 4),
    ("The Bernstein Companies", 4),
    ("Align Southern Indiana", 4),
    ("Allegiance Heating & Air", 3),
    ("Bliss Travel", 3),
    ("CCE Inc.", 3),
    ("Charlestowne Hotels:Courtyard Starkville", 3),
    ("City of Salem", 3),
    ("Countryside Insurance", 3),
    ("1400 Willow Council", 3),
    ("Betteau Law Office", 3),
    ("Advantage Construction Equipment", 3),
    ("Crestline:AC Hotel Portland Downtown/Waterfront", 3),
    ("Crestline:Courtyard Fort Lauderdale East/Lauderdale-by-the-Sea", 3),
    ("Crestline:Comfort Inn & Suites Carbondale", 3),
    ("Crestline:Clarion Inn & Suites - Atlanta", 2),
    ("Crestline:AC Hotel Seattle Downtown", 2),
    ("Crestline:Aloft Hotel Wichita", 2),
    ("Crestline:AC Houston Downtown", 2),
    ("Auberge", 2),
    ("Auberge:Bishop's Lodge", 2),
    ("Aperture Hotels:Clair Tappaan Lodge", 2),
    ("Aperture Hotels:Hampton Inn & Suites Memphis East Germantown Area", 2),
    ("Aperture Hotels:Hotel Indigo Tuscaloosa", 2),
]

COMPANY_LIST = []
for company, weight in COMPANIES_WEIGHTED:
    COMPANY_LIST.extend([company] * weight)

# ── Contacts (Last, First) ───────────────────────────────────────────
# Mix of repeat callers from March and new ones for February
CONTACTS = [
    "Ghareeb, Mustafa", "Buckley, Adam", "Lowe, Edward", "Griffin, Kerra",
    "Adams, Dante", "Aders, Kathy", "Aggers, Mark", "Allmond, Melissa",
    "Almashtah, Mohammed", "Alonso, Aniya", "Alonso, Ruben", "Alvarez, Karla",
    "Anthony, Marcus", "Arguello, Gisele", "Arnold, Emily", "Artiles, Kathy",
    "Bagnasco, Kenny", "Bain, Kate", "Banks, Erica", "Barnett, Craig",
    "Bartlett, Eric", "Bayliss, Nathan", "Bemben, Brian",
    # New Feb contacts
    "Chen, Lisa", "Davila, Marco", "Ellis, Jordan", "Foster, Diana",
    "Gutierrez, Pablo", "Hoffman, Sandra", "Ibrahim, Tariq", "Jeffries, Cole",
    "Kemp, Rochelle", "Lambert, Trevor", "Montoya, Silvia", "Nash, Derek",
    "Ortega, Carmen", "Palmer, Bryce", "Quinn, Sienna", "Reeves, Malik",
    "Sullivan, Bridget", "Torres, Alejandra", "Uribe, Daniel", "Vasquez, Rosa",
    "Whitaker, Gavin", "Xiong, Mei", "Yamamoto, Ken", "Zimmerman, Heidi",
    "Brooks, Tanya", "Coleman, Isaiah", "Dunn, Patricia", "Espinoza, Andres",
    "Flores, Valentina", "Garcia, Mateo", "Harris, Dominique", "Ingram, Wesley",
    "Jackson, Tamara", "Knox, Brandon", "Lewis, Shantel", "Mitchell, Darnell",
    "Navarro, Isabel", "Owens, Terrence", "Perez, Lucia", "Ramirez, Oscar",
]

# ── Issue Types with Sub-Issue Types ─────────────────────────────────
ISSUE_MAP = {
    "Email": [
        "O365/Outlook", "Send/Receive", "Spam Filtering",
        "Temporary Mailbox Forwarding", "Distribution Group - Creation",
        "Distribution Group - Modify", "Manage Distribution List",
    ],
    "User Account/Access": [
        "Password Reset", "Password", "Account Lockout", "Permissions",
        "Account Add/Remove", "Admin Level Access Request",
        "2FA/MFA - Reset", "2FA/MFA - Setup", "2FA/MFA - Disable",
        "Logon Failure",
    ],
    "Software": [
        "3rd Party Application - Error", "3rd Party Application - Install/Uninstall",
        "3rd Party Application - Update", "Office - Other", "Office - Word",
        "Browser - Google Chrome", "Browser - Edge",
    ],
    "Computer (laptop, workstation)": [
        "Windows - Other", "Windows - System Performance",
        "Windows - Operating System", "Windows - New Setup",
        "Driver Update/Install", "Error",
    ],
    "Network": [
        "Connectivity", "VPN", "Remote Access", "Browsing", "Other",
    ],
    "Hardware/Peripherals": [
        "Printer - Unable to print", "Printer - Connect/Setup",
        "Phone Equipment", "Keyboard", "Web Cam", "Fax Machine",
    ],
    "Spam": ["Spam"],
    "Security": ["Risk", "Configuration"],
    "Mobile Device": [
        "iOS - Smartphone - Mail", "Android - Smartphone - O365/Exchange",
    ],
    "Unknown": ["Unknown"],
    "Customer Concern": ["General"],
}

# Issue type weights for Feb (fewer Unknown than March's 10.3%)
ISSUE_TYPE_WEIGHTS = {
    "Email": 32,
    "User Account/Access": 20,
    "Software": 14,
    "Unknown": 5,       # Down from ~10% in March
    "Computer (laptop, workstation)": 10,
    "Network": 9,
    "Hardware/Peripherals": 5,
    "Spam": 2,
    "Security": 2,
    "Mobile Device": 1,
    "Customer Concern": 0.5,
}

ISSUE_TYPES_LIST = []
for it, w in ISSUE_TYPE_WEIGHTS.items():
    ISSUE_TYPES_LIST.extend([it] * int(w * 10))

# ── Queues ────────────────────────────────────────────────────────────
QUEUES_WEIGHTED = [
    ("KHD - Level I", 40),
    ("KHD - Escalated to Partner", 35),  # Target ~35% escalation
    ("KHD - Triage", 10),
    ("KHD - Level II", 9),
    ("KHD - SPAM", 4),
    ("Merged Tickets", 1),
    ("KHD - SDM", 1),
]

QUEUE_LIST = []
for q, w in QUEUES_WEIGHTED:
    QUEUE_LIST.extend([q] * w)

# ── Escalation Reasons ───────────────────────────────────────────────
ESCALATION_REASONS = [
    "Downed User", "MSP - Direct Request", "Infrastructure Management",
    "End User - Direct Request", "Security", "Device & Peripheral Management",
    "Spam", "Out of Scope", "Insufficient ITG Documentation",
    "Billing Inquiries/Purchases", "3rd Party Support",
    "Insufficient ITG Credentials", "Customer Unresponsive",
    "Extended Resolution Time", "Scheduled Services", "Unsupported Company",
]

ESCALATION_WEIGHTS = [14, 10, 9, 9, 7, 6, 5, 5, 4, 3, 2, 2, 2, 1, 1, 1]

# ── Primary Resources ────────────────────────────────────────────────
RESOURCES = [
    "Vera, Onix", "Blume, Theodore", "Ortiz, Brandon", "Jaramillo, Leon",
    "Cruz, Manuel", "Guzman, Giovanni", "Halsey, Justin", "Caballero, Alejandro",
    "Cabrera, Gustavo", "Carreño, Ronaldo", "Davenport, Trent", "Delgado, Mariana",
    "Dias, Bryan", "Fouquet, Jean", "Hinds, Codi", "Jackson, Unique",
    "Lichti, Liam", "Martinez, Elias", "McCann, Michael", "Mico, Leonardo",
    "Minton, Lonnie", "Nock, Louis", "Ortiz, Mateo", "Sakowicz, Brian",
    "Salgado, Christopher", "Santana, Leury", "Santiago, Yibiel", "Sharpe, Alex",
    "Solon, Kevin", "Thakar, Ricky", "Thomas, Geo", "Weaver, Danijel",
    "Woodard, Michael", "dos Santos, Felipe", "Aviles, Eric", "Bangoura, Alpha",
    "Byrd, Allan", "Cruz, Yohan", "Enukora, Nicholas",
]

# ── Titles (templates) ───────────────────────────────────────────────
TITLE_TEMPLATES = {
    "Email": [
        "{contact_first} unable to send/receive emails in Outlook",
        "{contact_first} reports Outlook not syncing on {device}",
        "Spam filtering issue - legitimate emails being blocked",
        "{contact_first} needs distribution list updated",
        "Email forwarding setup requested for {contact_first}",
        "{contact_first} cannot access shared mailbox",
        "Outlook crashing on startup for {contact_first}",
        "{contact_first} - email signature not displaying correctly",
        "Auto-reply setup request for {contact_first}",
        "{contact_first} reports missing emails from inbox",
        "Calendar invite not received by {contact_first}",
        "Need to set up email on new device for {contact_first}",
    ],
    "User Account/Access": [
        "{contact_first} reports that he forgot his network password",
        "{contact_first} requesting password reset",
        "Account lockout - {contact_first}",
        "{contact_first} needs admin access to shared drive",
        "MFA reset requested for {contact_first}",
        "New user account setup - {contact_first}",
        "{contact_first} unable to log into workstation",
        "Permission change request for {contact_first}",
        "{contact_first} - 2FA not working on mobile device",
        "Account disabled - {contact_first} requesting reactivation",
        "VPN credentials needed for {contact_first}",
        "{contact_first} locked out of Microsoft 365",
    ],
    "Software": [
        "Update Citrix",
        "{contact_first} needs Adobe Acrobat installed",
        "Microsoft Teams not launching on {device}",
        "Chrome browser crashing repeatedly",
        "QuickBooks update failing on {device}",
        "Zoom not connecting to audio for {contact_first}",
        "{contact_first} requests OneDrive app installation",
        "Java update required for hotel PMS system",
        "Microsoft Word freezing when saving documents",
        "Software license expired - {contact_first}",
        "Need to uninstall old antivirus software on {device}",
    ],
    "Computer (laptop, workstation)": [
        "{contact_first} - laptop running extremely slow",
        "Blue screen error on {device}",
        "{device} will not boot up",
        "New laptop setup for {contact_first}",
        "{contact_first} - workstation freezing intermittently",
        "Windows update failing on {device}",
        "{contact_first} reports display issues on laptop",
        "Disk space critically low on {device}",
        "Laptop not charging - {contact_first}",
        "Touchpad not working on {device}",
    ],
    "Network": [
        "Internet connectivity issues at property",
        "VPN not connecting for {contact_first}",
        "Wi-Fi dropping repeatedly in lobby area",
        "Cannot access mapped network drives",
        "{contact_first} unable to connect to remote desktop",
        "Network printer not accessible from {device}",
        "Slow internet speed reported at front desk",
        "CAPS server offline",
        "Firewall Configuration Inquiry for Margin Edge",
        "Guest WiFi portal not loading",
    ],
    "Hardware/Peripherals": [
        "{contact_first} - desk phone not working",
        "Printer paper jam - front desk printer",
        "Cannot connect to conference room projector",
        "Keyboard not responding on {device}",
        "Webcam not detected in Teams meetings",
        "Fax machine not sending outgoing faxes",
        "Monitor flickering on {contact_first}'s workstation",
        "Badge reader at entrance not scanning",
        "Receipt printer offline at front desk",
    ],
    "Spam": [
        "Suspicious email - possible phishing attempt",
        "Spam emails flooding {contact_first}'s inbox",
    ],
    "Security": [
        "Security alert - unusual sign-in activity",
        "Endpoint protection alert on {device}",
        "Suspicious login attempt from unknown location",
    ],
    "Mobile Device": [
        "{contact_first} cannot set up email on iPhone",
        "Android phone not syncing with Exchange",
    ],
    "Unknown": [
        "We detected synchronization errors in your directory",
        "Automated alert - system notification",
        "Service notification from Microsoft",
        "Alert notification - review required",
    ],
    "Customer Concern": [
        "{contact_first} has a billing question about IT services",
        "General inquiry from {contact_first}",
    ],
}

# ── Description Templates ────────────────────────────────────────────
DESCRIPTION_TEMPLATES = {
    "Email": [
        "Name: {contact_full}\nCall Back Number: {phone}\nEmail: {email}\nDevice Name: {device}\n\n{contact_first} reports issues with Outlook. Unable to send or receive emails. Restarted application and device, issue persists.",
        "Name: {contact_full}\nCall Back Number: {phone}\nEmail: {email}\nDevice Name: {device}\n\n{contact_first} is not receiving emails from external senders. Internal emails working fine. Checked spam folder - nothing there.",
    ],
    "User Account/Access": [
        "Name: {contact_full}\nCall Back Number: {phone}\nEmail: {email}\nDevice Name: {device}\n\n{contact_first} reports that he forgot his network password. He is requesting to have it reset.",
        "Name: {contact_full}\nCall Back Number: {phone}\nEmail: {email}\nDevice Name: {device}\n\n{contact_first} is locked out of their account after multiple failed login attempts. Requesting account unlock and password reset.",
    ],
    "Software": [
        "Name: {contact_full}\nCall Back Number: {phone}\nEmail: {email}\nDevice Name: {device}\n\nUser needs assistance updating/installing software on their workstation. Admin credentials required.",
        "Name: {contact_full}\nCall Back Number: {phone}\nEmail: {email}\nDevice Name: {device}\n\nApplication crashing on launch. Tried reinstall but issue persists. May need to clear cache or check compatibility.",
    ],
    "default": [
        "Name: {contact_full}\nCall Back Number: {phone}\nEmail: {email}\nDevice Name: {device}\n\n{contact_first} is reporting an issue and requesting assistance.",
    ],
}

# ── KB URLs ───────────────────────────────────────────────────────────
KB_URLS = [
    "", "", "", "",  # 40% no KB
    "https://cybertek.itglue.com/6796919",
    "https://cybertek.itglue.com/6095774",
    "https://cybertek.itglue.com/7771449",
    "https://cybertek.itglue.com/",
    "https://cybertek.itglue.com/6095774/passwords/17242355",
    "https://cybertek.itglue.com/6796919/passwords/21038821",
]

# ── Device name patterns ─────────────────────────────────────────────
DEVICE_PREFIXES = [
    "DESKTOP-", "LAPTOP-", "WS-", "FD-PC-", "2023-WLDT-",
    "2024-KAH-", "HP-", "DELL-", "LEN-",
]

DEVICE_SUFFIXES = [
    "001", "002", "003", "004", "005", "010", "015", "020",
    "FD01", "FD02", "GM01", "ACCT01",
]

# ── Helpers ───────────────────────────────────────────────────────────

def random_feb_datetime():
    """Return a random datetime in February 2026."""
    start = datetime(2026, 2, 1, 7, 0, 0)
    end = datetime(2026, 2, 28, 23, 59, 59)
    delta = end - start
    rand_seconds = random.randint(0, int(delta.total_seconds()))
    dt = start + timedelta(seconds=rand_seconds)
    # Weight toward business hours (8 AM - 6 PM) but allow some off-hours
    if random.random() < 0.15:  # 15% off-hours
        hour = random.choice(list(range(0, 8)) + list(range(18, 24)))
        dt = dt.replace(hour=hour)
    return dt


def format_dt(dt):
    """Format datetime like '02/15/2026 03:42 PM'."""
    return dt.strftime("%m/%d/%Y %I:%M %p")


def random_complete_date(created_dt, status):
    """Return a completion date. Feb has slightly worse SLA than March."""
    if status != "Complete":
        return ""
    # Most resolve same day, but some take longer (worse SLA)
    r = random.random()
    if r < 0.35:  # 35% within 30 min
        delta_min = random.randint(5, 30)
    elif r < 0.60:  # 25% within 2 hours
        delta_min = random.randint(30, 120)
    elif r < 0.80:  # 20% within same day
        delta_min = random.randint(120, 480)
    elif r < 0.92:  # 12% next day
        delta_min = random.randint(480, 1440)
    else:  # 8% multi-day (worse SLA in Feb)
        delta_min = random.randint(1440, 10080)
    return format_dt(created_dt + timedelta(minutes=delta_min))


def random_phone():
    area = random.choice(["305", "786", "954", "407", "212", "415", "312", "202", "503", "404", "650", "408", "703"])
    return f"{area}-{random.randint(200,999)}-{random.randint(1000,9999)}"


def random_email(contact):
    """Generate email from contact name."""
    if not contact:
        return "not provided"
    parts = contact.split(", ")
    if len(parts) == 2:
        last, first = parts
        domains = ["gmail.com", "crestlinehotels.com", "waldorftowersmiami.com",
                    "peachtreegroup.com", "nobuhotels.com", "aperture.com",
                    "lifespanhealth.org", "cybertek-eng.com"]
        return f"{first.lower()}.{last.lower()}@{random.choice(domains)}"
    return "not provided"


def random_device():
    return random.choice(DEVICE_PREFIXES) + random.choice(DEVICE_SUFFIXES)


def random_hours(status, queue):
    """Generate realistic hours worked."""
    if status != "Complete":
        return f"{random.uniform(0, 0.5):.2f}"
    if queue == "KHD - SPAM" or queue == "KHD - Triage":
        return f"{random.uniform(0, 0.08):.2f}"
    r = random.random()
    if r < 0.3:
        return f"{random.uniform(0.05, 0.20):.2f}"
    elif r < 0.7:
        return f"{random.uniform(0.17, 0.55):.2f}"
    elif r < 0.9:
        return f"{random.uniform(0.50, 1.50):.2f}"
    else:
        return f"{random.uniform(1.0, 3.0):.2f}"


def generate_ticket_number(dt, seq):
    """Generate Autotask-style ticket number."""
    return f"T{dt.strftime('%Y%m%d')}.{seq:04d}"


# ── Main Generation ──────────────────────────────────────────────────

def main():
    tickets = []

    # Generate created dates and sort them (most recent first, like March data)
    dates = sorted([random_feb_datetime() for _ in range(NUM_TICKETS)], reverse=True)

    # Track daily sequence numbers
    daily_seqs = {}
    daily_nexus_seqs = {}

    for i, created_dt in enumerate(dates):
        day_key = created_dt.strftime("%Y%m%d")

        # Ticket numbering: sequential within each day
        if day_key not in daily_seqs:
            daily_seqs[day_key] = random.randint(300, 500)
            daily_nexus_seqs[day_key] = random.randint(100, 250)
        daily_seqs[day_key] -= random.randint(1, 5)
        daily_nexus_seqs[day_key] -= random.randint(1, 3)

        ticket_num = f"T{day_key}.{max(daily_seqs[day_key], 1):04d}"
        nexus_num = f"T{day_key}.{max(daily_nexus_seqs[day_key], 1):04d}"

        # Company
        company = random.choice(COMPANY_LIST)

        # Contact (empty ~15% for email/spam tickets)
        if random.random() < 0.15:
            contact = ""
        else:
            contact = random.choice(CONTACTS)

        contact_first = contact.split(", ")[1] if ", " in contact else ""

        # Issue type & sub-issue type
        issue_type = random.choice(ISSUE_TYPES_LIST)
        sub_issues = ISSUE_MAP.get(issue_type, ["Unknown"])
        sub_issue = random.choice(sub_issues)

        # Status - mostly Complete
        status_r = random.random()
        if status_r < 0.90:
            status = "Complete"
        elif status_r < 0.94:
            status = "Waiting Customer"
        elif status_r < 0.97:
            status = "Reviewed"
        else:
            status = "Call Attempt Day 1"

        # Queue
        queue = random.choice(QUEUE_LIST)
        if issue_type == "Spam":
            queue = "KHD - SPAM"

        # Source - ~70% Phone for Feb (vs March's ~62%)
        source = "Phone" if random.random() < 0.75 else "Email"
        # Spam/Unknown typically come via Email
        if issue_type in ("Spam", "Unknown"):
            source = "Email" if random.random() < 0.7 else "Phone"

        # Priority
        priority_r = random.random()
        if priority_r < 0.75:
            priority = "Medium"
        elif priority_r < 0.88:
            priority = "High"
        elif priority_r < 0.93:
            priority = "Low"
        elif priority_r < 0.97:
            priority = "Critical"
        else:
            priority = "High (VIP)"

        # Parent Account
        # CyberTek MSSP is parent for most; some have none
        if company == "CyberTek MSSP" or random.random() < 0.10:
            parent_account = ""
        else:
            parent_account = "CyberTek MSSP"

        # Escalation reason (~35% escalation rate for Feb)
        is_escalated = queue == "KHD - Escalated to Partner"
        if is_escalated:
            escalation_reason = random.choices(
                ESCALATION_REASONS, weights=ESCALATION_WEIGHTS, k=1
            )[0]
        else:
            escalation_reason = ""

        # Primary Resource
        if queue in ("KHD - Triage", "KHD - SPAM") and random.random() < 0.4:
            primary_resource = ""
        else:
            primary_resource = random.choice(RESOURCES)

        # KB Used
        kb_used = random.choice(KB_URLS)

        # Complete date
        complete_date = random_complete_date(created_dt, status)

        # Hours
        hours = random_hours(status, queue)

        # Device name
        device = random_device()

        # Title
        templates = TITLE_TEMPLATES.get(issue_type, TITLE_TEMPLATES["Unknown"])
        title = random.choice(templates).format(
            contact_first=contact_first or "User",
            device=device,
        )

        # Description
        desc_templates = DESCRIPTION_TEMPLATES.get(
            issue_type, DESCRIPTION_TEMPLATES["default"]
        )
        phone_num = random_phone()
        email = random_email(contact)
        contact_full = f"{contact_first} {contact.split(', ')[0]}" if contact else "User"

        description = random.choice(desc_templates).format(
            contact_first=contact_first or "User",
            contact_full=contact_full,
            phone=phone_num,
            email=email,
            device=device,
        )

        tickets.append({
            "Ticket Number": ticket_num,
            "Nexus Ticket Number": nexus_num,
            "External Customer Ticket Ref": "",
            "Title": title,
            "Company": company,
            "Created": format_dt(created_dt),
            "Complete Date": complete_date,
            "Issue Type": issue_type,
            "Sub-Issue Type": sub_issue,
            "Status": status,
            "Parent Account": parent_account,
            "Contact": contact,
            "Queue": queue,
            "Escalation Reason": escalation_reason,
            "Source": source,
            "Priority": priority,
            "KB Used": kb_used,
            "Primary Resource": primary_resource,
            "Total Hours Worked": hours,
            "Description": description,
        })

    # Write CSV
    fieldnames = [
        "Ticket Number", "Nexus Ticket Number", "External Customer Ticket Ref",
        "Title", "Company", "Created", "Complete Date", "Issue Type",
        "Sub-Issue Type", "Status", "Parent Account", "Contact", "Queue",
        "Escalation Reason", "Source", "Priority", "KB Used",
        "Primary Resource", "Total Hours Worked", "Description",
    ]

    output_path = "/Users/virtualshinobi/CODE/khd-gov-ticket-report-builder/sample_february.csv"
    with open(output_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, quoting=csv.QUOTE_MINIMAL)
        writer.writeheader()
        writer.writerows(tickets)

    print(f"Generated {len(tickets)} tickets to {output_path}")

    # Quick stats
    esc_count = sum(1 for t in tickets if t["Escalation Reason"])
    phone_count = sum(1 for t in tickets if t["Source"] == "Phone")
    unknown_count = sum(1 for t in tickets if t["Issue Type"] == "Unknown")
    print(f"Escalation rate: {esc_count/len(tickets)*100:.1f}%")
    print(f"Phone source: {phone_count/len(tickets)*100:.1f}%")
    print(f"Unknown issue type: {unknown_count/len(tickets)*100:.1f}%")


if __name__ == "__main__":
    main()
