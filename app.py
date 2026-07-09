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

st.set_page_config(page_title="Aquanis", page_icon="💧", layout="wide")

# ---------- Design tokens ----------
BG = "#03111e"
FG = "#e7f0f5"
CARD = "#0a1c2c"
PRIMARY = "#3dbfe2"
PRIMARY_FG = "#010e1d"
SECONDARY = "#112b40"
MUTED_FG = "#879ca8"
ACCENT = "#10364e"
BORDER = "rgba(119, 184, 215, 0.15)"
SIDEBAR = "#051729"
SIDEBAR_ACCENT = "#0f283d"

TRANSLATIONS = {
    "en": {
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
        "no_chats": "No conversations yet",
        "user_label": "User",
        "guest_label": "Guest",
        "log_out": "Log out",
        "app_title": "New chat",
        "welcome_sub": "Your AI companion for fluid mechanics and hydraulic engineering. Ask about pipe flow, pumps, open channels, hydrology, and more.",
        "chat_input_placeholder": "Ask a question about hydraulics, or attach a file...",
        "thinking": "Aquanis is thinking...",
        "sources_label": "Sources",
        "language_label": "Interface language",
        "footer_note": "Aquanis can make mistakes. Verify critical hydraulic calculations.",
        "suggestions": [
            "Explain the Bernoulli equation with a practical example",
            "How do I size a centrifugal pump for a pipeline?",
            "Derive the Darcy-Weisbach head loss formula",
            "What causes water hammer and how do I prevent it?",
        ],
    },
    "fr": {
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
        "no_chats": "Aucune conversation pour le moment",
        "user_label": "Utilisateur",
        "guest_label": "Invité",
        "log_out": "Se déconnecter",
        "app_title": "Nouvelle discussion",
        "welcome_sub": "Votre assistant IA pour la mécanique des fluides et l'hydraulique. Posez vos questions sur les écoulements, les pompes, les canaux ouverts, l'hydrologie, et plus encore.",
        "chat_input_placeholder": "Posez une question, ou joignez un fichier...",
        "thinking": "Aquanis réfléchit...",
        "sources_label": "Sources",
        "language_label": "Langue de l'interface",
        "footer_note": "Aquanis peut faire des erreurs. Vérifiez les calculs hydrauliques critiques.",
        "suggestions": [
            "Expliquer l'équation de Bernoulli avec un exemple pratique",
            "Comment dimensionner une pompe centrifuge pour une conduite ?",
            "Démontrer la formule de perte de charge de Darcy-Weisbach",
            "Quelles sont les causes du coup de bélier et comment l'éviter ?",
        ],
    },
    "ar": {
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
        "no_chats": "لا توجد محادثات بعد",
        "user_label": "المستخدم",
        "guest_label": "ضيف",
        "log_out": "تسجيل الخروج",
        "app_title": "محادثة جديدة",
        "welcome_sub": "مساعدك الذكي في ميكانيكا الموائع والهندسة الهيدروليكية. اسأل عن جريان الأنابيب، المضخات، القنوات المفتوحة، الهيدرولوجيا، والمزيد.",
        "chat_input_placeholder": "اطرح سؤالا، أو أرفق ملفا...",
        "thinking": "Aquanis يفكر...",
        "sources_label": "المصادر",
        "language_label": "لغة الواجهة",
        "footer_note": "قد يخطئ Aquanis. تحقق من الحسابات الهيدروليكية الهامة.",
        "suggestions": [
            "اشرح معادلة برنولي بمثال عملي",
            "كيف أحدد حجم مضخة طاردة مركزية لخط أنابيب؟",
            "اشتق معادلة فقدان الضغط دارسي-فايسباخ",
            "ما أسباب المطرقة المائية وكيف أمنعها؟",
        ],
    },
}

lang_options = {
    "English": "en",
    "Français": "fr",
    "العربية": "ar"
}

if "ui_lang" not in st.session_state:
    st.session_state.ui_lang = "en"

t = TRANSLATIONS[st.session_state.ui_lang]
is_rtl = st.session_state.ui_lang == "ar"

if "guest_mode" not in st.session_state:
    st.session_state.guest_mode = False
if "guest_id" not