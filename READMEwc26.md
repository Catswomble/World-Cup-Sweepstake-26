# ⚽ World Cup 2026 Sweepstake Tracker

Automatically tracks group stage standings for your sweepstake and emails a daily leaderboard showing all 4 prize positions.

## Prizes tracked

| Prize | Criteria |
|---|---|
| 🏆 **Winner** | Person who drew the World Cup winning team |
| 💀 **Worst team** | Team with fewest points → worst GD → fewest goals → most cards |
| ⭐ **Best average** | Highest avg points/team across your 5–6 teams (group stage) |
| 😬 **Worst average** | Lowest avg points/team across your 5–6 teams (group stage) |

All ties broken by: fewest points → worst goal difference → fewest goals scored → most disciplinary cards → coin toss.

---

## Setup (one-time, ~5 minutes)

### 1. Create the GitHub repo

```bash
# Clone or create a new repo and push these files
git init wc2026-sweepstake
cd wc2026-sweepstake
# Copy all files in, then:
git add .
git commit -m "Initial sweepstake tracker"
git remote add origin https://github.com/YOUR_USERNAME/wc2026-sweepstake.git
git push -u origin main
```

### 2. Check `sweepstake.json`

The draws are already set up in `sweepstake.json`:

| Participant | Teams |
|---|---|
| Toby | Belgium, Norway, Algeria, Croatia, Senegal, Turkey |
| Mark | France, Switzerland, Ghana, Qatar, Canada |
| Jack | Spain, Uzbekistan, Scotland, Uruguay, Saudi Arabia |
| Dylan | Argentina, Mexico, South Korea, DR Congo, New Zealand, Haiti |
| Caelan | Netherlands, Austria, Czechia, Cape Verde, Jordan, Bosnia and Herzegovina |
| Yonis | England, Ecuador, Colombia, Iran, Sweden |
| Alex | Germany, USA, Australia, South Africa, Iraq |
| Dage | Portugal, Morocco, Paraguay, Ivory Coast, Tunisia |
| Isaac | Brazil, Japan, Panama, Curaçao, Egypt |

If you ever need to edit it, team names must match the group stage spelling exactly (e.g. `Czechia` not `Czech Republic`, `Ivory Coast` not `Côte d'Ivoire`).

### 3. Set up email (Gmail recommended)

You'll need a Gmail account to send the daily email. If you use 2-factor authentication (you should), create an **App Password**:

1. Go to [myaccount.google.com/apppasswords](https://myaccount.google.com/apppasswords)
2. Create a new app password (name it "Sweepstake")
3. Copy the 16-character password

Then add these **GitHub Secrets** (Settings → Secrets and variables → Actions → New repository secret):

| Secret name | Value |
|---|---|
| `EMAIL_SENDER` | Your Gmail address, e.g. `you@gmail.com` |
| `EMAIL_RECIPIENT` | Where to send updates (can be the same, or a comma-separated list) |
| `EMAIL_PASSWORD` | The 16-character App Password from step above |

### 4. Enable GitHub Actions

- Go to your repo → **Actions** tab
- If prompted, click **"I understand my workflows, go ahead and enable them"**
- The tracker will now run automatically at **8am UTC (9am BST)** every day

### 5. Test it manually

Go to **Actions → Daily Sweepstake Update → Run workflow** to trigger it immediately and check everything works.

---

## Files

```
wc2026-sweepstake/
├── sweepstaketeamswc26.json          ← Participants & teams (already configured)
├── wc26tracker.py               ← Main script (runs daily)
├── wc26requirements.txt         ← Python dependencies
├── reports/                 ← HTML reports saved here (auto-committed)
│   ├── latest.html
│   └── report_YYYY-MM-DD.html
└── .github/
    └── workflows/
        └── daily-update.yml ← GitHub Actions schedule
```

## Running locally

```bash
pip install -r requirements.txt
python tracker.py
# (No email will be sent without the env vars — report prints to terminal instead)
```

## Changing the schedule

Edit `.github/workflows/daily-update.yml` and change the cron line. The format is `minute hour day month weekday`.

- 8am UTC daily: `0 8 * * *`
- 7am UTC daily: `0 7 * * *`
- Twice daily (8am & 8pm UTC): `0 8,20 * * *`

---

*Built for the WC2026 group stage (June–July 2026). Group stage ends ~26 June 2026.*

