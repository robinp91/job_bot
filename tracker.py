#!/usr/bin/env python3
"""
Palo Alto Networks Job Tracker
Scrapes jobs.paloaltonetworks.com and sends email alerts for new matching jobs.
Criteria: Cybersecurity/InfoSec roles in Austin, Dallas, or California
"""

import json
import os
import smtplib
import sys
from datetime import datetime
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from pathlib import Path

import requests
from bs4 import BeautifulSoup

# ── Configuration ────────────────────────────────────────────────────────────

BASE_URL = "https://jobs.paloaltonetworks.com/en/search-jobs"
SEEN_FILE = Path("seen_jobs.json")

# Departments that match Cybersecurity/InfoSec interest
TARGET_DEPARTMENTS = [
    "infosec",
    "information security",
    "cybersecurity",
    "unit 42",
    "threat",
    "security",
    "sase",
    "cortex",
    "prisma",
    "netsec",
]

# Locations to match (case-insensitive)
TARGET_LOCATIONS = [
    "austin",
    "dallas",
    "plano",        # DFW metro
    "california",
    "santa clara",
    "san francisco",
    "san jose",
    "los angeles",
    "san diego",
    "burbank",
    "irvine",
]

# Email config — set these as GitHub Actions secrets (see README)
SMTP_HOST = os.environ.get("SMTP_HOST", "smtp.gmail.com")
SMTP_PORT = int(os.environ.get("SMTP_PORT", "587"))
EMAIL_SENDER = os.environ.get("EMAIL_SENDER", "")
EMAIL_PASSWORD = os.environ.get("EMAIL_PASSWORD", "")
EMAIL_RECIPIENT = os.environ.get("EMAIL_RECIPIENT", "")

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    )
}

# ── Helpers ──────────────────────────────────────────────────────────────────

def load_seen() -> set:
    if SEEN_FILE.exists():
        with open(SEEN_FILE) as f:
            return set(json.load(f))
    return set()


def save_seen(seen: set):
    with open(SEEN_FILE, "w") as f:
        json.dump(sorted(seen), f, indent=2)


def matches_location(location_text: str) -> bool:
    loc = location_text.lower()
    return any(target in loc for target in TARGET_LOCATIONS)


def matches_department(title: str, dept: str) -> bool:
    combined = (title + " " + dept).lower()
    return any(kw in combined for kw in TARGET_DEPARTMENTS)


# ── Scraping ─────────────────────────────────────────────────────────────────

def fetch_jobs(page: int = 1) -> list[dict]:
    """Fetch one page of search results and return list of job dicts."""
    params = {"p": page}
    try:
        resp = requests.get(BASE_URL, params=params, headers=HEADERS, timeout=15)
        resp.raise_for_status()
    except requests.RequestException as e:
        print(f"  ⚠️  Request error on page {page}: {e}")
        return []

    soup = BeautifulSoup(resp.text, "html.parser")
    jobs = []

    # Each job is an <li> inside the results list
    for item in soup.select("ul.jobs-list li, #search-results-list li"):
        link_tag = item.find("a")
        if not link_tag:
            continue

        title = link_tag.get_text(strip=True)
        url = link_tag.get("href", "")
        if url and not url.startswith("http"):
            url = "https://jobs.paloaltonetworks.com" + url

        # Location and department live in sibling elements
        location = ""
        department = ""
        spans = item.find_all(["span", "p"])
        for span in spans:
            text = span.get_text(strip=True)
            if "," in text and not location:   # heuristic: "Austin, Texas, United States"
                location = text
            elif location and not department:
                department = text

        if title:
            jobs.append({
                "id": url,
                "title": title,
                "location": location,
                "department": department,
                "url": url,
            })

    return jobs


def get_total_pages(soup) -> int:
    """Try to extract total page count from the pagination element."""
    page_info = soup.find(string=lambda t: t and "/ 70" in str(t))
    if page_info:
        try:
            return int(str(page_info).split("/")[-1].strip().split()[0])
        except Exception:
            pass
    return 5  # safe default — covers ~75 jobs


def scrape_all_matching_jobs() -> list[dict]:
    """Scrape pages until we've checked enough, return only matching jobs."""
    print("🔍 Scraping Palo Alto Networks jobs...")
    matching = []
    seen_titles = set()

    # We scrape up to 10 pages (150 jobs). PAN sorts by date desc,
    # so newer jobs appear first — we'll catch fresh postings quickly.
    for page in range(1, 11):
        print(f"  Page {page}...")
        jobs = fetch_jobs(page)
        if not jobs:
            break

        for job in jobs:
            if job["id"] in seen_titles:
                continue
            seen_titles.add(job["id"])

            if matches_location(job["location"]) and matches_department(job["title"], job["department"]):
                matching.append(job)

    print(f"✅ Found {len(matching)} matching jobs total.")
    return matching


# ── Email ────────────────────────────────────────────────────────────────────

def build_email_html(new_jobs: list[dict]) -> str:
    rows = ""
    for job in new_jobs:
        rows += f"""
        <tr>
          <td style="padding:10px 8px; border-bottom:1px solid #eee;">
            <a href="{job['url']}" style="color:#0070c9; font-weight:600; text-decoration:none;">
              {job['title']}
            </a>
          </td>
          <td style="padding:10px 8px; border-bottom:1px solid #eee; color:#555;">
            {job['location']}
          </td>
          <td style="padding:10px 8px; border-bottom:1px solid #eee; color:#555;">
            {job['department']}
          </td>
        </tr>"""

    return f"""
    <html><body style="font-family:Arial,sans-serif; color:#222; max-width:700px; margin:auto;">
      <div style="background:#0070c9; padding:20px 24px; border-radius:8px 8px 0 0;">
        <h2 style="color:white; margin:0;">🔐 New PAN Job Alerts</h2>
        <p style="color:#cce4ff; margin:4px 0 0;">{len(new_jobs)} new posting(s) — {datetime.now().strftime('%B %d, %Y %I:%M %p')}</p>
      </div>
      <div style="border:1px solid #ddd; border-top:none; border-radius:0 0 8px 8px; padding:16px;">
        <p>New <strong>Cybersecurity/InfoSec</strong> roles in <strong>Austin, Dallas, or California</strong>:</p>
        <table style="width:100%; border-collapse:collapse; font-size:14px;">
          <thead>
            <tr style="background:#f5f5f5;">
              <th style="padding:8px; text-align:left;">Role</th>
              <th style="padding:8px; text-align:left;">Location</th>
              <th style="padding:8px; text-align:left;">Department</th>
            </tr>
          </thead>
          <tbody>{rows}</tbody>
        </table>
        <p style="margin-top:20px; font-size:12px; color:#888;">
          You're receiving this because you set up a PAN job tracker. 
          <a href="https://jobs.paloaltonetworks.com/en/search-jobs">View all jobs →</a>
        </p>
      </div>
    </body></html>
    """


def send_email(new_jobs: list[dict]):
    if not all([EMAIL_SENDER, EMAIL_PASSWORD, EMAIL_RECIPIENT]):
        print("⚠️  Email env vars not set — skipping send. (Set EMAIL_SENDER, EMAIL_PASSWORD, EMAIL_RECIPIENT)")
        for j in new_jobs:
            print(f"  NEW: {j['title']} | {j['location']}")
        return

    msg = MIMEMultipart("alternative")
    msg["Subject"] = f"🔐 {len(new_jobs)} New PAN Cybersecurity Job(s) — Austin/Dallas/CA"
    msg["From"] = EMAIL_SENDER
    msg["To"] = EMAIL_RECIPIENT

    msg.attach(MIMEText(build_email_html(new_jobs), "html"))

    with smtplib.SMTP(SMTP_HOST, SMTP_PORT) as server:
        server.ehlo()
        server.starttls()
        server.login(EMAIL_SENDER, EMAIL_PASSWORD)
        server.sendmail(EMAIL_SENDER, EMAIL_RECIPIENT, msg.as_string())

    print(f"📧 Email sent with {len(new_jobs)} new job(s).")


# ── Main ─────────────────────────────────────────────────────────────────────

def main():
    seen = load_seen()
    all_matching = scrape_all_matching_jobs()

    new_jobs = [j for j in all_matching if j["id"] not in seen]
    print(f"🆕 {len(new_jobs)} new job(s) since last run.")

    if new_jobs:
        send_email(new_jobs)
        # Mark all as seen
        seen.update(j["id"] for j in new_jobs)
        save_seen(seen)
    else:
        print("No new jobs — nothing to send.")

    # Always update seen with full current list (handles removed jobs gracefully)
    # Uncomment below if you want to re-alert on jobs that were removed and re-posted:
    # seen = set(j["id"] for j in all_matching)
    # save_seen(seen)


if __name__ == "__main__":
    main()
