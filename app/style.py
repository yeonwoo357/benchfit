import streamlit as st

PALETTE = {
    "pink": "#F6B8D6",
    "periwinkle": "#8C94F0",
    "orange": "#F6A04D",
    "lime": "#D6DD5C",
    "sky": "#9FDCF2",
    "ink": "#0B0B0C",
    "muted": "#5B5B63",
    "surface": "#F7F7F9",
    "border": "#E7E7EA",
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
        @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap');

        html, body, [class*="css"] { font-family: 'Inter', -apple-system, sans-serif; }

        #MainMenu, footer, header[data-testid="stHeader"] { visibility: hidden; height: 0; }

        .block-container { padding-top: 1rem; max-width: 880px; }

        h1, h2, h3 { font-weight: 800 !important; letter-spacing: -0.02em; color: #0B0B0C; }

        .bf-hero { position: relative; padding: 2.75rem 0 1.5rem 0; overflow: visible; }
        .bf-blobs { position: relative; height: 90px; margin-bottom: 0.25rem; }
        .bf-blob {
            position: absolute; top: 0; width: 86px; height: 86px;
            box-shadow: 0 10px 24px rgba(0,0,0,0.06);
        }
        .bf-blob.b1 { left: 0%;  background: #F6B8D6; border-radius: 42% 58% 70% 30% / 45% 45% 55% 55%; transform: rotate(-8deg); }
        .bf-blob.b2 { left: 13%; top: 14px; background: #8C94F0; border-radius: 58% 42% 35% 65% / 55% 40% 60% 45%; transform: rotate(10deg); }
        .bf-blob.b3 { left: 26%; background: #F6A04D; border-radius: 35% 65% 55% 45% / 40% 55% 45% 60%; transform: rotate(4deg); }
        .bf-blob.b4 { left: 39%; top: 10px; background: #D6DD5C; border-radius: 65% 35% 45% 55% / 50% 55% 45% 50%; transform: rotate(-6deg); }
        .bf-blob.b5 { left: 52%; background: #9FDCF2; border-radius: 48% 52% 60% 40% / 55% 45% 55% 45%; transform: rotate(12deg); }

        .bf-title { font-size: 3rem; font-weight: 800; letter-spacing: -0.03em; color: #0B0B0C; line-height: 1.05; margin: 0; }
        .bf-subtitle { font-size: 1.05rem; color: #5B5B63; max-width: 640px; margin-top: 0.85rem; line-height: 1.55; }
        .bf-tag { display: inline-block; font-size: 0.72rem; font-weight: 600; letter-spacing: 0.04em; text-transform: uppercase;
                  color: #5B5B63; background: #F7F7F9; border: 1px solid #E7E7EA; border-radius: 999px; padding: 0.25rem 0.7rem; margin-top: 1rem; }

        .bf-card { background: #FFFFFF; border: 1px solid #E7E7EA; border-radius: 20px; padding: 1.5rem; margin-bottom: 1rem;
                   box-shadow: 0 1px 2px rgba(0,0,0,0.02); }

        div[data-testid="stVerticalBlockBorderWrapper"] > div > div[data-testid="stVerticalBlock"] {
            gap: 0.5rem;
        }
        div[data-testid="stVerticalBlockBorderWrapper"]:has(> div > div[data-testid="stVerticalBlock"]) {
            border-radius: 20px !important; border-color: #E7E7EA !important;
            box-shadow: 0 1px 2px rgba(0,0,0,0.02); padding: 0.25rem 0.25rem;
        }

        .bf-section-label { font-size: 0.78rem; font-weight: 700; letter-spacing: 0.06em; text-transform: uppercase; color: #8C94F0; margin-bottom: 0.4rem; }

        .bf-gate { border: 1.5px solid #8C94F0; border-radius: 20px; padding: 1rem 1.25rem; background: linear-gradient(135deg, #F7F7FF 0%, #FFFFFF 100%); margin-bottom: 1.25rem; }
        .bf-gate b { color: #0B0B0C; }

        .bf-metric-name { font-size: 1.05rem; font-weight: 700; color: #0B0B0C; margin-bottom: 0.1rem; }

        .bf-badge { display: inline-block; font-size: 0.78rem; font-weight: 700; border-radius: 999px; padding: 0.2rem 0.65rem; }

        div.stButton > button, div.stFormSubmitButton > button {
            border-radius: 999px !important; font-weight: 700 !important; border: none !important;
            background: #0B0B0C !important; color: #FFFFFF !important; padding: 0.55rem 1.4rem !important;
        }
        div.stButton > button:hover, div.stFormSubmitButton > button:hover { background: #2A2A2E !important; }

        [data-testid="stTextInput"] input, [data-testid="stTextArea"] textarea, [data-testid="stSelectbox"] div[data-baseweb="select"] {
            border-radius: 12px !important;
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
            <div class="bf-blobs">
                <div class="bf-blob b1"></div>
                <div class="bf-blob b2"></div>
                <div class="bf-blob b3"></div>
                <div class="bf-blob b4"></div>
                <div class="bf-blob b5"></div>
            </div>
            <div class="bf-title">BenchFit</div>
            <div class="bf-subtitle">
                The hard part of judging campaign results isn't the math — it's knowing what a
                reasonable benchmark even <i>is</i> for your industry, company stage, and channel.
                BenchFit researches that benchmark, lets you review and adjust it, and only then
                scores your actual results against it. AI proposes the standard; you approve it.
            </div>
            <span class="bf-tag">Portfolio project · not a production service</span>
        </div>
        """,
        unsafe_allow_html=True,
    )


def verdict_badge(verdict):
    bg, fg = VERDICT_COLORS.get(verdict, VERDICT_COLORS["No benchmark available"])
    return f'<span class="bf-badge" style="background:{bg};color:{fg};">{verdict}</span>'
