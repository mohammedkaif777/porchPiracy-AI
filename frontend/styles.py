"""Theme constants and CSS for the Streamlit dashboard."""

# --- Colour palette ---
PRIMARY = "#6C63FF"
PRIMARY_DARK = "#5A52D5"
ACCENT = "#FF6584"
BG_DARK = "#0E1117"
BG_CARD = "#1A1D29"
BG_CARD_HOVER = "#232738"
TEXT_PRIMARY = "#FFFFFF"
TEXT_SECONDARY = "#A0AEC0"
BORDER = "#2D3748"

SUCCESS = "#48BB78"
WARNING = "#F6AD55"
DANGER = "#FC8181"

# --- Severity colours ---
SEVERITY_COLORS = {
    "LOW": "#48BB78",
    "MEDIUM": "#F6AD55",
    "HIGH": "#FC8181",
}

THREAT_COLORS = {
    "NONE": "#A0AEC0",
    "MONITORING": "#63B3ED",
    "SUSPICIOUS": "#F6AD55",
    "THREAT": "#FC8181",
}

STATUS_COLORS = {
    "OPEN": DANGER,
    "REVIEWED": SUCCESS,
    "DISMISSED": TEXT_SECONDARY,
}

# --- CSS injection ---
GLOBAL_CSS = f"""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap');

.stApp {{
    font-family: 'Inter', sans-serif;
}}

/* Custom metric cards */
.metric-card {{
    background: {BG_CARD};
    border: 1px solid {BORDER};
    border-radius: 12px;
    padding: 20px;
    text-align: center;
    transition: all 0.3s ease;
}}
.metric-card:hover {{
    background: {BG_CARD_HOVER};
    border-color: {PRIMARY};
    transform: translateY(-2px);
    box-shadow: 0 8px 25px rgba(108, 99, 255, 0.15);
}}
.metric-value {{
    font-size: 2.2em;
    font-weight: 700;
    color: {TEXT_PRIMARY};
    margin: 4px 0;
}}
.metric-label {{
    font-size: 0.85em;
    color: {TEXT_SECONDARY};
    text-transform: uppercase;
    letter-spacing: 0.5px;
}}

/* Badge styles */
.badge {{
    display: inline-block;
    padding: 4px 14px;
    border-radius: 20px;
    font-size: 0.8em;
    font-weight: 600;
    letter-spacing: 0.3px;
}}
.badge-low {{ background: rgba(72, 187, 120, 0.15); color: {SUCCESS}; }}
.badge-medium {{ background: rgba(246, 173, 85, 0.15); color: {WARNING}; }}
.badge-high {{ background: rgba(252, 129, 129, 0.15); color: {DANGER}; }}
.badge-simulated {{
    background: rgba(99, 179, 237, 0.15);
    color: #63B3ED;
    font-size: 0.7em;
    padding: 2px 8px;
    border-radius: 10px;
    margin-left: 6px;
}}

/* Event feed */
.event-item {{
    background: {BG_CARD};
    border: 1px solid {BORDER};
    border-radius: 8px;
    padding: 12px 16px;
    margin-bottom: 8px;
    transition: border-color 0.2s;
}}
.event-item:hover {{
    border-color: {PRIMARY};
}}

/* Status indicator */
.status-dot {{
    display: inline-block;
    width: 10px;
    height: 10px;
    border-radius: 50%;
    margin-right: 8px;
    animation: pulse 2s infinite;
}}
@keyframes pulse {{
    0%, 100% {{ opacity: 1; }}
    50% {{ opacity: 0.5; }}
}}

/* Section headers */
.section-header {{
    display: flex;
    align-items: center;
    gap: 10px;
    margin-bottom: 16px;
    padding-bottom: 8px;
    border-bottom: 1px solid {BORDER};
}}
</style>
"""
