import streamlit as st
import requests
import openai

# Set up page layout
st.set_page_config(page_title="Cas Boys BBall AI Coach", page_icon="🏀")
st.title("🏀 Fantasy Basketball AI Coach")

# Your Sleeper Information
SLEEPER_USERNAME = "airballartist"
LEAGUE_ID = "1346846297000267776"
USER_ID = "1412647306305527808"

# Optional OpenAI API Key input (or set in secrets)
api_key = st.text_input("Enter OpenAI API Key:", type="password")

@st.cache_data(ttl=86400)
def load_all_players():
    """Fetch and cache NBA player database from Sleeper"""
    url = "https://api.sleeper.app/v1/players/nba"
    res = requests.get(url)
    return res.json() if res.status_code == 200 else {}

if st.button("Fetch My Roster Data"):
    with st.spinner("Connecting to Sleeper API..."):
        all_players = load_all_players()
        rosters = requests.get(f"https://api.sleeper.app/v1/league/{LEAGUE_ID}/rosters").json()
        
        my_roster = next((r for r in rosters if r['owner_id'] == USER_ID), None)
        
        if my_roster:
            starter_ids = my_roster.get("starters", [])
            player_ids = my_roster.get("players", [])
            bench_ids = [p for p in player_ids if p not in starter_ids]
            
            starters_names = [all_players.get(pid, {}).get("full_name", pid) for pid in starter_ids]
            bench_names = [all_players.get(pid, {}).get("full_name", pid) for pid in bench_ids]
            
            st.write("### 📋 Your Current Roster")
            st.write(f"**Starters:** {', '.join(starters_names)}")
            st.write(f"**Bench:** {', '.join(bench_names)}")
            
            # Save to session state for the AI prompt
            st.session_state['starters'] = starters_names
            st.session_state['bench'] = bench_names

if 'starters' in st.session_state:
    st.markdown("---")
    user_question = st.text_input("Ask your AI Assistant a question:", value="Which bench players should I consider starting, or what waiver additions should I make?")
    
    if st.button("Get AI Recommendation"):
        if not api_key:
            st.error("Please enter an OpenAI API Key to generate AI answers.")
        else:
            with st.spinner("Analyzing your roster..."):
                client = openai.OpenAI(api_key=api_key)
                
                prompt = f"""
                You are a Fantasy Basketball expert assistant.
                
                League Format: Points League
                Scoring Settings: PTS = 0.5, REB = 1, AST = 1, STL = 2, BLK = 2, 3PM = 1, TO = -1, DD = 1, TD = 2.
                
                User Starters: {', '.join(st.session_state['starters'])}
                User Bench: {', '.join(st.session_state['bench'])}
                
                User Request: {user_question}
                
                Provide a clear, strategic recommendation optimized for Fantasy Basketball points scoring.
                """
                
                response = client.chat.completions.create(
                    model="gpt-4o-mini",
                    messages=[{"role": "user", "content": prompt}]
                )
                
                st.write("### 🤖 AI Coach Advice:")
                st.write(response.choices[0].message.content)
