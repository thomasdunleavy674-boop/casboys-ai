import streamlit as st
import requests

st.set_page_config(page_title="Team Info & Scoreboard", page_icon="📊", layout="centered")

st.markdown("""
    <style>
    .stApp {
        background: linear-gradient(to bottom, #1e3a8a 0%, #0a0e1a 45%, #000000 100%);
        background-attachment: fixed;
    }
    h1, h2, h3, p, label, .stMarkdown {
        color: #f8fafc !important;
    }
    </style>
    """, unsafe_allow_html=True)

LEAGUE_ID = "1346846297000267776"

if not st.session_state.get("active_user_id"):
    st.warning("⚠️ Please select your manager profile on the main page first!")
    st.stop()

selected_name = st.session_state.active_user_name
active_user_id = st.session_state.active_user_id

st.title("📊 Matchup & Roster Dashboard")
st.info(f"👤 Active Manager: **{selected_name}**")

@st.cache_data(ttl=86400)
def load_all_players():
    res = requests.get("https://api.sleeper.app/v1/players/nba")
    return res.json() if res.status_code == 200 else {}

@st.cache_data(ttl=3600)
def get_league_state():
    try:
        return requests.get("https://api.sleeper.app/v1/state/nba").json().get("week", 1)
    except:
        return 1

def fetch_dashboard_data():
    all_players = load_all_players()
    current_week = get_league_state()
    
    rosters_res = requests.get(f"https://api.sleeper.app/v1/league/{LEAGUE_ID}/rosters")
    if rosters_res.status_code != 200:
        return {}, {}, [], current_week, 0.0, 0.0, 0.0, 0.0
    rosters = rosters_res.json()
    my_roster = next((r for r in rosters if str(r.get('owner_id')) == str(active_user_id)), None)
    my_roster_id = my_roster['roster_id'] if my_roster else None
    
    taken = set()
    for r in rosters:
        taken.update(r.get("players", []) or [])

    matchups_res = requests.get(f"https://api.sleeper.app/v1/league/{LEAGUE_ID}/matchups/{current_week}")
    matchups = matchups_res.json() if matchups_res.status_code == 200 else []
    my_matchup = next((m for m in matchups if m.get('roster_id') == my_roster_id), None) if my_roster_id else None
    
    my_pts = float(my_matchup.get("pts", 0.0)) if my_matchup and my_matchup.get("pts") else 0.0
    my_proj = float(my_matchup.get("custom_points", 0.0)) if my_matchup and my_matchup.get("custom_points") else 0.0

    user_team = {"starters": [], "bench": []}
    if my_roster:
        starters = my_roster.get("starters", []) or []
        pts_map = my_matchup.get("players_points", {}) if my_matchup else {}
        for pid in starters:
            name = all_players.get(pid, {}).get("full_name", pid)
            score = float(pts_map.get(pid, 0.0) or 0.0)
            user_team["starters"].append(f"{name} — {score:.1f} PTS")
        bench_ids = [p for p in (my_roster.get("players", []) or []) if p not in starters]
        user_team["bench"] = [all_players.get(pid, {}).get("full_name", pid) for pid in bench_ids]

    opponent_team = {"starters": [], "bench": []}
    opp_pts, opp_proj = 0.0, 0.0
    if my_matchup:
        opp_matchup = next((m for m in matchups if m.get("matchup_id") == my_matchup.get("matchup_id") and m.get('roster_id') != my_roster_id), None)
        if opp_matchup:
            opp_pts = float(opp_matchup.get("pts", 0.0) or 0.0)
            opp_pts_map = opp_matchup.get("players_points", {}) or {}
            opp_proj = sum(float(v) for v in opp_pts_map.values() if v is not None)
            for pid in (opp_matchup.get("starters", []) or []):
                name = all_players.get(pid, {}).get("full_name", pid)
                score = float(opp_pts_map.get(pid, 0.0) or 0.0)
                opponent_team["starters"].append(f"{name} — {score:.1f} PTS")
            opp_bench = [p for p in (opp_matchup.get("players", []) or []) if p not in opp_matchup.get("starters", [])]
            opponent_team["bench"] = [all_players.get(pid, {}).get("full_name", pid) for pid in opp_bench]

    top_fa = []
    trending = requests.get("https://api.sleeper.app/v1/players/nba/trending/add")
    if trending.status_code == 200:
        for item in trending.json():
            pid = item.get("player_id")
            if pid not in taken and pid in all_players:
                p = all_players[pid]
                top_fa.append(f"{p.get('full_name')} ({p.get('position')} - {p.get('team')})")
                if len(top_fa) >= 15: break

    return user_team, opponent_team, top_fa, current_week, my_pts, my_proj, opp_pts, opp_proj

user_team, opponent_team, top_fa, wk, my_pts, my_proj, opp_pts, opp_proj = fetch_dashboard_data()

st.write(f"### 📅 Week {wk} Matchup Scoreboard")
c1, c2 = st.columns(2)
c1.metric(label=f"🟢 {selected_name} (You)", value=f"{my_pts:.1f} PTS", delta=f"Proj: {my_proj:.1f}")
c2.metric(label="⚔️ Opponent", value=f"{opp_pts:.1f} PTS", delta=f"Proj: {opp_proj:.1f}")

st.markdown("---")

col1, col2 = st.columns(2)
with col1:
    with st.expander(f"🏀 {selected_name}'s Starters", expanded=True):
        for s in user_team['starters']:
            st.write(f"- {s}")
    with st.expander("Bench", expanded=False):
        st.write(", ".join(user_team['bench']) if user_team['bench'] else "None")

with col2:
    with st.expander("⚔️ Opponent Starters", expanded=True):
        for os in opponent_team['starters']:
            st.write(f"- {os}")
    with st.expander("Opponent Bench", expanded=False):
        st.write(", ".join(opponent_team['bench']) if opponent_team['bench'] else "None")

with st.expander("🔥 Top Trending Free Agents Available", expanded=False):
    st.write(", ".join(top_fa) if top_fa else "No trending free agents found.")
