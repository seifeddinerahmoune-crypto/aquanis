import traceback
import os
import json
import uuid
import base64
import io
from datetime import datetime
import streamlit as st
from sentence_transformers import SentenceTransformer
import chromadb
from groq import Groq
import fitz
from pptx import Presentation
from docx import Document
import openpyxl

st.set_page_config(page_title="Aquanis", page_icon="water", layout="wide")

TRANSLATIONS = {
    "en": {
        "app_name": "Aquanis",
        "welcome_title": "Welcome to Aquanis",
        "welcome_caption": "Sign in to save your chat history, or continue without an account.",
        "sign_in": "Sign in with Google",
        "continue_guest": "Continue without signing in",
        "guest_warning": "Guest chats are not saved and will be lost if you refresh the page.",
        "new_chat": "+ New chat",
        "chat_name_label": "Chat name",
        "chat_name_placeholder": "e.g. Reynolds number",
        "create": "Create",
        "cancel": "Cancel",
        "recent_chats": "Recent chats",
        "user_label": "User",
        "guest_label": "Guest",
        "log_out": "Log out",
        "start_new_chat_caption": "Start a new chat to ask a question about your hydraulics course materials.",
        "chat_input_placeholder": "Ask a question, or attach a file...",
        "thinking": "Thinking...",
        "sources_label": "Sources",
        "language_label": "Interface language",
        "delete": "Delete",
    },
    "fr": {
        "app_name": "Aquanis",
        "welcome_title": "Bienvenue sur Aquanis",
        "welcome_caption": "Connectez-vous pour sauvegarder vos discussions, ou continuez sans compte.",
        "sign_in": "Se connecter avec Google",
        "continue_guest": "Continuer sans se connecter",
        "guest_warning": "Les discussions invité ne sont pas sauvegardées et seront perdues si vous actualisez la page.",
        "new_chat": "+ Nouvelle discussion",
        "chat_name_label": "Nom de la discussion",
        "chat_name_placeholder": "ex: Nombre de Reynolds",
        "create": "Créer",
        "cancel": "Annuler",
        "recent_chats": "Discussions récentes",
        "user_label": "Utilisateur",
        "guest_label": "Invité",
        "log_out": "Se déconnecter",
        "start_new_chat_caption": "Démarrez une nouvelle discussion pour poser une question sur vos cours d'hydraulique.",
        "chat_input_placeholder": "Posez une question, ou joignez un fichier...",
        "thinking": "Réflexion en cours...",
        "sources_label": "Sources",
        "language_label": "Langue de l'interface",
        "delete": "Supprimer",
    },
    "ar": {
        "app_name": "Aquanis",
        "welcome_title": "مرحبا بك في Aquanis",
        "welcome_caption": "سجل الدخول لحفظ محادثاتك، أو تابع بدون حساب.",
        "sign_in": "تسجيل الدخول بجوجل",
        "continue_guest": "المتابعة بدون تسجيل الدخول",
        "guest_warning": "لا يتم حفظ محادثات الضيف وستفقد عند تحديث الصفحة.",
        "new_chat": "+ محادثة جديدة",
        "chat_name_label": "اسم المحادثة",
        "chat_name_placeholder": "مثال: عدد رينولدز",
        "create": "إنشاء",
        "cancel": "إلغاء",
        "recent_chats": "المحادثات الأخيرة",
        "user_label": "المستخدم",
        "guest_label": "ضيف",
        "log_out": "تسجيل الخروج",
        "start_new_chat_caption": "ابدأ محادثة جديدة لطرح سؤال حول مواد مقرر الهيدروليك.",
        "chat_input_placeholder": "اطرح سؤالا، أو أرفق ملفا...",
        "thinking": "جارٍ التفكير...",
        "sources_label": "المصادر",
        "language_label": "لغة الواجهة",
        "delete": "حذف",
    },
}

if "ui_lang" not in st.session_state:
    st.session_state.ui_lang = "en"

t = TRANSLATIONS[st.session_state.ui_lang]

if st.session_state.ui_lang == "ar":
    st.markdown("<style>body, .stApp { direction: rtl; }</style>", unsafe_allow_html=True)

if "guest_mode" not in st.session_state:
    st.session_state.guest_mode = False

if "guest_id" not in st.session_state:
    st.session_state.guest_id = "guest_" + str(uuid.uuid4())


def extract_text_from_pdf(file_bytes):
    doc = fitz.open(stream=file_bytes, filetype="pdf")
    return "\n".join(page.get_text() for page in doc)


def extract_text_from_pptx(file_bytes):
    prs = Presentation(io.BytesIO(file_bytes))
    parts = []
    for slide in prs.slides:
        for shape in slide.shapes:
            if hasattr(shape, "text"):
                parts.append(shape.text)
    return "\n".join(parts)


def extract_text_from_docx(file_bytes):
    doc = Document(io.BytesIO(file_bytes))
    return "\n".join(p.text for p in doc.paragraphs)


def extract_text_from_xlsx(file_bytes):
    wb = openpyxl.load_workbook(io.BytesIO(file_bytes), data_only=True)
    parts = []
    for sheet in wb.worksheets:
        for row in sheet.iter_rows(values_only=True):
            row_text = " | ".join(str(cell) for cell in row if cell is not None)
            if row_text:
                parts.append(row_text)
    return "\n".join(parts)


try:
    is_logged_in = st.user.is_logged_in

    if not is_logged_in and not st.session_state.guest_mode:
        st.markdown("### " + t["welcome_title"])
        st.caption(t["welcome_caption"])
        col1, col2 = st.columns(2)
        with col1:
            if st.button(t["sign_in"], use_container_width=True):
                st.login()
        with col2:
            if st.button(t["continue_guest"], use_container_width=True):
                st.session_state.guest_mode = True
                st.rerun()
        st.caption(t["guest_warning"])
        st.stop()

    if is_logged_in:
        user_identity = st.user.email
        display_name = st.user.name
    else:
        user_identity = st.session_state.guest_id
        display_name = t["guest_label"]

    groq_client = Groq(api_key=st.secrets["GROQ_API_KEY"])
    CHROMA_PATH = "chroma_db"
    CHATS_FILE = "chats.json"

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

    def load_all_chats():
        if os.path.exists(CHATS_FILE):
            with open(CHATS_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        return {}

    def save_all_chats(all_chats):
        with open(CHATS_FILE, "w", encoding="utf-8") as f:
            json.dump(all_chats, f, ensure_ascii=False, indent=2)

    def load_chats(user_key):
        all_chats = load_all_chats()
        return all_chats.get(user_key, {})

    def save_chats(user_key, chats):
        all_chats = load_all_chats()
        all_chats[user_key] = chats
        save_all_chats(all_chats)

    if "chats" not in st.session_state:
        if is_logged_in:
            st.session_state.chats = load_chats(user_identity)
        else:
            st.session_state.chats = {}

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

    model, collection = load_resources()

    with st.sidebar:
        st.markdown("### " + t["app_name"])

        lang_options = {"English": "en", "Français": "fr", "العربية": "ar"}
        lang_names = list(lang_options.keys())
        current_lang_name = [k for k, v in lang_options.items() if v == st.session_state.ui_lang][0]
        selected_lang_name = st.selectbox(
            t["language_label"],
            lang_names,
            index=lang_names.index(current_lang_name)
        )
        selected_lang_code = lang_options[selected_lang_name]
        if selected_lang_code != st.session_state.ui_lang:
            st.session_state.ui_lang = selected_lang_code
            st.rerun()

        if st.button(t["new_chat"], use_container_width=True):
            st.session_state.creating_new_chat = True
            st.rerun()

        if st.session_state.creating_new_chat:
            new_name = st.text_input(t["chat_name_label"], placeholder=t["chat_name_placeholder"], key="new_chat_name")
            col_a, col_b = st.columns(2)
            with col_a:
                if st.button(t["create"], use_container_width=True):
                    new_id = str(uuid.uuid4())
                    title = new_name.strip() if new_name.strip() else t["new_chat"]
                    st.session_state.chats[new_id] = {
                        "title": title,
                        "messages": [],
                        "created": datetime.now().isoformat()
                    }
                    st.session_state.current_chat_id = new_id
                    st.session_state.creating_new_chat = False
                    if is_logged_in:
                        save_chats(user_identity, st.session_state.chats)
                    st.rerun()
            with col_b:
                if st.button(t["cancel"], use_container_width=True):
                    st.session_state.creating_new_chat = False
                    st.rerun()

        st.markdown("---")
        st.caption(t["recent_chats"])

        for chat_id, chat in sorted(
            st.session_state.chats.items(),
            key=lambda x: x[1]["created"],
            reverse=True
        ):
            label = chat["title"] if chat["title"] else t["new_chat"]
            col1, col2 = st.columns([5, 1])
            with col1:
                if st.button(label, key=f"chat_{chat_id}", use_container_width=True):
                    st.session_state.current_chat_id = chat_id
                    st.rerun()
            with col2:
                if st.button("\U0001F5D1", key=f"del_{chat_id}"):
                    del st.session_state.chats[chat_id]
                    if st.session_state.current_chat_id == chat_id:
                        remaining = list(st.session_state.chats.keys())
                        st.session_state.current_chat_id = remaining[0] if remaining else None
                    if is_logged_in:
                        save_chats(user_identity, st.session_state.chats)
                    st.rerun()

        st.markdown("---")
        st.markdown(t["user_label"] + ": " + display_name)
        if is_logged_in:
            if st.button(t["log_out"]):
                st.logout()
        else:
            if st.button(t["log_out"]):
                st.session_state.guest_mode = False
                st.session_state.chats = {}
                st.session_state.current_chat_id = None
                st.rerun()

    current_id = st.session_state.current_chat_id

    if current_id is None:
        st.markdown("### " + t["welcome_title"])
        st.caption(t["start_new_chat_caption"])
        st.stop()

    current_chat = st.session_state.chats[current_id]

    st.markdown("#### " + current_chat["title"])

    for msg in current_chat["messages"]:
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])

    prompt = st.chat_input(
        t["chat_input_placeholder"],
        accept_file=True,
        file_type=["png", "jpg", "jpeg", "pdf", "docx", "pptx", "xlsx", "xls"]
    )

    if prompt:
        question = prompt.text if prompt.text else ""
        uploaded_files = prompt["files"] if prompt["files"] else []

        image_data_url = None
        extra_text_context = ""

        for f in uploaded_files:
            file_bytes = f.read()
            ext = f.name.split(".")[-1].lower()

            if ext in ["png", "jpg", "jpeg"]:
                base64_image = base64.b64encode(file_bytes).decode("utf-8")
                image_data_url = "data:" + f.type + ";base64," + base64_image
            elif ext == "pdf":
                extra_text_context += "\n\n[Content from " + f.name + "]\n" + extract_text_from_pdf(file_bytes)
            elif ext == "pptx":
                extra_text_context += "\n\n[Content from " + f.name + "]\n" + extract_text_from_pptx(file_bytes)
            elif ext == "docx":
                extra_text_context += "\n\n[Content from " + f.name + "]\n" + extract_text_from_docx(file_bytes)
            elif ext in ["xlsx", "xls"]:
                extra_text_context += "\n\n[Content from " + f.name + "]\n" + extract_text_from_xlsx(file_bytes)

        display_text = question if question else "(file attached)"
        current_chat["messages"].append({"role": "user", "content": display_text})

        with st.chat_message("user"):
            for f in uploaded_files:
                ext = f.name.split(".")[-1].lower()
                if ext in ["png", "jpg", "jpeg"]:
                    st.image(f)
                else:
                    st.markdown("📎 " + f.name)
            if question:
                st.markdown(question)

        query_embedding = model.encode([display_text]).tolist()
        results = collection.query(query_embeddings=query_embedding, n_results=4)
        context = "\n\n".join(results["documents"][0])
        sources = list(set(r["source"] for r in results["metadatas"][0]))

        system_prompt = ("You are Aquanis, a helpful assistant for hydraulics engineers and students. "
                          "Always answer in the same language the student used in their latest question. "
                          "Use the course context below to answer questions. If an image or file is attached, "
                          "analyze it and relate it to hydraulics concepts. If the answer is not available, "
                          "say so in the student's language. Use earlier conversation for follow-up questions.\n\n"
                          "Course context:\n" + context)

        if extra_text_context:
            system_prompt += "\n\nAttached file content:\n" + extra_text_context

        conversation_messages = [{"role": "system", "content": system_prompt}]

        num_messages = len(current_chat["messages"])
        for i, msg in enumerate(current_chat["messages"]):
            if i == num_messages - 1 and image_data_url:
                conversation_messages.append({
                    "role": "user",
                    "content": [
                        {"type": "text", "text": msg["content"]},
                        {"type": "image_url", "image_url": {"url": image_data_url}}
                    ]
                })
            else:
                conversation_messages.append({"role": msg["role"], "content": msg["content"]})

        model_to_use = "meta-llama/llama-4-maverick-17b-128e-instruct" if image_data_url else "llama-3.3-70b-versatile"

        with st.chat_message("assistant"):
            with st.spinner(t["thinking"]):
                response = groq_client.chat.completions.create(
                    model=model_to_use,
                    messages=conversation_messages
                )
                answer = response.choices[0].message.content + "\n\n" + t["sources_label"] + ": " + ", ".join(sources)
                st.markdown(answer)

        current_chat["messages"].append({"role": "assistant", "content": answer})
        if is_logged_in:
            save_chats(user_identity, st.session_state.chats)
        st.rerun()

except Exception as e:
    st.error("An error occurred while running Aquanis:")
    st.code(traceback.format_exc())