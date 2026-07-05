import os
import json
import uuid
from datetime import datetime
import streamlit as st
from sentence_transformers import SentenceTransformer
import chromadb
from groq import Groq

st.set_page_config(page_title="Aquanis", page_icon="💧", layout="wide")

# ---------- Require Google sign-in ----------
if not st.user.is_logged_in:
    st.markdown("### 💧 Welcome to Aquanis")
    st.caption("Sign in with your Google account to continue.")
    if st.button("Sign in with Google"):
        st.login()
    st.stop()

groq_client = Groq(api_key=st.secrets["GROQ_API_KEY"])
CHROMA_PATH = "chroma_db"
CHATS_FILE = "chats.json"

# ---------- Blue water theme ----------
st.markdown("""
<style>
[data-testid="stSidebar"] {
    background-color: #0d2b4e;
}
[data-testid="stSidebar"] * {
    color: #e6f1fb !important;
}
.stButton button {
    background-color: transparent;
    border: none;
    text-align: left;
    color: #e6f1fb;
}
.stButton button:hover {
    background-color: #16406e;
    color: white;
}
[data-testid="stChatMessage"] {
    font-size: 15px;
}
</style>
""", unsafe_allow_html=True)

# ---------- Load / save chats ----------
def load_chats():
    if os.path.exists(CHATS_FILE):
        with open(CHATS_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}

def save_chats(chats):
    with open(CHATS_FILE, "w", encoding="utf-8") as f:
        json.dump(chats, f, ensure_ascii=False, indent=2)

if "chats" not in st.session_state:
    st.session_state.chats = load_chats()

if "current_chat_id" not in st.session_state:
    if st.session_state.chats:
        st.session_state.current_chat_id = list(st.session_state.chats.keys())[0]
    else:
        st.session_state.current_chat_id = None

if "creating_new_chat" not in st.session_state:
    st.session_state.creating_new_chat = False

@st.cache_resource
def load_resources():
    model = SentenceTransformer("all-MiniLM-L6-v2")
    client = chromadb.PersistentClient(path=CHROMA_PATH)
    collection = client.get_collection("aquanis_docs")
    return model, collection

try:
    model, collection = load_resources()
except Exception as e:
    st.error(f"Failed to load resources: {e}")
    st.stop()

# ---------- Sidebar ----------
with st.sidebar:
    st.markdown("### 💧 Aquanis")

    if st.button("+ New chat", use_container_width=True):
        st.session_state.creating_new_chat = True
        st.rerun()

    if st.session_state.creating_new_chat:
        new_name = st.text_input("Chat name", placeholder="e.g. Reynolds number", key="new_chat_name")
        col_a, col_b = st.columns(2)
        with col_a:
            if st.button("Create", use_container_width=True):
                new_id = str(uuid.uuid4())
                title = new_name.strip() if new_name.strip() else "New chat"
                st.session_state.chats[new_id] = {
                    "title": title,
                    "messages": [],
                    "created": datetime.now().isoformat()
                }
                st.session_state.current_chat_id = new_id
                st.session_state.creating_new_chat = False
                save_chats(st.session_state.chats)
                st.rerun()
        with col_b:
            if st.button("Cancel", use_container_width=True):
                st.session_state.creating_new_chat = False
                st.rerun()

    st.markdown("---")
    st.caption("Recent chats")

    for chat_id, chat in sorted(
        st.session_state.chats.items(),
        key=lambda x: x[1]["created"],
        reverse=True
    ):
        label = chat["title"] if chat["title"] else "New chat"
        col1, col2 = st.columns([5, 1])
        with col1:
            if st.button(label, key=f"chat_{chat_id}", use_container_width=True):
                st.session_state.current_chat_id = chat_id
                st.rerun()
        with col2:
            if st.button("🗑️", key=f"del_{chat_id}"):
                del st.session_state.chats[chat_id]
                if st.session_state.current_chat_id == chat_id:
                    remaining = list(st.session_state.chats.keys())