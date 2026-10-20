import streamlit as st
import requests
import google.generativeai as genai

# Page Configuration
st.set_page_config(page_title="Cas Boys BBall AI Coach", page_icon="🏀")
st.title("🏀 Fantasy Basketball AI Chat Coach")

# Sleeper Info
LEAGUE_ID = "1346846297000267776"
USER_ID = "1412647306305527808"

# Retrieve API key automatically from Streamlit secrets
api_key = st.secrets.get("GEMINI_API_KEY", None)

@st.cache_data(ttl=86400)
def load_all_players():
    """Fetch and cache NBA player database"""
    url = "https://api.sleeper.app/v1/players/nba"
    res = requests.get(url)
    return res.json() if res.status_code == 200 else {}

@st.cache_data(ttl=3600)
def fetch_roster():
    """Fetch user starting lineup and bench"""
    all_players = load_all_players()
    rosters = requests.get(f"https://api.sleeper.app/v1/league/{LEAGUE_ID}/rosters").json()
    my_roster = next((r for r in rosters if r['owner_id'] == USER_ID), None)
    
    if my_roster:
        starter_ids = my_roster.get("starters", [])
        player_ids = my_roster.get("players", [])
        bench_ids = [p for p in player_ids if p not in starter_ids]
        
        starters = [all_players.get(pid, {}).get("full_name", pid) for pid in starter_ids]
        bench = [all_players.get(pid, {}).get("full_name", pid) for pid in bench_ids]
        return starters, bench
    return [], []

# Fetch roster details
starters, bench = fetch_roster()

# Display current roster in a collapsed section
with st.expander("📋 View My Sleeper Roster", expanded=False):
    st.write(f"**Starters:** {', '.join(starters)}")
    st.write(f"**Bench:** {', '.join(bench)}")

# 1. Initialize message history in memory if not already present
if "messages" not in st.session_state:
    st.session_state.messages = [
        {"role": "assistant", "content": "Hey! I'm your Fantasy Basketball AI Coach. Ask me anything about your roster, waiver wire pickups, or starting lineups!"}
    ]

# 2. Render existing chat messages on screen
for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.write(message["content"])

# 3. Sticky Chat Input bar at the bottom
if user_prompt := st.chat_input("Type your question here..."):
    # Display the user's message immediately
    with st.chat_message("user"):
        st.write(user_prompt)
    
    # Add user message to history
    st.session_state.messages.append({"role": "user", "content": user_prompt})

    # Generate response using AI
    if not api_key:
        st.error("API Key missing! Please add GEMINI_API_KEY in Streamlit app secrets.")
    else:
        with st.chat_message("assistant"):
            with st.spinner("Thinking..."):
                try:
                    genai.configure(api_key=api_key)
                    model = genai.GenerativeModel("gemini-3.8-flash")
                    
                    # Construct system context with roster info and chat history
                    system_context = f"""
                    You are a Fantasy Basketball expert assistant.
                    
                    League Format: Points League
                    Scoring Settings: PTS = 0.5, REB = 1, AST = 1, STL = 2, BLK = 2, 3PM = 1, TO = -1, DD = 1, TD = 2.
                    
                    User Starters: {', '.join(starters)}
                    User Bench: {', '.join(bench)}
                    """
                    
                    # Prepare conversation history for Gemini
                    conversation = system_context + "\n\nConversation History:\n"
                    for msg in st.session_state.messages:
                        conversation += f"{msg['role'].capitalize()}: {msg['content']}\n"
                    
                    response = model.generate_content(conversation)
                    bot_reply = response.text
                    
                    # Display response & store in history
                    st.write(bot_reply)
                    st.session_state.messages.append({"role": "assistant", "content": bot_reply})
                    
                except Exception as e:
                    st.error(f"Error generating advice: {e}")
