"""
Shared visual theme for the nursing sim app.
Call inject_theme() at the top of any Streamlit page.
"""

import streamlit as st

THEME_CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&family=Cormorant+Garamond:wght@500;600;700&display=swap');

:root {
    --bg:               #F5F1E8;
    --bg-soft:          #EFE7DA;
    --bg-surface:       #E8E1D3;
    --bg-card:          #FCFAF5;
    --bg-card-hover:    #F4EEE3;

    --border:           #D8CCB8;
    --border-strong:    #CDBB9C;

    --sidebar-bg:       #E3D9C8;
    --sidebar-active:   #D9CCB8;

    --accent:           #A86248;
    --accent-dark:      #8F533D;
    --accent-soft:      rgba(168, 98, 72, 0.12);

    --sage:             #4E5A47;
    --sage-soft:        #6B7562;

    --text-primary:     #2F352D;
    --text-secondary:   #586055;
    --text-muted:       #8F887D;

    --severity-critical:#A54C44;
    --severity-high:    #C67B4E;
    --severity-medium:  #C89B42;
    --severity-low:     #6D7C62;

    --shadow-soft:      0 6px 20px rgba(89, 72, 52, 0.05);
    --shadow-hover:     0 10px 28px rgba(89, 72, 52, 0.09);
}

/* ── Base ───────────────────────────────────────────────────────────── */
html, body, [data-testid="stAppViewContainer"], [data-testid="stApp"] {
    background-color: var(--bg) !important;
    font-family: 'Inter', sans-serif !important;
    color: var(--text-primary) !important;
}

[data-testid="stMain"] {
    background-color: var(--bg) !important;
}

section.main > div {
    padding-top: 0 !important;
}

.main .block-container {
    background-color: var(--bg) !important;
    padding-top: 0.2rem !important;
    padding-bottom: 1.5rem !important;
    padding-left: 2.2rem !important;
    padding-right: 2.2rem !important;
    max-width: 1400px !important;
}

/* ── Sidebar ────────────────────────────────────────────────────────── */
[data-testid="stSidebar"] {
    background:
        linear-gradient(180deg, rgba(255,255,255,0.18), rgba(255,255,255,0.04)),
        var(--sidebar-bg) !important;
    border-right: 1px solid var(--border) !important;
}

[data-testid="stSidebar"] * {
    color: var(--text-primary) !important;
}

[data-testid="stSidebar"] .stMarkdown p {
    color: var(--text-secondary) !important;
    font-size: 0.94rem !important;
    line-height: 1.45 !important;
}

[data-testid="stSidebarNavItems"] {
    padding-top: 0.35rem !important;
}

[data-testid="stSidebarNavItems"] a {
    border-radius: 14px !important;
    color: var(--text-secondary) !important;
    font-size: 1rem !important;
    font-weight: 700 !important;
    padding: 0.62rem 0.9rem !important;
    transition: all 0.18s ease !important;
    border: 1px solid transparent !important;
}

[data-testid="stSidebarNavItems"] a[aria-current="page"] {
    background-color: var(--sidebar-active) !important;
    color: var(--text-primary) !important;
    border-color: var(--border-strong) !important;
    box-shadow: inset 3px 0 0 var(--accent) !important;
}

[data-testid="stSidebarNavItems"] a:hover {
    background-color: rgba(255,255,255,0.3) !important;
    color: var(--text-primary) !important;
    border-color: var(--border) !important;
}

/* ── Typography ─────────────────────────────────────────────────────── */
h1 {
    font-family: 'Cormorant Garamond', serif !important;
    font-size: 2.75rem !important;
    line-height: 1.02 !important;
    font-weight: 600 !important;
    color: var(--text-primary) !important;
    letter-spacing: -0.02em !important;
    margin-top: 0 !important;
    margin-bottom: 0.18rem !important;
}

h2 {
    font-family: 'Inter', sans-serif !important;
    font-size: 1.8rem !important;
    font-weight: 800 !important;
    color: var(--text-primary) !important;
    letter-spacing: -0.02em !important;
    margin-top: 1rem !important;
    margin-bottom: 0.45rem !important;
}

h3, h4 {
    font-family: 'Inter', sans-serif !important;
    font-weight: 700 !important;
    color: var(--text-primary) !important;
}

p, li, span, label {
    color: var(--text-secondary) !important;
}

small, .stCaption, [data-testid="stCaptionContainer"] p {
    color: var(--text-muted) !important;
    font-size: 0.86rem !important;
}

/* ── Reusable custom text styles ────────────────────────────────────── */
.case-eyebrow,
.section-kicker {
    font-size: 0.78rem;
    text-transform: uppercase;
    letter-spacing: 0.12em;
    font-weight: 800;
    color: var(--accent);
    margin-bottom: 0.28rem;
}

.case-title {
    font-family: 'Cormorant Garamond', serif;
    font-size: 2.65rem;
    line-height: 1.0;
    font-weight: 600;
    color: var(--text-primary);
    margin: 0;
}

.case-complaint {
    margin-top: 0.45rem;
    color: var(--sage-soft);
    font-size: 1rem;
    line-height: 1.45;
    max-width: 840px;
}

.case-header-wrap {
    margin-bottom: 0.65rem;
}

.section-title {
    font-family: 'Inter', sans-serif;
    font-size: 1.9rem;
    font-weight: 800;
    color: var(--text-primary);
    margin-bottom: 0.65rem;
    letter-spacing: -0.02em;
}

/* ── Panels / callouts ──────────────────────────────────────────────── */
.feature-panel {
    background: var(--bg-card);
    border: 1px solid var(--border-strong);
    border-radius: 20px;
    padding: 1.2rem 1.35rem;
    box-shadow: 0 8px 24px rgba(89, 72, 52, 0.06);
}

.diagnosis-callout {
    background: #F8F2EA;
    border: 1px solid var(--border);
    border-left: 4px solid var(--accent);
    border-radius: 14px;
    padding: 0.95rem 1rem;
    margin-bottom: 1rem;
}

.diagnosis-label {
    font-size: 0.78rem;
    letter-spacing: 0.09em;
    text-transform: uppercase;
    color: var(--accent);
    font-weight: 800;
}

.diagnosis-text {
    display: block;
    margin-top: 0.2rem;
    font-size: 1.08rem;
    color: var(--text-primary);
    font-weight: 600;
}

/* ── Buttons ────────────────────────────────────────────────────────── */
.stButton > button {
    background: var(--bg-card) !important;
    border: 1px solid var(--border-strong) !important;
    border-radius: 12px !important;
    color: var(--text-primary) !important;
    font-family: 'Inter', sans-serif !important;
    font-weight: 700 !important;
    font-size: 0.96rem !important;
    transition: all 0.16s ease !important;
    padding: 0.62rem 1.05rem !important;
    box-shadow: none !important;
}

.stButton > button:hover {
    background: var(--bg-card-hover) !important;
    border-color: var(--accent) !important;
    color: var(--accent-dark) !important;
}

.stButton > button[kind="secondary"] {
    border-color: var(--severity-critical) !important;
    color: var(--severity-critical) !important;
}

.stButton > button[kind="secondary"]:hover {
    background: rgba(165, 76, 68, 0.08) !important;
}

/* ── Inputs ─────────────────────────────────────────────────────────── */
[data-testid="stSelectbox"] > div > div {
    background: var(--bg-card) !important;
    border: 1px solid var(--border-strong) !important;
    border-radius: 14px !important;
    color: var(--text-primary) !important;
    min-height: 3rem !important;
    box-shadow: var(--shadow-soft) !important;
}

[data-testid="stSelectbox"] > div > div:focus-within {
    border-color: var(--accent) !important;
    box-shadow: 0 0 0 3px var(--accent-soft) !important;
}

[data-testid="stTextInput"] > div > div > input {
    background: var(--bg-card) !important;
    border: 1.5px solid var(--border-strong) !important;
    border-radius: 14px !important;
    color: var(--text-primary) !important;
    font-family: 'Inter', sans-serif !important;
    font-size: 0.95rem !important;
    padding: 0.6rem 0.85rem !important;
    box-shadow: var(--shadow-soft) !important;
    transition: all 0.15s ease !important;
}

[data-testid="stTextInput"] input::placeholder {
    color: var(--text-muted) !important;
    opacity: 0.82 !important;
}

[data-testid="stTextInput"] > div > div > input:hover {
    border-color: var(--accent) !important;
    background: var(--bg-card-hover) !important;
}

[data-testid="stTextInput"] > div > div > input:focus {
    border-color: var(--accent) !important;
    box-shadow: 0 0 0 3px var(--accent-soft) !important;
    background: var(--bg-card) !important;
}

label[data-testid="stWidgetLabel"] p {
    color: var(--text-primary) !important;
    font-weight: 700 !important;
    font-size: 0.95rem !important;
}

/* ── Generic bordered containers ────────────────────────────────────── */
[data-testid="stVerticalBlockBorderWrapper"] {
    background: var(--bg-card) !important;
    border: 1px solid var(--border) !important;
    border-radius: 18px !important;
    transition: all 0.18s ease !important;
    overflow: hidden !important;
    box-shadow: 0 6px 20px rgba(89, 72, 52, 0.05) !important;
}

[data-testid="stVerticalBlockBorderWrapper"]:hover {
    border-color: var(--border-strong) !important;
    background: var(--bg-card-hover) !important;
    box-shadow: var(--shadow-hover) !important;
    transform: translateY(-1px);
}

/* ── Metrics ────────────────────────────────────────────────────────── */
[data-testid="stMetric"] {
    background: var(--bg-card) !important;
    border: 1px solid var(--border-strong) !important;
    border-radius: 18px !important;
    padding: 1rem 1.2rem !important;
    box-shadow: 0 8px 24px rgba(89, 72, 52, 0.08) !important;
}

[data-testid="stMetricLabel"] {
    font-size: 0.76rem !important;
    font-weight: 800 !important;
    text-transform: uppercase !important;
    letter-spacing: 0.1em !important;
    color: var(--text-secondary) !important;
}

[data-testid="stMetricValue"] {
    font-family: 'Cormorant Garamond', serif !important;
    font-size: 2rem !important;
    color: var(--text-primary) !important;
}

/* ── Chat ───────────────────────────────────────────────────────────── */
[data-testid="stChatMessage"] {
    background: var(--bg-card) !important;
    border: 1px solid var(--border) !important;
    border-radius: 16px !important;
    margin-bottom: 0.65rem !important;
    padding: 0.85rem 1rem !important;
    box-shadow: var(--shadow-soft) !important;
}

[data-testid="stChatMessage"]:has([data-testid="stChatMessageAvatarUser"]) {
    border-left: 4px solid var(--sage) !important;
    background: #F7F3EB !important;
}

[data-testid="stChatMessage"]:has([data-testid="stChatMessageAvatarAssistant"]) {
    border-left: 4px solid var(--accent) !important;
    background: #FCF8F3 !important;
}

[data-testid="stChatInputContainer"] {
    background: var(--bg-card) !important;
    border: 1px solid var(--border) !important;
    border-radius: 14px !important;
    box-shadow: var(--shadow-soft) !important;
}

[data-testid="stChatInputContainer"]:focus-within {
    border-color: var(--accent) !important;
    box-shadow: 0 0 0 3px var(--accent-soft) !important;
}

[data-testid="stChatInput"] {
    background: transparent !important;
    color: var(--text-primary) !important;
    font-family: 'Inter', sans-serif !important;
}

/* ── Expander / alerts ──────────────────────────────────────────────── */
[data-testid="stExpander"] {
    background: var(--bg-card) !important;
    border: 1px solid var(--border-strong) !important;
    border-radius: 16px !important;
    box-shadow: 0 4px 16px rgba(89, 72, 52, 0.05) !important;
}

[data-testid="stExpander"] summary {
    color: var(--text-primary) !important;
    font-weight: 700 !important;
}

[data-testid="stAlert"] {
    background: #F2EDD8 !important;
    border-radius: 14px !important;
    border: 1px solid var(--border-strong) !important;
    color: var(--text-primary) !important;
}

hr {
    border-color: var(--border) !important;
    opacity: 0.85 !important;
    margin-top: 0.9rem !important;
    margin-bottom: 1rem !important;
}

/* ── Progress ───────────────────────────────────────────────────────── */
[data-testid="stProgress"] > div {
    background: #E3DACB !important;
    border-radius: 999px !important;
}
[data-testid="stProgress"] > div > div {
    background: linear-gradient(90deg, var(--sage), var(--accent)) !important;
    border-radius: 999px !important;
}

/* ── Misc ───────────────────────────────────────────────────────────── */
p[style*="text-align:center"] {
    color: var(--text-secondary) !important;
}

::-webkit-scrollbar { width: 8px; height: 8px; }
::-webkit-scrollbar-track { background: var(--bg-soft); }
::-webkit-scrollbar-thumb {
    background: #C9BEAD;
    border-radius: 999px;
}
::-webkit-scrollbar-thumb:hover {
    background: #B5A792;
}

header[data-testid="stHeader"] {
    background: transparent !important;
}

div[data-testid="stToolbar"] {
    right: 1rem !important;
}

.stMarkdown p {
    line-height: 1.55 !important;
    max-width: 900px;
}
</style>
"""

def inject_theme():
    st.markdown(THEME_CSS, unsafe_allow_html=True)