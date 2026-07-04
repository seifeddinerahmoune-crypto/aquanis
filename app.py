import os
import streamlit as st
from sentence_transformers import SentenceTransformer
import chromadb
from groq import Groq
from dotenv import load_dotenv

load_dotenv()
groq_client = Groq(api_key=os.getenv("GROQ_API_KEY"))

CHROMA_PATH = "chroma_db"

@st.cache_resource
def load_resources():
    model = SentenceTransformer("all-MiniLM-L6-v2")
    client = chromadb.PersistentClient(path=CHROMA_PATH)
    collection = client.get_collection("aquanis_docs")
    return model, collection

model, collection = load_resources()

st.set_page_config(page_title="Aquanis", page_icon="💧")
st.title("💧 Aquanis")
st.caption("Your hydraulics course assistant — ask me anything about your materials!")

if "messages" not in st.session_state:
    st.session_state.messages = []

for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])

if question := st.chat_input("Ask a question about hydraulics..."):
    st.session_state.messages.append({"role": "user", "content": question})
    with st.chat_message("user"):
        st.markdown(question)

    # Retrieve relevant chunks
    query_embedding = model.encode([question]).tolist()
    results = collection.query(query_embeddings=query_embedding, n_results=4)
    context = "\n\n".join(results["documents"][0])
    sources = list(set(r["source"] for r in results["metadatas"][0]))

    # Ask Groq
    prompt = f"""You are Aquanis, a helpful assistant for hydraulics students.
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

    st.session_state.messages.append({"role": "assistant", "content": answer})