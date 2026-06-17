import streamlit as st
from duckduckgo_search import DDGS
from supabase import create_client, Client
import os
from datetime import datetime
import json

SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_KEY = os.environ.get("SUPABASE_ANON_KEY")

@st.cache_resource
def get_supabase() -> Client:
    return create_client(SUPABASE_URL, SUPABASE_KEY)

supabase = get_supabase()

def init_session_state():
    if "current_session_id" not in st.session_state:
        sessions = supabase.table("chat_sessions").select("*").order("updated_at", desc=True).limit(1).execute()
        if sessions.data:
            st.session_state.current_session_id = sessions.data[0]["id"]
            st.session_state.messages = load_messages(sessions.data[0]["id"])
        else:
            new_session = supabase.table("chat_sessions").insert({"title": "New Chat"}).execute()
            st.session_state.current_session_id = new_session.data[0]["id"]
            st.session_state.messages = []
    if "messages" not in st.session_state:
        st.session_state.messages = []

def load_messages(session_id: str):
    result = supabase.table("chat_messages").select("*").eq("session_id", session_id).order("created_at").execute()
    return result.data if result.data else []

def search_and_cache(query: str):
    cached = supabase.table("cached_searches").select("*").eq("query", query.lower()).execute()
    if cached.data:
        return cached.data[0]["answer"], cached.data[0]["sources"]

    with DDGS() as ddgs:
        results = list(ddgs.text(query, max_results=5))

    if results:
        answer_parts = []
        sources = []
        for r in results:
            answer_parts.append(f"**{r.get('title', 'Source')}:** {r.get('body', '')}")
            sources.append({"title": r.get("title", ""), "href": r.get("href", "")})
        answer = "\n\n".join(answer_parts)

        supabase.table("cached_searches").insert({
            "query": query.lower(),
            "answer": answer,
            "sources": sources
        }).execute()
        return answer, sources

    return "I couldn't find any relevant information.", []

def create_new_chat():
    new_session = supabase.table("chat_sessions").insert({"title": "New Chat"}).execute()
    st.session_state.current_session_id = new_session.data[0]["id"]
    st.session_state.messages = []

def delete_chat(session_id: str):
    supabase.table("chat_sessions").delete().eq("id", session_id).execute()
    if st.session_state.current_session_id == session_id:
        sessions = supabase.table("chat_sessions").select("*").order("updated_at", desc=True).limit(1).execute()
        if sessions.data:
            st.session_state.current_session_id = sessions.data[0]["id"]
            st.session_state.messages = load_messages(sessions.data[0]["id"])
        else:
            create_new_chat()

def update_session_title(session_id: str, first_message: str):
    title = first_message[:50] + "..." if len(first_message) > 50 else first_message
    supabase.table("chat_sessions").update({"title": title, "updated_at": datetime.utcnow().isoformat()}).eq("id", session_id).execute()

def save_message(session_id: str, role: str, content: str):
    supabase.table("chat_messages").insert({
        "session_id": session_id,
        "role": role,
        "content": content
    }).execute()

def main():
    st.set_page_config(page_title="AI Assistant", page_icon=":robot_face:", layout="wide")

    st.markdown("""
    <style>
    .stApp {
        background: linear-gradient(135deg, #f5f7fa 0%, #e4e8ec 100%);
    }
    .main-header {
        background: linear-gradient(90deg, #1a1a2e 0%, #16213e 100%);
        padding: 1.5rem;
        border-radius: 0 0 1rem 1rem;
        margin-bottom: 1rem;
        box-shadow: 0 4px 6px rgba(0,0,0,0.1);
    }
    .main-header h1 {
        color: white;
        margin: 0;
        font-weight: 600;
    }
    .main-header p {
        color: #a0aec0;
        margin: 0.5rem 0 0;
    }
    .chat-container {
        background: white;
        border-radius: 1rem;
        padding: 1.5rem;
        box-shadow: 0 2px 10px rgba(0,0,0,0.05);
        margin-bottom: 1rem;
    }
    .user-message {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        color: white;
        padding: 1rem 1.25rem;
        border-radius: 1.25rem 1.25rem 0.25rem 1.25rem;
        margin: 0.5rem 0;
        display: inline-block;
        max-width: 80%;
        margin-left: auto;
        box-shadow: 0 2px 8px rgba(102,126,234,0.3);
    }
    .assistant-message {
        background: #f7fafc;
        color: #2d3748;
        padding: 1rem 1.25rem;
        border-radius: 1.25rem 1.25rem 1.25rem 0.25rem;
        margin: 0.5rem 0;
        display: inline-block;
        max-width: 80%;
        border: 1px solid #e2e8f0;
    }
    .sidebar .sidebar-content {
        background: #1a1a2e;
    }
    .stButton>button {
        background: linear-gradient(135deg, #1a1a2e 0%, #16213e 100%);
        color: white;
        border: none;
        border-radius: 0.75rem;
        padding: 0.75rem 1.5rem;
        font-weight: 500;
        transition: all 0.3s ease;
    }
    .stButton>button:hover {
        transform: translateY(-2px);
        box-shadow: 0 4px 12px rgba(26,26,46,0.4);
    }
    .chat-history-item {
        background: rgba(255,255,255,0.1);
        border-radius: 0.5rem;
        padding: 0.75rem;
        margin: 0.5rem 0;
        cursor: pointer;
        transition: all 0.2s ease;
    }
    .chat-history-item:hover {
        background: rgba(255,255,255,0.2);
    }
    .source-link {
        display: inline-block;
        background: #edf2f7;
        color: #4a5568;
        padding: 0.25rem 0.75rem;
        border-radius: 1rem;
        margin: 0.25rem;
        font-size: 0.85rem;
        text-decoration: none;
    }
    .source-link:hover {
        background: #e2e8f0;
    }
    div[data-testid="stSidebar"] {
        background: linear-gradient(180deg, #1a1a2e 0%, #16213e 100%);
    }
    div[data-testid="stSidebar"] [data-testid="stMarkdownContainer"] p {
        color: white;
    }
    .new-chat-btn button {
        width: 100%;
    }
    </style>
    """, unsafe_allow_html=True)

    init_session_state()

    with st.sidebar:
        st.markdown("<h2 style='color: white; margin-bottom: 1rem;'>AI Assistant</h2>", unsafe_allow_html=True)

        if st.button("New Chat", key="new_chat_button", use_container_width=True):
            create_new_chat()
            st.rerun()

        st.markdown("---")
        st.markdown("<h3 style='color: #a0aec0; font-size: 0.9rem;'>Chat History</h3>", unsafe_allow_html=True)

        sessions = supabase.table("chat_sessions").select("*").order("updated_at", desc=True).limit(20).execute()

        for session in sessions.data if sessions.data else []:
            col1, col2 = st.columns([4, 1])
            with col1:
                if st.button(session["title"], key=f"select_{session['id']}", use_container_width=True):
                    st.session_state.current_session_id = session["id"]
                    st.session_state.messages = load_messages(session["id"])
                    st.rerun()
            with col2:
                if st.button("X", key=f"delete_{session['id']}", help="Delete chat"):
                    delete_chat(session["id"])
                    st.rerun()

    st.markdown("""
    <div class="main-header">
        <h1>AI Assistant</h1>
        <p>Ask me anything! I'll search the internet if needed.</p>
    </div>
    """, unsafe_allow_html=True)

    chat_container = st.container()

    with chat_container:
        if st.session_state.messages:
            for msg in st.session_state.messages:
                if msg["role"] == "user":
                    st.markdown(f"""
                    <div style="text-align: right;">
                        <div class="user-message">{msg["content"]}</div>
                    </div>
                    """, unsafe_allow_html=True)
                else:
                    st.markdown(f"""
                    <div style="text-align: left;">
                        <div class="assistant-message">{msg["content"]}</div>
                    </div>
                    """, unsafe_allow_html=True)
        else:
            st.markdown("""
            <div style="text-align: center; padding: 3rem; color: #718096;">
                <h3>Welcome to AI Assistant!</h3>
                <p>Ask me any question and I'll help you find the answer.</p>
            </div>
            """, unsafe_allow_html=True)

    with st.container():
        st.markdown("<div style='height: 1rem;'></div>", unsafe_allow_html=True)
        col1, col2 = st.columns([6, 1])
        with col1:
            user_input = st.text_input(
                "Ask a question...",
                key="chat_input",
                placeholder="Type your question here...",
                label_visibility="collapsed"
            )
        with col2:
            send_button = st.button("Send", type="primary", use_container_width=True)

        if (send_button or user_input) and user_input.strip():
            with st.spinner("Searching for answers..."):
                save_message(st.session_state.current_session_id, "user", user_input)
                st.session_state.messages.append({"role": "user", "content": user_input})

                if len(st.session_state.messages) == 1:
                    update_session_title(st.session_state.current_session_id, user_input)

                answer, sources = search_and_cache(user_input)

                formatted_answer = answer
                if sources:
                    source_links = "\n\n**Sources:**\n"
                    for s in sources:
                        if s.get("href"):
                            source_links += f"[{s['title']}]({s['href']})  "
                    formatted_answer += source_links

                save_message(st.session_state.current_session_id, "assistant", formatted_answer)
                st.session_state.messages.append({"role": "assistant", "content": formatted_answer})

                st.rerun()

if __name__ == "__main__":
    main()
