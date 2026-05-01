#!/usr/bin/env python3
"""
Palo Alto Networks Job Tracker
Scrapes jobs.paloaltonetworks.com and sends email alerts for new matching jobs.

Criteria:
  - Department : Global Customer Services
  - Keywords   : Cortex, SOAR, CNAPP, Prisma
  - Seniority  : 3-7 years experience range
                 (matched via title keywords: excludes Junior/Associate/Intern
                  and excludes Staff/Principal/Director/VP/Fellow)
  - Locations  : Austin, Dallas, California
"""

import json
import os
import smtplib
from datetime import datetime
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from pathlib import Path

import requests
from bs4 import BeautifulSoup

# Configuration
BASE_URL   = "https://jobs.paloaltonetworks.com/en/search-jobs"
SEEN_FILE  = Path("seen_jobs.json")

# Target Department
TARGET_DEPARTMENTS = [
    "global customer services",
    "customer services",
    "customer success",
    "technical support",
    "gcs",
]

# Product / Technology Keywords
TARGET_KEYWORDS = [
    "cortex",
    "soar",
    "cnapp",
    "prisma",
    "xsiam",
    "xdr",
    "security",
    "technical support",
]

# Locations
TARGET_LOCATIONS = [
    "austin",
    "dallas",
    "plano",
    "california",
    "santa clara",
    "san francisco",
    "san jose",
    "los angeles",
    "san diego",
    "burbank",
    "irvine",
]

# Too junior (exclude)
EXCLUDE_SENIORITY = [
    "junior",
    "associate",
    "intern",
    "entry",
    "apprentice",
    "graduate",
    "new grad",
]

# Too senior (exclude)
EXCLUDE_OVER_SENIORITY = [
    "sr. staff",
    "senior staff",
    "principal",
    "director",
    "vice president",
    " vp ",
    "fellow",
    "distinguished",
    "head of",
    "chief",
]

# Email config
SMTP_HOST       = os.environ.get("SMTP_HOST", "smtp.gmail.com")
SMTP_PORT       = int(os.environ.get("SMTP_PORT", "587"))
EMAIL_SENDER    = os.environ.get("EMAIL_SENDER", "")
EMAIL_PASSWORD  = os.environ.get("EMAIL_PASSWORD", "")
EMAIL_RECIPIENT = os.environ.get("EMAIL_RECIPIENT", "")

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    )
}

# Filter functions

def matches_location(location_text):
    loc = location_text.lower()
    return any(target in loc for target in TARGET_LOCATIONS)

def matches_department(title, dept):
    combined = (title + " " + dept).lower()
    return any(kw in combined for kw in TARGET_DEPARTMENTS)

def matches_keyword(title, dept):
    combined = (title + " " + dept).lower()
    return any(kw in combined for kw in TARGET_KEYWORDS)

def matches_seniority(title):
    t = title.lower()
    if any(kw in t for kw in EXCLUDE_SENIORITY):
        return False
    if any(kw in t for kw in EXCLUDE_OVER_SENIORITY):
        return False
    return True

def matches_all(job):
    title = job.get("title", "")
    dept  = job.get("department", "")
    loc   = job.get("location", "")
    return (
        matches_location(loc)
        and matches_keyword(title, dept)
        and matches_seniority(title)
    )

# Scraping

def fetch_jobs(page=1):
    params = {"p": page}
    try:
        resp = requests.get(BASE_URL, params=params, headers=HEADERS, timeout=15)
        resp.raise_for_status()
    except requests.RequestException as e:
        print(f"  Warning: Request error on page {page}: {e}")
        return []

    soup = BeautifulSoup(resp.text, "html.parser")
    jobs = []

    for item in soup.select("ul.jobs-list li, #search-results-list li"):
        link_tag = item.find("a")
        if not link_tag:
            continue

        title = link_tag.get_text(strip=True)
        url   = link_tag.get("href", "")
        if url and not url.startswith("http"):
            url = "https://jobs.paloaltonetworks.com" + url

        location   = ""
        department = ""
        spans = item.find_all(["span", "p"])
        for span in spans:
            text = span.get_text(strip=True)
            if "," in text and not location:
                location = text
            elif location and not department:
                department = text

        if title:
            jobs.append({
                "id":         url,
                "title":      title,
                "location":   location,
                "department": department,
                "url":        url,
            })

    return jobs

def scrape_all_matching_jobs():
    print("Scraping Palo Alto Networks jobs...")
    matching = []
    seen_ids = set()

    for page in range(1, 11):
        print(f"  Page {page}...")
        jobs = fetch_jobs(page)
        if not jobs:
            break

        for job in jobs:
            if job["id"] in seen_ids:
                continue
            seen_ids.add(job["id"])

            if matches_all(job):
                matching.append(job)
                print(f"  MATCH: {job['title']} | {job['location']}")

    print(f"\nFound {len(matching)} matching jobs total.")
    return matching

# Seen jobs tracking

def load_seen():
    if SEEN_FILE.exists():
        with open(SEEN_FILE) as f:
            return set(json.load(f))
    return set()

def save_seen(seen):
    with open(SEEN_FILE, "w") as f:
        json.dump(sorted(seen), f, indent=2)

# Email

def build_email_html(new_jobs):
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
        <h2 style="color:white; margin:0;">New PAN Job Alerts</h2>
        <p style="color:#cce4ff; margin:4px 0 0;">
          {len(new_jobs)} new posting(s) - {datetime.now().strftime('%B %d, %Y %I:%M %p')}
        </p>
      </div>
      <div style="border:1px solid #ddd; border-top:none; border-radius:0 0 8px 8px; padding:16px;">
        <p style="margin:0 0 4px;"><strong>Your active filters:</strong></p>
        <ul style="color:#555; font-size:13px;">
          <li><strong>Department:</strong> Global Customer Services</li>
          <li><strong>Keywords:</strong> Cortex, SOAR, CNAPP, Prisma</li>
          <li><strong>Seniority:</strong> 3-7 years (Mid / Senior level)</li>
          <li><strong>Locations:</strong> Austin, Dallas, California</li>
        </ul>
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
          <a href="https://jobs.paloaltonetworks.com/en/search-jobs">View all PAN jobs</a>
        </p>
      </div>
    </body></html>
    """

def send_email(new_jobs):
    if not all([EMAIL_SENDER, EMAIL_PASSWORD, EMAIL_RECIPIENT]):
        print("Email env vars not set - printing matches instead:")
        for j in new_jobs:
            print(f"  - {j['title']} | {j['location']}")
        return

    msg = MIMEMultipart("alternative")
    msg["Subject"] = f"{len(new_jobs)} New PAN Job(s) - GCS / Cortex / Prisma / SOAR"
    msg["From"]    = EMAIL_SENDER
    msg["To"]      = EMAIL_RECIPIENT
    msg.attach(MIMEText(build_email_html(new_jobs), "html"))

    with smtplib.SMTP(SMTP_HOST, SMTP_PORT) as server:
        server.ehlo()
        server.starttls()
        server.login(EMAIL_SENDER, EMAIL_PASSWORD)
        server.sendmail(EMAIL_SENDER, EMAIL_RECIPIENT, msg.as_string())

    print(f"Email sent with {len(new_jobs)} new job(s).")

# Main

def main():
    seen         = load_seen()
    all_matching = scrape_all_matching_jobs()
    new_jobs     = [j for j in all_matching if j["id"] not in seen]

    print(f"{len(new_jobs)} new job(s) since last run.")

    if new_jobs:
        send_email(new_jobs)
        seen.update(j["id"] for j in new_jobs)
        save_seen(seen)
    else:
        print("No new jobs - nothing to send.")

if __name__ == "__main__":
    main()
