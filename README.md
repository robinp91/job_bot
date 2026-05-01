# 🔐 Palo Alto Networks Job Tracker

Automatically checks PAN's job board twice daily and emails you new
**Cybersecurity/InfoSec** postings in **Austin, Dallas, or California**.

Fully free — runs on GitHub Actions + Gmail.

---

## Setup (10 minutes)

### 1. Create a GitHub repo

1. Go to [github.com/new](https://github.com/new)
2. Name it something like `pan-job-tracker`
3. Set it to **Private**
4. Click **Create repository**

### 2. Upload these files

Upload all files from this folder into the root of your repo:
```
tracker.py
requirements.txt
seen_jobs.json
.github/
  workflows/
    tracker.yml
```

You can drag-and-drop files on GitHub's web UI, or use Git:
```bash
git clone https://github.com/YOUR_USERNAME/pan-job-tracker
# copy files in, then:
git add .
git commit -m "Initial setup"
git push
```

### 3. Set up Gmail App Password

> Gmail requires an **App Password** (not your regular password) for SMTP.

1. Go to your Google Account → **Security**
2. Enable **2-Step Verification** if not already on
3. Search for **"App Passwords"** → Create one
4. Name it "PAN Job Tracker" → Copy the 16-character password

### 4. Add GitHub Secrets

In your repo → **Settings** → **Secrets and variables** → **Actions** → **New repository secret**

Add these 3 secrets:

| Secret Name      | Value                              |
|------------------|------------------------------------|
| `EMAIL_SENDER`   | your Gmail address                 |
| `EMAIL_PASSWORD` | the 16-char App Password from above|
| `EMAIL_RECIPIENT`| email where you want alerts sent   |

> `EMAIL_SENDER` and `EMAIL_RECIPIENT` can be the same address.

### 5. Test it manually

1. Go to your repo → **Actions** tab
2. Click **PAN Job Tracker** → **Run workflow** → **Run workflow**
3. Watch the logs — you should get an email if any matching jobs exist!

---

## Schedule

The tracker runs at:
- **3:00 AM Central Time** (8:00 AM UTC)
- **1:00 PM Central Time** (6:00 PM UTC)

To adjust, edit the cron lines in `.github/workflows/tracker.yml`:
```yaml
- cron: "0 8 * * *"   # 8am UTC = 3am CT
- cron: "0 18 * * *"  # 6pm UTC = 1pm CT
```
Use [crontab.guru](https://crontab.guru) to build your preferred schedule.

---

## Customizing criteria

Open `tracker.py` and edit these two lists near the top:

```python
# Keywords matched against job title + department
TARGET_DEPARTMENTS = [
    "infosec", "security", "unit 42", "cortex", "sase", ...
]

# Substrings matched against the location field
TARGET_LOCATIONS = [
    "austin", "dallas", "california", "santa clara", ...
]
```

Add or remove keywords to widen/narrow your alerts.

---

## How it works

```
GitHub Actions (cron) → tracker.py
  └─ Fetches up to 10 pages of PAN job listings
  └─ Filters by location + department keywords
  └─ Compares against seen_jobs.json (stored in repo)
  └─ Sends HTML email for any new matches
  └─ Commits updated seen_jobs.json back to repo
```

No database, no server, no cost.
