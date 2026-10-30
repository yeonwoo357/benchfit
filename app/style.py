import streamlit as st

PALETTE = {
    "ink": "#0B0B0C",
    "muted": "#5B5B63",
    "surface": "#F7F7F9",
    "border": "#E7E7EA",
    "accent": "#2851FF",
}

VERDICT_COLORS = {
    "Below benchmark": ("#FCE4E4", "#B3261E"),
    "Within benchmark": ("#FFF4DE", "#8A5B00"),
    "Above benchmark": ("#E3F6E9", "#1E7B3C"),
    "No benchmark available": ("#F0F0F2", "#5B5B63"),
}


def inject_base_css():
    st.markdown(
        """
        <style>
        html, body, [class*="css"] {
            font-family: 'Helvetica Neue', Helvetica, Arial, sans-serif;
        }

        #MainMenu, footer, header[data-testid="stHeader"] { visibility: hidden; height: 0; }

        .block-container { padding-top: 1.5rem; max-width: 880px; }

        h1, h2, h3 { font-weight: 700 !important; letter-spacing: -0.01em; color: #0B0B0C; }

        .bf-hero { padding: 0.5rem 0 1.75rem 0; }
        .bf-eyebrow {
            font-size: 0.72rem; font-weight: 700; letter-spacing: 0.14em; text-transform: uppercase;
            color: #5B5B63; margin-bottom: 0.75rem;
        }
        .bf-title {
            font-size: 2.5rem; font-weight: 700; letter-spacing: 0.01em; text-transform: uppercase;
            color: #0B0B0C; line-height: 1.05; margin: 0;
        }
        .bf-subtitle {
            font-size: 1.02rem; color: #5B5B63; max-width: 620px; margin-top: 1rem; line-height: 1.6;
        }

        .bf-hr { border-top: 1px solid #E7E7EA; margin: 1.25rem 0 1.5rem 0; }

        .bf-card { background: #FFFFFF; border: 1px solid #E7E7EA; border-radius: 4px; padding: 1.5rem; margin-bottom: 1rem; }

        div[data-testid="stVerticalBlockBorderWrapper"] > div > div[data-testid="stVerticalBlock"] {
            gap: 0.5rem;
        }
        div[data-testid="stVerticalBlockBorderWrapper"]:has(> div > div[data-testid="stVerticalBlock"]) {
            border-radius: 4px !important; border-color: #E7E7EA !important;
            padding: 0.25rem 0.25rem;
        }

        .bf-gate {
            border: 1px solid #0B0B0C; border-radius: 4px; padding: 1rem 1.25rem;
            background: #F7F7F9; margin-bottom: 1.25rem;
        }
        .bf-gate b { color: #0B0B0C; }

        .bf-metric-name { font-size: 1.02rem; font-weight: 700; color: #0B0B0C; margin-bottom: 0.1rem; }

        .bf-badge {
            display: inline-block; font-size: 0.72rem; font-weight: 700; letter-spacing: 0.04em;
            text-transform: uppercase; border-radius: 3px; padding: 0.2rem 0.55rem;
        }

        button[kind="primary"], button[kind="primaryFormSubmit"] {
            border-radius: 999px !important; font-weight: 700 !important; border: none !important;
            background: #0B0B0C !important; color: #FFFFFF !important; padding: 0.6rem 1.4rem !important;
        }
        button[kind="primary"]:hover, button[kind="primaryFormSubmit"]:hover { background: #2A2A2E !important; }

        button[kind="secondary"], button[kind="secondaryFormSubmit"] {
            border-radius: 999px !important; font-weight: 600 !important;
            border: 1.5px solid #E7E7EA !important; background: #FFFFFF !important; color: #0B0B0C !important;
            padding: 0.6rem 1.4rem !important;
        }
        button[kind="secondary"]:hover, button[kind="secondaryFormSubmit"]:hover { border-color: #0B0B0C !important; }
        button:disabled { opacity: 0.35 !important; cursor: not-allowed !important; }

        [data-testid="stTextInput"] input, [data-testid="stTextArea"] textarea, [data-testid="stSelectbox"] div[data-baseweb="select"] {
            border-radius: 4px !important;
        }

        section[data-testid="stSidebar"] { background: #F7F7F9; border-right: 1px solid #E7E7EA; }
        </style>
        """,
        unsafe_allow_html=True,
    )


def render_hero():
    st.markdown(
        """
        <div class="bf-hero">
            <div class="bf-eyebrow">Portfolio project · AI research agent</div>
            <div class="bf-title">BENCH-FIT</div>
            <div class="bf-subtitle">
                The hard part of judging campaign results isn't the math — it's knowing what a
                reasonable benchmark even <i>is</i> for your industry, company stage, and channel.
                BENCH-FIT researches that benchmark, lets you review and adjust it, and only then
                scores your actual results against it. AI proposes the standard; you approve it.
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def verdict_badge(verdict):
    bg, fg = VERDICT_COLORS.get(verdict, VERDICT_COLORS["No benchmark available"])
    return f'<span class="bf-badge" style="background:{bg};color:{fg};">{verdict}</span>'
