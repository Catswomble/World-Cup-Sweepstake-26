#!/usr/bin/env python3
"""
World Cup 2026 Sweepstake Tracker
Fetches live group stage standings and calculates prize positions.
"""

import json
import os
import smtplib
import sys
from datetime import datetime, timezone
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

import requests
from bs4 import BeautifulSoup

# ── Config ─────────────────────────────────────────────────────────────────────

SWEEPSTAKE_FILE = "sweepstaketeamswc26.json"

# All 48 teams mapped to their group (for reference / normalisation)
ALL_GROUPS = {
    "A": ["Mexico", "South Africa", "South Korea", "Czechia"],
    "B": ["Canada", "Bosnia and Herzegovina", "Qatar", "Switzerland"],
    "C": ["Brazil", "Morocco", "Haiti", "Scotland"],
    "D": ["USA", "Paraguay", "Australia", "Turkey"],
    "E": ["Germany", "Curacao", "Ivory Coast", "Ecuador"],
    "F": ["Netherlands", "Japan", "Sweden", "Tunisia"],
    "G": ["Belgium", "Egypt", "Iran", "New Zealand"],
    "H": ["Spain", "Cape Verde", "Saudi Arabia", "Uruguay"],
    "I": ["France", "Senegal", "Iraq", "Norway"],
    "J": ["Argentina", "Algeria", "Austria", "Jordan"],
    "K": ["Portugal", "DR Congo", "Uzbekistan", "Colombia"],
    "L": ["England", "Croatia", "Ghana", "Panama"],
}

# Normalise team name variations from different data sources
NAME_MAP = {
    "türkiye": "Turkey",
    "turkiye": "Turkey",
    "côte d'ivoire": "Ivory Coast",
    "cote d'ivoire": "Ivory Coast",
    "côte divoire": "Ivory Coast",
    "ir iran": "Iran",
    "cabo verde": "Cape Verde",
    "dr congo": "DR Congo",
    "democratic republic of congo": "DR Congo",
    "bosnia & herzegovina": "Bosnia and Herzegovina",
    "bosnia-herzegovina": "Bosnia and Herzegovina",
    "república checa": "Czechia",
    "czech republic": "Czechia",
    "united states": "USA",
    "united states of america": "USA",
    "curaçao": "Curacao",
    "new zealand": "New Zealand",
    "south africa": "South Africa",
    "south korea": "South Korea",
    "saudi arabia": "Saudi Arabia",
}

def normalise(name: str) -> str:
    """Normalise a team name to match our sweepstake.json format."""
    n = name.strip().lower()
    return NAME_MAP.get(n, name.strip().title())


# ── Data Fetching ───────────────────────────────────────────────────────────────

def fetch_standings_from_fifa() -> dict[str, dict]:
    """
    Fetch group stage standings from the official FIFA website.
    Returns a dict keyed by team name with their stats.
    """
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/120.0.0.0 Safari/537.36"
        )
    }

    teams: dict[str, dict] = {}

    for group_letter in ALL_GROUPS:
        url = (
            f"https://www.fifa.com/en/tournaments/mens/worldcup/"
            f"canadamexicousa2026/standings?group={group_letter}"
        )
        try:
            resp = requests.get(url, headers=headers, timeout=15)
            resp.raise_for_status()
            soup = BeautifulSoup(resp.text, "html.parser")

            # FIFA standings rows — each row is a team
            rows = soup.select("tr[data-testid*='group-standing-row']") or \
                   soup.select("tbody tr")

            for row in rows:
                cells = row.find_all("td")
                if len(cells) < 9:
                    continue
                try:
                    # Typical FIFA table: Pos | Team | P | W | D | L | GF | GA | GD | Pts | YC | RC
                    team_el = row.select_one("[data-testid='team-name']") or cells[1]
                    raw_name = team_el.get_text(strip=True)
                    name = normalise(raw_name)

                    def ci(idx, default=0):
                        try:
                            return int(cells[idx].get_text(strip=True))
                        except (ValueError, IndexError):
                            return default

                    teams[name] = {
                        "group": group_letter,
                        "played": ci(2),
                        "won": ci(3),
                        "drawn": ci(4),
                        "lost": ci(5),
                        "gf": ci(6),   # goals for
                        "ga": ci(7),   # goals against
                        "gd": ci(8),   # goal difference
                        "points": ci(9),
                        "yellow_cards": ci(10),
                        "red_cards": ci(11),
                    }
                except Exception:
                    continue

        except Exception as e:
            print(f"  Warning: could not fetch Group {group_letter} from FIFA: {e}")

    return teams


def fetch_standings_fallback() -> dict[str, dict]:
    """
    Fallback: scrape standings from ESPN or BBC Sport if FIFA site fails.
    """
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/120.0.0.0 Safari/537.36"
        )
    }

    teams: dict[str, dict] = {}

    try:
        resp = requests.get(
            "https://www.bbc.co.uk/sport/football/world-cup/tables",
            headers=headers, timeout=15
        )
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "html.parser")

        group_sections = soup.select(".gs-o-table")
        for section in group_sections:
            rows = section.select("tbody tr")
            for row in rows:
                cells = row.find_all("td")
                if len(cells) < 8:
                    continue
                try:
                    raw_name = cells[0].get_text(strip=True)
                    name = normalise(raw_name)
                    def ci(idx, default=0):
                        try:
                            return int(cells[idx].get_text(strip=True))
                        except (ValueError, IndexError):
                            return default
                    teams[name] = {
                        "group": "?",
                        "played": ci(1),
                        "won": ci(2),
                        "drawn": ci(3),
                        "lost": ci(4),
                        "gf": ci(5),
                        "ga": ci(6),
                        "gd": ci(5) - ci(6),
                        "points": ci(7),
                        "yellow_cards": 0,
                        "red_cards": 0,
                    }
                except Exception:
                    continue
    except Exception as e:
        print(f"  Warning: fallback scrape also failed: {e}")

    return teams


def get_all_standings() -> dict[str, dict]:
    """Try FIFA first, fallback to BBC if needed."""
    print("Fetching standings from FIFA...")
    standings = fetch_standings_from_fifa()

    if len(standings) < 10:
        print("FIFA fetch returned too few teams, trying BBC fallback...")
        standings = fetch_standings_fallback()

    if not standings:
        print("ERROR: Could not fetch any standings. Using zeros.")
        # Build empty standings so the script still runs
        for group, team_list in ALL_GROUPS.items():
            for t in team_list:
                standings[t] = {
                    "group": group, "played": 0, "won": 0, "drawn": 0,
                    "lost": 0, "gf": 0, "ga": 0, "gd": 0,
                    "points": 0, "yellow_cards": 0, "red_cards": 0,
                }

    print(f"  Got standings for {len(standings)} teams.")
    return standings


# ── Prize Calculations ─────────────────────────────────────────────────────────

def tiebreak_key(team_stats: dict) -> tuple:
    """
    Returns a sort key for 'worst team' prize.
    Lower is worse (ascending): fewer points, worse GD, fewer goals, more cards.
    """
    s = team_stats
    cards = s.get("yellow_cards", 0) + (s.get("red_cards", 0) * 3)
    return (
        s.get("points", 0),         # fewer = worse
        s.get("gd", 0),             # lower = worse
        s.get("gf", 0),             # fewer = worse
        -cards,                     # more cards = worse (negate so lower sort = more cards)
    )


def load_sweepstake() -> list[dict]:
    with open(SWEEPSTAKE_FILE) as f:
        data = json.load(f)
    return data["participants"]


def calculate_prizes(participants: list[dict], standings: dict[str, dict]) -> dict:
    """
    Work out standings for all 4 prizes.
    """
    results = []

    all_teams_in_play = set()

    for p in participants:
        real_teams = [t for t in p["teams"] if t != "BLANK"]
        all_teams_in_play.update(real_teams)

        team_stats = []
        total_points = 0
        has_any_data = False

        for team in real_teams:
            # Try exact match first, then case-insensitive
            stats = standings.get(team)
            if not stats:
                for k, v in standings.items():
                    if k.lower() == team.lower():
                        stats = v
                        break
            if not stats:
                stats = {
                    "group": "?", "played": 0, "won": 0, "drawn": 0,
                    "lost": 0, "gf": 0, "ga": 0, "gd": 0,
                    "points": 0, "yellow_cards": 0, "red_cards": 0,
                }
            else:
                if stats["played"] > 0:
                    has_any_data = True
            team_stats.append((team, stats))
            total_points += stats.get("points", 0)

        avg_points = total_points / len(real_teams) if real_teams else 0

        results.append({
            "name": p["name"],
            "real_teams": real_teams,
            "num_teams": len(real_teams),
            "team_stats": team_stats,
            "total_points": total_points,
            "avg_points": avg_points,
            "has_data": has_any_data,
        })

    # ── Prize: Best average ────────────────────────────────────
    def avg_tiebreak(r):
        # Higher avg = better. Tiebreak: higher total, then GD sum, etc.
        total_gd = sum(s.get("gd", 0) for _, s in r["team_stats"])
        total_gf = sum(s.get("gf", 0) for _, s in r["team_stats"])
        total_cards = sum(
            s.get("yellow_cards", 0) + s.get("red_cards", 0) * 3
            for _, s in r["team_stats"]
        )
        return (-r["avg_points"], -total_gd, -total_gf, total_cards)

    sorted_by_avg = sorted(results, key=avg_tiebreak)

    # ── Prize: Worst average ───────────────────────────────────
    def worst_avg_tiebreak(r):
        total_gd = sum(s.get("gd", 0) for _, s in r["team_stats"])
        total_gf = sum(s.get("gf", 0) for _, s in r["team_stats"])
        total_cards = sum(
            s.get("yellow_cards", 0) + s.get("red_cards", 0) * 3
            for _, s in r["team_stats"]
        )
        return (r["avg_points"], total_gd, total_gf, -total_cards)

    sorted_by_worst_avg = sorted(results, key=worst_avg_tiebreak)

    # ── Prize: Worst individual team ──────────────────────────
    all_team_entries = []
    for r in results:
        for team, stats in r["team_stats"]:
            all_team_entries.append({
                "participant": r["name"],
                "team": team,
                "stats": stats,
                "sort_key": tiebreak_key(stats),
            })

    sorted_worst_teams = sorted(all_team_entries, key=lambda x: x["sort_key"])
    worst_team_entry = sorted_worst_teams[0] if sorted_worst_teams else None

    return {
        "results": results,
        "best_avg_ranking": sorted_by_avg,
        "worst_avg_ranking": sorted_by_worst_avg,
        "worst_team": worst_team_entry,
        "all_worst_teams": sorted_worst_teams[:5],  # show top 5 contenders
    }


# ── Report Generation ──────────────────────────────────────────────────────────

def medal(pos: int) -> str:
    return ["🥇", "🥈", "🥉", "4️⃣", "5️⃣", "6️⃣", "7️⃣", "8️⃣", "9️⃣"][pos] if pos < 9 else f"{pos+1}."


def build_report(prizes: dict, standings: dict) -> tuple[str, str]:
    """Returns (plain_text, html) report."""
    now = datetime.now(timezone.utc).strftime("%A %d %B %Y, %H:%M UTC")
    results = prizes["results"]

    # ── Plain text ─────────────────────────────────────────────
    lines = [
        "=" * 60,
        f"  ⚽ WORLD CUP 2026 SWEEPSTAKE UPDATE",
        f"  {now}",
        "=" * 60,
        "",
    ]

    # Individual team standings per person
    lines.append("📋 YOUR TEAMS — CURRENT STANDINGS")
    lines.append("-" * 60)
    for r in sorted(results, key=lambda x: x["name"]):
        lines.append(f"\n{r['name']}  (avg: {r['avg_points']:.2f} pts/team)")
        for team, s in r["team_stats"]:
            played = s['played']
            pts = s['points']
            gd = s['gd']
            gf = s['gf']
            lines.append(
                f"  {'✅' if played > 0 else '⏳'} {team:<22} "
                f"P{played} | Pts:{pts} | GD:{gd:+d} | GF:{gf}"
            )

    lines += ["", "=" * 60, "🏆 PRIZE LEADERBOARDS", "=" * 60]

    # Prize 1: Winner
    lines += ["", "🎯 WHO HAS THE WINNING TEAM?"]
    lines.append("  (Updated once knockout stage begins)")
    for r in results:
        for team, s in r["team_stats"]:
            if s["played"] > 0:
                lines.append(f"  {r['name']} has {team}")

    # Prize 2: Worst team
    wt = prizes["worst_team"]
    if wt:
        s = wt["stats"]
        lines += [
            "",
            "💀 WORST TEAM PRIZE CONTENDERS (team with fewest points):",
        ]
        for i, entry in enumerate(prizes["all_worst_teams"]):
            st = entry["stats"]
            cards = st.get("yellow_cards", 0) + st.get("red_cards", 0) * 3
            lines.append(
                f"  {medal(i)} {entry['team']:<22} "
                f"(held by {entry['participant']}) — "
                f"Pts:{st['points']} GD:{st['gd']:+d} GF:{st['gf']} Cards:{cards}"
            )

    # Prize 3: Best average
    lines += ["", "⭐ BEST AVERAGE POINTS/TEAM (group stage):"]
    for i, r in enumerate(prizes["best_avg_ranking"]):
        lines.append(f"  {medal(i)} {r['name']:<15} {r['avg_points']:.3f} avg  ({r['total_points']} pts from {r['num_teams']} teams)")

    # Prize 4: Worst average
    lines += ["", "😬 WORST AVERAGE POINTS/TEAM (group stage):"]
    for i, r in enumerate(prizes["worst_avg_ranking"]):
        lines.append(f"  {medal(i)} {r['name']:<15} {r['avg_points']:.3f} avg  ({r['total_points']} pts from {r['num_teams']} teams)")

    lines += ["", "=" * 60, "Next update tomorrow. Good luck! ⚽", "=" * 60]
    plain = "\n".join(lines)

    # ── HTML ───────────────────────────────────────────────────
    def row_color(i):
        return "#f9f9f9" if i % 2 == 0 else "#ffffff"

    def pts_badge(pts):
        color = "#2ecc71" if pts >= 6 else "#e67e22" if pts >= 3 else "#e74c3c" if pts > 0 else "#95a5a6"
        return f'<span style="background:{color};color:white;padding:2px 7px;border-radius:10px;font-weight:bold">{pts}pts</span>'

    team_rows = ""
    for r in sorted(results, key=lambda x: x["name"]):
        team_rows += f"""
        <tr>
          <td colspan="6" style="background:#2c3e50;color:white;padding:8px 12px;font-weight:bold">
            {r['name']} &nbsp;<small style="font-weight:normal;opacity:.7">avg {r['avg_points']:.2f} pts/team</small>
          </td>
        </tr>"""
        for i, (team, s) in enumerate(r["team_stats"]):
            played = s['played']
            cards = s.get('yellow_cards', 0) + s.get('red_cards', 0) * 3
            team_rows += f"""
        <tr style="background:{row_color(i)}">
          <td style="padding:6px 12px">{'✅' if played > 0 else '⏳'} {team}</td>
          <td style="text-align:center">{pts_badge(s['points'])}</td>
          <td style="text-align:center">P{played}</td>
          <td style="text-align:center">{s['gd']:+d} GD</td>
          <td style="text-align:center">{s['gf']} GF</td>
          <td style="text-align:center">🟨×{s.get('yellow_cards',0)} 🟥×{s.get('red_cards',0)}</td>
        </tr>"""

    best_avg_rows = ""
    for i, r in enumerate(prizes["best_avg_ranking"]):
        best_avg_rows += f"""
        <tr style="background:{row_color(i)}">
          <td style="padding:6px 12px">{medal(i)} {r['name']}</td>
          <td style="text-align:center;font-weight:bold">{r['avg_points']:.3f}</td>
          <td style="text-align:center">{r['total_points']} pts</td>
          <td style="text-align:center">{r['num_teams']} teams</td>
        </tr>"""

    worst_avg_rows = ""
    for i, r in enumerate(prizes["worst_avg_ranking"]):
        worst_avg_rows += f"""
        <tr style="background:{row_color(i)}">
          <td style="padding:6px 12px">{medal(i)} {r['name']}</td>
          <td style="text-align:center;font-weight:bold">{r['avg_points']:.3f}</td>
          <td style="text-align:center">{r['total_points']} pts</td>
          <td style="text-align:center">{r['num_teams']} teams</td>
        </tr>"""

    worst_team_rows = ""
    for i, entry in enumerate(prizes["all_worst_teams"]):
        st = entry["stats"]
        cards = st.get("yellow_cards", 0) + st.get("red_cards", 0) * 3
        worst_team_rows += f"""
        <tr style="background:{row_color(i)}">
          <td style="padding:6px 12px">{medal(i)} {entry['team']}</td>
          <td style="text-align:center">{entry['participant']}</td>
          <td style="text-align:center">{st['points']} pts</td>
          <td style="text-align:center">{st['gd']:+d} GD</td>
          <td style="text-align:center">{st['gf']} GF</td>
          <td style="text-align:center">{cards} cards</td>
        </tr>"""

    table_style = "width:100%;border-collapse:collapse;margin-bottom:24px;font-size:14px"
    th_style = "background:#34495e;color:white;padding:8px 12px;text-align:left"

    html = f"""<!DOCTYPE html>
<html>
<head><meta charset="utf-8">
<style>
  body {{ font-family: Arial, sans-serif; max-width: 700px; margin: 0 auto; padding: 20px; color: #333; }}
  h1 {{ background: linear-gradient(135deg, #1a6b1a, #2ecc71); color: white; padding: 20px; border-radius: 8px; }}
  h2 {{ color: #2c3e50; border-bottom: 2px solid #2ecc71; padding-bottom: 6px; }}
  table {{ {table_style} }}
  th {{ {th_style} }}
  td {{ border-bottom: 1px solid #eee; }}
  .footer {{ color: #999; font-size: 12px; text-align:center; margin-top: 30px; }}
</style>
</head>
<body>
<h1>⚽ World Cup 2026 Sweepstake<br><small style="font-size:0.6em">{now}</small></h1>

<h2>📋 All Teams — Current Standings</h2>
<table>
  <thead><tr>
    <th>Team</th><th>Points</th><th>Played</th><th>Goal Diff</th><th>Goals For</th><th>Cards</th>
  </tr></thead>
  <tbody>{team_rows}</tbody>
</table>

<h2>⭐ Best Average Pts/Team</h2>
<p style="color:#666;font-size:13px">Highest average points across your teams (group stage). Prize goes to position 🥇.</p>
<table>
  <thead><tr><th>Participant</th><th>Avg Pts/Team</th><th>Total Pts</th><th>Teams</th></tr></thead>
  <tbody>{best_avg_rows}</tbody>
</table>

<h2>😬 Worst Average Pts/Team</h2>
<p style="color:#666;font-size:13px">Lowest average — another prize! Position 🥇 wins (or loses, depending how you look at it).</p>
<table>
  <thead><tr><th>Participant</th><th>Avg Pts/Team</th><th>Total Pts</th><th>Teams</th></tr></thead>
  <tbody>{worst_avg_rows}</tbody>
</table>

<h2>💀 Worst Individual Team (Top 5 Contenders)</h2>
<p style="color:#666;font-size:13px">Tiebreak: fewest points → worst GD → fewest goals scored → most cards.</p>
<table>
  <thead><tr><th>Team</th><th>Held By</th><th>Points</th><th>GD</th><th>Goals For</th><th>Cards</th></tr></thead>
  <tbody>{worst_team_rows}</tbody>
</table>

<p class="footer">Auto-generated by your WC2026 Sweepstake Tracker · Next update tomorrow ⚽</p>
</body>
</html>"""

    return plain, html


# ── Email Sending ──────────────────────────────────────────────────────────────

def send_email(plain: str, html: str):
    """Send the report via Gmail SMTP using GitHub Actions secrets."""
    sender = os.environ.get("EMAIL_SENDER")
    recipient = os.environ.get("EMAIL_RECIPIENT")
    password = os.environ.get("EMAIL_PASSWORD")

    if not all([sender, recipient, password]):
        print("Email env vars not set — printing report to stdout instead.\n")
        print(plain)
        return

    msg = MIMEMultipart("alternative")
    today = datetime.now(timezone.utc).strftime("%d %b")
    msg["Subject"] = f"⚽ WC2026 Sweepstake Update — {today}"
    msg["From"] = sender
    msg["To"] = recipient

    msg.attach(MIMEText(plain, "plain"))
    msg.attach(MIMEText(html, "html"))

    try:
        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
            server.login(sender, password)
            server.sendmail(sender, recipient.split(","), msg.as_string())
        print(f"✅ Email sent to {recipient}")
    except Exception as e:
        print(f"❌ Email failed: {e}")
        print(plain)  # fallback print


# ── Main ───────────────────────────────────────────────────────────────────────

def main():
    print(f"\n{'='*50}")
    print(f"  WC2026 Sweepstake Tracker — {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}")
    print(f"{'='*50}\n")

    participants = load_sweepstake()
    standings = get_all_standings()
    prizes = calculate_prizes(participants, standings)
    plain, html = build_report(prizes, standings)

    # Save HTML report as artifact
    os.makedirs("reports", exist_ok=True)
    report_path = f"reports/report_{datetime.now(timezone.utc).strftime('%Y-%m-%d')}.html"
    with open(report_path, "w") as f:
        f.write(html)
    print(f"📄 Report saved to {report_path}")

    # Also save latest.html for easy access
    with open("reports/latest.html", "w") as f:
        f.write(html)

    send_email(plain, html)


if __name__ == "__main__":
    main()
