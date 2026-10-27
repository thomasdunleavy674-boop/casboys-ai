import streamlit as st
import requests
from google import genai

# --- Page Configuration ---
st.set_page_config(
    page_title="Fantasy Basketball AI Assistant",
    page_icon="🏀",
    layout="wide"
)

# Initialize Gemini Client (make sure your API key is in st.secrets)
client = genai.Client(api_key=st.secrets["GEMINI_API_KEY"])

# ==========================================
# 1. CACHED SLEEPER API FUNCTIONS (Speed Boost)
# ==========================================
@st.cache_data(ttl=600)  # Caches data for 10 minutes to prevent laggy reruns
def fetch_sleeper_league_data(league_id):
    """Fetches league details, rosters, and users from Sleeper in one go."""
    base_url = f"https://api.sleeper.app/v1/league/{league_id}"
    
    league_resp = requests.get(base_url).json()
    rosters_resp = requests.get(f"{base_url}/rosters").json()
    users_resp = requests.get(f"{base_url}/users").json()
    
    return {
        "league": league_resp,
        "rosters": rosters_resp,
        "users": users_resp
    }

# ==========================================
# 2. SIDEBAR CONFIGURATION
# ==========================================
st.sidebar.title("⚙️ League Settings")
league_id_input = st.sidebar.text_input(
    "Sleeper League ID", 
    value="123456789012345678"  # Default or placeholder
)

# Load data only if league ID is provided
league_data = None
if league_id_input:
    with st.spinner("Loading league context..."):
        try:
            league_data = fetch_sleeper_league_data(league_id_input)
            st.sidebar.success("League data loaded successfully!")
        except Exception as e:
            st.sidebar.error("Could not load league. Check ID.")

# ==========================================
# 3. CHAT INTERFACE & STATE MANAGEMENT
# ==========================================
st.title("🏀 Fantasy Basketball AI Hub")

if "messages" not in st.session_state:
    st.session_state.messages = []

# Display existing chat messages
for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

# User chat input
if prompt := st.chat_input("Ask about your roster, match projections, or waiver wire..."):
    # Append user message
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    # Generate assistant response
    with st.chat_message("assistant"):
        # Build system context using fetched Sleeper data if available
        system_context = "You are an expert fantasy basketball assistant."
        if league_data:
            system_context += f" Current league info: {league_data['league'].get('name', 'League')}."

        # ==========================================
        # 4. CHAT HISTORY TRIMMING (Speed Boost)
        # ==========================================
        # Keep only the last 6 messages so prompt payload doesn't bloat and slow down
        MAX_HISTORY = 6
        recent_history = st.session_state.messages[-MAX_HISTORY:]
        
        formatted_contents = [{"role": m["role"], "parts": [m["content"]]} for m in recent_history]

        try:
            # ==========================================
            # 5. STREAMING RESPONSE (Speed Boost)
            # ==========================================
            response_stream = client.models.generate_content_stream(
                model="gemini-2.5-flash", # Fast model choice for low latency
                contents=formatted_contents,
                config={
                    "system_instruction": system_context
                }
            )

            # Stream response directly to UI
            ai_response = st.write_stream(chunk.text for chunk in response_stream)
            
            # Save assistant response to state
            st.session_state.messages.append({"role": "model", "content": ai_response})

        except Exception as e:
            st.setError(f"An error occurred: {e}")
