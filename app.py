import os
import json
import uuid
from datetime import datetime
import streamlit as st
from sentence_transformers import SentenceTransformer
import chromadb
from groq import Groq

groq_client = Groq(api_key=st.secrets["GROQ_API_KEY"])
CHROMA_PATH = "chroma_db"
CHATS_FILE = "chats.json"

st.set_page_config(page_title="Aquanis", page_icon="💧", layout="wide")

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
.main-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    padding-bottom: 8px;
    border-bottom: 1px solid #dbe9f7;
    margin-bottom: 12px;
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

@st.cache_resource
def load_resources():
    model = SentenceTransformer("all-MiniLM-L6-v2")
    client = chromadb.PersistentClient(path=CHROMA_PATH)
    collection = client.get_collection("aquanis_docs")
    return model, collection

model, collection = load_resources()

# ---------- Sidebar ----------
with st.sidebar:
    st.markdown("### 💧 Aquanis")

    if st.button("+ New chat", use_container_width=True):
        new_id = str(uuid.uuid4())
        st.session_state.chats[new_id] = {
            "title": "New chat",
            "messages": [],
            "created": datetime.now().isoformat()
        }
        st.session_state.current_chat_id = new_id
        save_chats(st.session_state.chats)
        st.rerun()

    st.markdown("---")
    st.caption("Recent chats")

    for chat_id, chat in sorted(
        st.session_state.chats.items(),
        key=lambda x: x[1]["created"],
        reverse=True
    ):
        label = chat["title"] if chat["title"] else "New chat"
        if st.button(label, key=f"chat_{chat_id}", use_container_width=True):
            st.session_state.current_chat_id = chat_id
            st.rerun()

    st.markdown("---")
    st.markdown("👤 **Student**")

# ---------- Main area ----------
current_id = st.session_state.current_chat_id

if current_id is None:
    st.markdown("### 💧 Welcome to Aquanis")
    st.caption("Start a new chat to ask a question about your hydraulics course materials.")
    if st.button("+ Start new chat"):
        new_id = str(uuid.uuid4())
        st.session_state.chats[new_id] = {
            "title": "New chat",
            "messages": [],
            "created": datetime.now().isoformat()
        }
        st.session_state.current_chat_id = new_id
        save_chats(st.session_state.chats)
        st.rerun()
    st.stop()

current_chat = st.session_state.chats[current_id]

col1, col2 = st.columns([6, 1])
with col1:
    st.markdown(f"#### {current_chat['title']}")
with col2:
    if st.button("📋 Copy"):
        full_text = "\n\n".join(
            f"{m['role'].upper()}: {m['content']}" for m in current_chat["messages"]
        )
        st.code(full_text)

for msg in current_chat["messages"]:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])

question = st.chat_input("Ask a question about hydraulics...")

if question:
    current_chat["messages"].append({"role": "user", "content": question})

    if current_chat["title"] == "New chat":
        current_chat["title"] = question[:40] + ("..." if len(question) > 40 else "")

    with st.chat_message("user"):
        st.markdown(question)

    query_embedding = model.encode([question]).tolist()
    results = collection.query(query_embeddings=query_embedding, n_results=4)
    context = "\n\n".join(results["documents"][0])
    sources = list(set(r["source"] for r in results["metadatas"][0]))

    prompt = f"""You are Aquanis, a helpful assistant for hydraulics engineers and students.
Answer the question using ONLY the context below.
If the answer is not in the context, say "I don't have that information in my materials."

Context:
{context}

Question: {question}
"""
    with st.chat_message("assistant"):
        with st.spinner("Thinking..."):
            response = groq_client.chat.completions.create(
                model="llama-3.3-70b-versatile",
                messages=[{"role": "user", "content": prompt}]
            )
            answer = response.choices[0].message.content + f"\n\n📄 *Sources: {', '.join(sources)}*"
            st.markdown(answer)

    current_chat["messages"].append({"role": "assistant", "content": answer})
    save_chats(st.session_state.chats)
    st.rerun()