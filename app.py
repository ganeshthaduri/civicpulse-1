import streamlit as st
import streamlit.components.v1 as components
import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go
from collections import Counter
import warnings
import hashlib
from groq import Groq
import json
import os
import folium
from folium.plugins import HeatMap
from streamlit_folium import st_folium
from datetime import datetime, timedelta
import random
warnings.filterwarnings("ignore")
from dotenv import load_dotenv

path = "TELANGANA_DISTRICTS.geojson"

print("Current folder:", os.getcwd())
print("Exists:", os.path.exists(path))



# ══════════════════════════════════════════════════════
#  GROQ CLIENT
# ══════════════════════════════════════════════════════

load_dotenv()

GROQ_API_KEY = os.getenv("GROQ_API_KEY")


groq_client = Groq(api_key=GROQ_API_KEY)


# ══════════════════════════════════════════════════════
#  AUTH CONFIG
# ══════════════════════════════════════════════════════

USERS = {
    "admin": {
        "password": hashlib.sha256("admin123".encode()).hexdigest(),
        "role": "admin",
        "display_name": "Administrator",
        "department": "CivicPulse HQ",
        "email": "admin@civicpulse.gov.in",
    },
    "user1": {
        "password": hashlib.sha256("user123".encode()).hexdigest(),
        "role": "user",
        "display_name": "Ramu",
        "department": "GHMC",
        "email": "ramu@ghmc.gov.in",
    },
    "user2": {
        "password": hashlib.sha256("pass456".encode()).hexdigest(),
        "role": "user",
        "display_name": "Ganesh",
        "department": "HMWSSB",
        "email": "ganesh@hmwssb.gov.in",
    },
    "user3": {
        "password": hashlib.sha256("demo789".encode()).hexdigest(),
        "role": "user",
        "display_name": "Pooja",
        "department": "TSRTC",
        "email": "pooja@tsrtc.gov.in",
    },
}

LOG_FILE        = "activity_log.json"
SUB_FILE        = "subscriptions.json"
LOGIN_COUNTER_FILE = "login_counters.json"
MAX_FREE_LOGINS = 3


# ══════════════════════════════════════════════════════
#  PERSISTENCE HELPERS
# ══════════════════════════════════════════════════════

def load_json(path, default):
    if os.path.exists(path):
        try:
            with open(path, "r") as f:
                return json.load(f)
        except Exception:
            return default
    return default

def save_json(path, data):
    with open(path, "w") as f:
        json.dump(data, f, indent=2)

def load_logs():       return load_json(LOG_FILE, [])
def save_log(entry):
    logs = load_logs(); logs.append(entry); save_json(LOG_FILE, logs)

def load_subs():       return load_json(SUB_FILE, {})
def save_subs(data):   save_json(SUB_FILE, data)

def load_counters():   return load_json(LOGIN_COUNTER_FILE, {})
def save_counters(d):  save_json(LOGIN_COUNTER_FILE, d)

def log_activity(username, action, detail=""):
    save_log({
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "username":  username,
        "role":      USERS.get(username, {}).get("role", "unknown"),
        "action":    action,
        "detail":    detail,
    })

def hash_pw(pw):
    return hashlib.sha256(pw.encode()).hexdigest()

def authenticate(username, password):
    u = USERS.get(username)
    return bool(u and u["password"] == hash_pw(password))


# ══════════════════════════════════════════════════════
#  SUBSCRIPTION HELPERS
# ══════════════════════════════════════════════════════

PLAN_MONTHLY = {"name": "Monthly",  "price": 199,  "duration_days": 30,  "label": "₹199 / month"}
PLAN_YEARLY  = {"name": "Yearly",   "price": 999,  "duration_days": 365, "label": "₹999 / year"}

def get_subscription(username):
    subs = load_subs()
    return subs.get(username)

def is_subscribed(username):
    sub = get_subscription(username)
    if not sub:
        return False
    expiry = datetime.strptime(sub["expiry"], "%Y-%m-%d")
    return expiry >= datetime.now()

def subscribe_user(username, plan_name):
    subs   = load_subs()
    days   = PLAN_MONTHLY["duration_days"] if plan_name == "Monthly" else PLAN_YEARLY["duration_days"]
    price  = PLAN_MONTHLY["price"]         if plan_name == "Monthly" else PLAN_YEARLY["price"]
    expiry = (datetime.now() + timedelta(days=days)).strftime("%Y-%m-%d")
    order  = f"CP{random.randint(100000,999999)}"
    subs[username] = {
        "plan":        plan_name,
        "price":       price,
        "start_date":  datetime.now().strftime("%Y-%m-%d"),
        "expiry":      expiry,
        "order_id":    order,
        "status":      "Active",
        "subscribed_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    }
    save_subs(subs)
    log_activity(username, "SUBSCRIPTION", f"plan={plan_name}, price=₹{price}, order={order}, expiry={expiry}")
    return order

def get_login_count(username):
    counters = load_counters()
    return counters.get(username, 0)

def increment_login_count(username):
    counters = load_counters()
    counters[username] = counters.get(username, 0) + 1
    save_counters(counters)


# ══════════════════════════════════════════════════════
#  PAGE CONFIG
# ══════════════════════════════════════════════════════

st.set_page_config(
    page_title="CivicPulse · Telangana Governance Hub",
    page_icon="🏛️",
    layout="wide",
    initial_sidebar_state="expanded",
)


# ══════════════════════════════════════════════════════
#  GLOBAL CSS
# ══════════════════════════════════════════════════════

st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@300;400;500;600;700;800&family=Lora:wght@600;700&family=JetBrains+Mono:wght@400;500&display=swap');

:root {
  --bg:#e8f4f8; --surface:#ffffff; --surface2:#f0f9fc; --surface3:#daf0f5;
  --border:#b8dce8; --border2:#93c5d8;
  --navy:#0a2540; --navy2:#0d3460; --blue:#1565c0; --blue2:#1e88e5;
  --teal:#00897b; --teal2:#26a69a; --amber:#d97706; --amber2:#f59e0b;
  --rose:#e11d48; --rose2:#f43f5e; --emerald:#00796b; --emerald2:#26a69a;
  --violet:#5e35b1; --violet2:#7e57c2;
  --t1:#0a2540; --t2:#1a4a6b; --t3:#4a7fa0; --t4:#80b0c8;
  --gold:#f59e0b; --gold2:#fbbf24;
  --mint:#00bcd4; --mint2:#4dd0e1; --mint3:#b2ebf2;
}

html,body,[data-testid="stAppViewContainer"]{background:var(--bg)!important;font-family:'Plus Jakarta Sans',sans-serif;color:var(--t1);}
[data-testid="stSidebar"]{background:linear-gradient(180deg,#0a2540 0%,#0d3460 100%)!important;border-right:none;box-shadow:4px 0 24px rgba(10,37,64,.22);}
[data-testid="stSidebar"] *{color:#e0f2fe!important;}
[data-testid="stHeader"]{background:transparent!important;}
.block-container{padding:1.5rem 2.5rem 3rem!important;max-width:100%!important;}

/* Sidebar */
.sb-logo{font-family:'Lora',serif;font-size:1.85rem;font-weight:700;color:#fff!important;letter-spacing:-.02em;line-height:1;margin-bottom:.1rem;}
.sb-logo span{color:#4dd0e1!important;}
.sb-sub{font-size:.58rem;color:#4a90b8!important;text-transform:uppercase;letter-spacing:.2em;font-weight:600;margin-bottom:1.8rem;font-family:'JetBrains Mono',monospace;}
.nav-label{font-size:.55rem;color:#3a7090!important;text-transform:uppercase;letter-spacing:.25em;font-weight:700;margin:1.2rem 0 .5rem;font-family:'JetBrains Mono',monospace;}
.live-pill{display:inline-flex;align-items:center;gap:.35rem;font-size:.6rem;color:#4dd0e1!important;background:rgba(77,208,225,.12);border:1px solid rgba(77,208,225,.25);border-radius:20px;padding:.18rem .65rem;font-family:'JetBrains Mono',monospace;font-weight:600;letter-spacing:.06em;margin-bottom:.7rem;}
.pulse-dot{width:5px;height:5px;border-radius:50%;background:#4dd0e1;box-shadow:0 0 6px #4dd0e1;animation:blink 2s infinite;}
@keyframes blink{0%,100%{opacity:1}50%{opacity:.3}}
[data-testid="stRadio"] label{color:#a0c8de!important;font-size:.82rem!important;}
[data-testid="stRadio"] label:hover{color:#fff!important;}

/* Inputs */
.stMultiSelect>div>div,.stSelectbox>div>div>div,.stTextInput>div>div>input,.stTextArea>div>div>textarea{background:rgba(0,0,0,.08)!important;border:1px solid rgba(0,0,0,.15)!important;border-radius:8px!important;color:#000000!important;font-size:.82rem!important;font-family:'Plus Jakarta Sans',sans-serif!important;}

/* Button */
.stButton>button{background:linear-gradient(135deg,#00897b,#1565c0)!important;color:#fff!important;font-family:'Plus Jakarta Sans',sans-serif!important;font-weight:700!important;font-size:.8rem!important;letter-spacing:.06em!important;text-transform:uppercase!important;border:none!important;border-radius:8px!important;padding:.65rem 2rem!important;box-shadow:0 4px 16px rgba(0,137,123,.3)!important;transition:all .2s!important;}
.stButton>button:hover{transform:translateY(-1px)!important;box-shadow:0 8px 28px rgba(0,188,212,.45)!important;}

/* Hero */
.hero{background:linear-gradient(135deg,var(--navy) 0%,var(--navy2) 50%,#0d4f7c 100%);border-radius:20px;padding:2.5rem 3rem;margin-bottom:2rem;position:relative;overflow:hidden;box-shadow:0 8px 40px rgba(10,37,64,.25);}
.hero::before{content:'';position:absolute;top:-80px;right:-80px;width:380px;height:380px;background:radial-gradient(circle,rgba(0,188,212,.22) 0%,transparent 65%);pointer-events:none;}
.hero::after{content:'';position:absolute;bottom:-60px;left:-60px;width:260px;height:260px;background:radial-gradient(circle,rgba(21,101,192,.25) 0%,transparent 65%);pointer-events:none;}
.hero-eye{font-size:.62rem;color:#4dd0e1;text-transform:uppercase;letter-spacing:.28em;font-weight:600;margin-bottom:.6rem;font-family:'JetBrains Mono',monospace;}
.hero-h{font-family:'Lora',serif;font-size:2.8rem;font-weight:700;line-height:1.08;color:#fff;margin-bottom:.7rem;}
.hero-p{font-size:.92rem;color:#80cfe8;max-width:600px;line-height:1.8;}

/* KPI Card */
.kcard{background:var(--surface);border:1px solid var(--border);border-radius:14px;padding:1.4rem 1.5rem;position:relative;overflow:hidden;box-shadow:0 2px 12px rgba(15,28,46,.06);transition:box-shadow .2s,transform .2s;}
.kcard:hover{box-shadow:0 6px 28px rgba(15,28,46,.12);transform:translateY(-2px);}
.kcard-bar{position:absolute;top:0;left:0;right:0;height:3px;border-radius:14px 14px 0 0;}
.kcard-ico{font-size:1.3rem;margin-bottom:.6rem;}
.kcard-lbl{font-size:.62rem;color:var(--t3);text-transform:uppercase;letter-spacing:.18em;font-weight:600;margin-bottom:.45rem;font-family:'JetBrains Mono',monospace;}
.kcard-val{font-family:'Lora',serif;font-size:2rem;font-weight:700;letter-spacing:-.02em;line-height:1;margin-bottom:.4rem;}
.kcard-sub{font-size:.72rem;color:var(--t3);line-height:1.4;}

/* Section */
.sec-h{font-family:'Lora',serif;font-size:1.15rem;font-weight:700;color:var(--t1);margin-bottom:.2rem;}
.sec-s{font-size:.77rem;color:var(--t3);margin-bottom:1rem;}

/* Chart box */
.cbox{background:var(--surface);border:1px solid var(--border);border-radius:14px;padding:1.3rem 1.4rem;box-shadow:0 2px 10px rgba(15,28,46,.05);}

/* Insight card */
.icard{background:var(--surface);border:1px solid var(--border);border-left:3px solid var(--amber);border-radius:12px;padding:1.1rem 1.3rem;margin-bottom:.8rem;box-shadow:0 2px 8px rgba(15,28,46,.04);transition:box-shadow .2s,transform .2s;}
.icard:hover{box-shadow:0 5px 20px rgba(15,28,46,.1);transform:translateY(-1px);}
.icard-t{font-size:.88rem;font-weight:700;color:var(--t1);margin-bottom:.35rem;}
.icard-b{font-size:.79rem;color:var(--t2);line-height:1.7;}
.badge{display:inline-block;font-size:.57rem;font-weight:700;text-transform:uppercase;letter-spacing:.14em;padding:.14rem .58rem;border-radius:4px;margin-bottom:.45rem;font-family:'JetBrains Mono',monospace;}
.b-red{background:#fef2f2;color:#dc2626;border:1px solid #fecaca;}
.b-amber{background:#fffbeb;color:#d97706;border:1px solid #fde68a;}
.b-teal{background:#f0fdfa;color:#0d9488;border:1px solid #99f6e4;}
.b-green{background:#f0fdf4;color:#059669;border:1px solid #a7f3d0;}
.b-blue{background:#eff6ff;color:#2563eb;border:1px solid #bfdbfe;}
.b-violet{background:#f5f3ff;color:#7c3aed;border:1px solid #ddd6fe;}
.b-gold{background:#fffbeb;color:#b45309;border:1px solid #fde68a;}

/* Feature card */
.fcard{background:var(--surface);border:1px solid var(--border);border-radius:16px;padding:1.7rem 1.5rem;box-shadow:0 2px 10px rgba(10,37,64,.07);position:relative;overflow:hidden;transition:box-shadow .2s,transform .2s;}
.fcard::after{content:'';position:absolute;top:0;left:0;right:0;height:3px;background:linear-gradient(90deg,#1565c0,#00bcd4);transform:scaleX(0);transform-origin:left;transition:transform .3s;}
.fcard:hover{box-shadow:0 8px 32px rgba(10,37,64,.14);transform:translateY(-3px);}
.fcard:hover::after{transform:scaleX(1);}
.fcard-ico{font-size:1.9rem;margin-bottom:.85rem;}
.fcard-t{font-size:.92rem;font-weight:700;color:var(--t1);margin-bottom:.4rem;}
.fcard-d{font-size:.79rem;color:var(--t2);line-height:1.7;}

/* Filter banner */
.fbanner{background:linear-gradient(90deg,#e0f7fa,#e3f2fd);border:1px solid #80deea;border-radius:10px;padding:.6rem 1.1rem;font-size:.72rem;color:#00838f;margin-bottom:1.4rem;font-family:'JetBrains Mono',monospace;letter-spacing:.04em;}

/* Map card */
.map-card{background:var(--surface);border:1px solid var(--border);border-radius:16px;overflow:hidden;box-shadow:0 4px 20px rgba(15,28,46,.1);}

/* Stat pill */
.stat-pill{display:inline-block;background:var(--surface2);border:1px solid var(--border);border-radius:8px;padding:.55rem .9rem;margin:.25rem;text-align:center;}
.stat-pill-val{font-family:'Lora',serif;font-size:1.1rem;font-weight:700;color:var(--t1);}
.stat-pill-lbl{font-size:.62rem;color:var(--t3);text-transform:uppercase;letter-spacing:.1em;margin-top:.1rem;}

/* Divider */
.div{height:1px;background:var(--border);margin:1.8rem 0;}

/* Timeline */
.tl{display:flex;gap:1rem;margin-bottom:1.3rem;}
.tl-dot{width:9px;height:9px;border-radius:50%;background:#00bcd4;margin-top:.38rem;flex-shrink:0;box-shadow:0 0 6px rgba(0,188,212,.5);}
.tl-y{font-family:'JetBrains Mono',monospace;font-size:.7rem;font-weight:600;color:#00838f;margin-bottom:.1rem;}
.tl-d{font-size:.81rem;color:var(--t2);line-height:1.7;}

/* AI section */
.ai-section-header{background:linear-gradient(135deg,#0a2540 0%,#0d3460 100%);border-radius:12px;padding:1rem 1.5rem;margin:1.5rem 0 1rem 0;border-left:4px solid #00bcd4;}
.ai-section-header h3{font-family:'Lora',serif;font-size:1rem;font-weight:700;color:#fff;margin:0 0 .15rem 0;}
.ai-section-header p{font-size:.72rem;color:#80cfe8;margin:0;font-family:'JetBrains Mono',monospace;letter-spacing:.04em;}
.prob-sol-card{background:var(--surface);border:1px solid var(--border);border-radius:14px;padding:1.3rem 1.5rem;margin-bottom:1rem;box-shadow:0 2px 10px rgba(15,28,46,.05);}
.prob-sol-card .prob{background:#fef2f2;border:1px solid #fecaca;border-radius:8px;padding:.75rem 1rem;margin-bottom:.75rem;}
.prob-sol-card .prob-label{font-size:.58rem;font-weight:700;color:#dc2626;text-transform:uppercase;letter-spacing:.18em;font-family:'JetBrains Mono',monospace;margin-bottom:.3rem;}
.prob-sol-card .prob-text{font-size:.84rem;color:#7f1d1d;font-weight:600;line-height:1.5;}
.prob-sol-card .sol{background:#f0fdf4;border:1px solid #a7f3d0;border-radius:8px;padding:.75rem 1rem;}
.prob-sol-card .sol-label{font-size:.58rem;font-weight:700;color:#059669;text-transform:uppercase;letter-spacing:.18em;font-family:'JetBrains Mono',monospace;margin-bottom:.3rem;}
.prob-sol-card .sol-text{font-size:.83rem;color:#14532d;line-height:1.65;}
.metric-highlight{display:inline-block;background:#eff6ff;border:1px solid #bfdbfe;border-radius:6px;padding:.15rem .55rem;font-family:'JetBrains Mono',monospace;font-size:.78rem;font-weight:700;color:#1d4ed8;}

/* Login page */
.login-wrap{max-width:440px;margin:4rem auto 0;background:var(--surface);border:1px solid var(--border);border-radius:20px;padding:2.8rem 2.5rem;box-shadow:0 12px 48px rgba(15,28,46,.12);}
.login-logo{font-family:'Lora',serif;font-size:2.2rem;font-weight:700;color:var(--navy);letter-spacing:-.02em;text-align:center;margin-bottom:.2rem;}
.login-logo span{color:#f59e0b;}
.login-sub{font-size:.65rem;color:var(--t3);text-transform:uppercase;letter-spacing:.22em;font-weight:600;text-align:center;margin-bottom:2rem;font-family:'JetBrains Mono',monospace;}
.role-badge{display:inline-flex;align-items:center;gap:.4rem;padding:.25rem .85rem;border-radius:20px;font-size:.65rem;font-weight:700;letter-spacing:.1em;font-family:'JetBrains Mono',monospace;}
.role-admin{background:#5eead4;color:#60a5fa;border:1px solid #fde68a;}
.role-user{background:#5eead4;color:#1e40af;border:1px solid #bfdbfe;}
.role-pro{background:linear-gradient(135deg,#5eead4,#60a5fa);color:#92400e;border:1px solid #fde68a;}

/* User info bar */
.userbar{background:rgba(255,255,255,.07);border:1px solid rgba(255,255,255,.1);border-radius:10px;padding:.55rem .9rem;margin-bottom:1rem;display:flex;align-items:center;gap:.6rem;}
.userbar-name{font-size:.78rem;font-weight:700;color:#e2e8f0;}
.userbar-dept{font-size:.62rem;color:#7a8fa6;font-family:'JetBrains Mono',monospace;}

/* Subscription plans */
.plan-card{background:var(--surface);border:2px solid var(--border);border-radius:20px;padding:2rem 1.5rem;text-align:center;position:relative;overflow:hidden;transition:all .3s;cursor:pointer;}
.plan-card:hover{border-color:var(--blue);box-shadow:0 12px 40px rgba(37,99,235,.15);transform:translateY(-4px);}
.plan-card.recommended{border-color:var(--gold);box-shadow:0 8px 32px rgba(245,158,11,.2);}
.plan-badge{position:absolute;top:16px;right:-28px;background:linear-gradient(135deg,#f59e0b,#d97706);color:#fff;font-size:.55rem;font-weight:700;letter-spacing:.15em;text-transform:uppercase;padding:.25rem 2.5rem;transform:rotate(45deg);font-family:'JetBrains Mono',monospace;}
.plan-name{font-family:'Lora',serif;font-size:1.4rem;font-weight:700;color:var(--t1);margin-bottom:.4rem;}
.plan-price{font-family:'Lora',serif;font-size:3rem;font-weight:700;color:var(--blue);line-height:1;}
.plan-price span{font-size:1rem;color:var(--t3);}
.plan-period{font-size:.72rem;color:var(--t3);margin-bottom:1.2rem;font-family:'JetBrains Mono',monospace;}
.plan-feature{display:flex;align-items:center;gap:.5rem;font-size:.78rem;color:var(--t2);margin-bottom:.45rem;text-align:left;}

/* Subscription status bar */
.sub-bar-active{background:linear-gradient(135deg,#f0fdf4,#dcfce7);border:1px solid #a7f3d0;border-radius:10px;padding:.6rem 1.1rem;font-size:.72rem;color:#059669;margin-bottom:1rem;font-family:'JetBrains Mono',monospace;letter-spacing:.04em;}
.sub-bar-free{background:linear-gradient(135deg,#fef2f2,#fee2e2);border:1px solid #fecaca;border-radius:10px;padding:.6rem 1.1rem;font-size:.72rem;color:#dc2626;margin-bottom:1rem;font-family:'JetBrains Mono',monospace;letter-spacing:.04em;}

/* Admin revenue card */
.rev-card{background:linear-gradient(135deg,var(--navy),var(--navy2));border-radius:16px;padding:1.6rem;color:#fff;position:relative;overflow:hidden;}
.rev-card::before{content:'';position:absolute;top:-40px;right:-40px;width:180px;height:180px;background:radial-gradient(circle,rgba(245,158,11,.25),transparent 65%);}
.rev-card-label{font-size:.6rem;color:#93adc8;text-transform:uppercase;letter-spacing:.2em;font-family:'JetBrains Mono',monospace;margin-bottom:.4rem;}
.rev-card-val{font-family:'Lora',serif;font-size:2.2rem;font-weight:700;color:#fff;}
.rev-card-sub{font-size:.72rem;color:#93adc8;margin-top:.25rem;}

/* User table row styling */
.sub-active-row{color:#059669;font-weight:700;}
.sub-inactive-row{color:#dc2626;}

/* Paywalled overlay */
.paywall-overlay{background:linear-gradient(135deg,#1a2744 0%,#243056 100%);border-radius:20px;padding:3rem 2.5rem;text-align:center;box-shadow:0 12px 48px rgba(26,39,68,.25);}
.paywall-overlay h2{font-family:'Lora',serif;font-size:2rem;font-weight:700;color:#fff;margin-bottom:.6rem;}
.paywall-overlay p{font-size:.9rem;color:#93adc8;max-width:500px;margin:0 auto 1.5rem;line-height:1.8;}

/* Log row */
.log-row{display:flex;gap:.6rem;align-items:flex-start;padding:.6rem .9rem;border-bottom:1px solid var(--border);font-size:.78rem;}
.log-ts{font-family:'JetBrains Mono',monospace;font-size:.65rem;color:var(--t3);white-space:nowrap;min-width:130px;}

[data-testid="stDataFrame"]{border-radius:12px!important;border:1px solid var(--border)!important;background:var(--surface)!important;}
[data-testid="stExpander"]{background:var(--surface)!important;border:1px solid var(--border)!important;border-radius:10px!important;}
</style>
""", unsafe_allow_html=True)


# ══════════════════════════════════════════════════════
#  SESSION STATE INIT
# ══════════════════════════════════════════════════════

for k, v in [("logged_in", False), ("username", ""), ("role", ""),
             ("login_error", ""), ("show_subscribe", False),
             ("sub_success", ""), ("last_page", ""), ("last_filter", "")]:
    if k not in st.session_state:
        st.session_state[k] = v


# ══════════════════════════════════════════════════════
#  PLOTLY BASE THEME
# ══════════════════════════════════════════════════════

PB = dict(
    paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
    font=dict(color="#4a7fa0", family="Plus Jakarta Sans"),
    margin=dict(l=10, r=10, t=36, b=10),
    legend=dict(bgcolor="rgba(0,0,0,0)", font=dict(color="#1a4a6b", size=11)),
    xaxis=dict(gridcolor="#daf0f5", linecolor="#b8dce8", tickfont=dict(color="#4a7fa0", size=10), zerolinecolor="#b8dce8"),
    yaxis=dict(gridcolor="#daf0f5", linecolor="#b8dce8", tickfont=dict(color="#4a7fa0", size=10), zerolinecolor="#b8dce8"),
)
C        = ["#1565c0","#00897b","#00bcd4","#26a69a","#5e35b1","#0288d1","#00acc1","#2e7d32","#1976d2","#00695c"]
HEAT     = [[0,"#e0f7fa"],[0.5,"#0288d1"],[1,"#0a2540"]]
SENT     = [[0,"#e53935"],[0.45,"#f59e0b"],[1,"#00897b"]]
BLUE_S   = [[0,"#e3f2fd"],[0.5,"#42a5f5"],[1,"#1565c0"]]
TEAL_S   = [[0,"#e0f7fa"],[0.5,"#26c6da"],[1,"#00838f"]]
AMBER_S  = [[0,"#fff8e1"],[0.5,"#ffca28"],[1,"#f57f17"]]
VIOLET_S = [[0,"#ede7f6"],[0.5,"#9575cd"],[1,"#4527a0"]]
MINT_S   = [[0,"#e0f2f1"],[0.5,"#4db6ac"],[1,"#00695c"]]


# ══════════════════════════════════════════════════════
#  HELPER COMPONENTS
# ══════════════════════════════════════════════════════

def kpi(label, value, sub, color, icon=""):
    st.markdown(f"""<div class="kcard">
      <div class="kcard-bar" style="background:linear-gradient(90deg,{color},transparent);"></div>
      <div class="kcard-ico">{icon}</div>
      <div class="kcard-lbl">{label}</div>
      <div class="kcard-val" style="color:{color};">{value}</div>
      <div class="kcard-sub">{sub}</div>
    </div>""", unsafe_allow_html=True)

def sec(title, sub=""):
    st.markdown(f'<div class="sec-h">{title}</div>', unsafe_allow_html=True)
    if sub: st.markdown(f'<div class="sec-s">{sub}</div>', unsafe_allow_html=True)

def show_fbanner(df, fact, filters_active, sel_years, sel_bor, sel_agency, sel_ctype):
    if filters_active:
        pct = len(df)/len(fact)*100
        active_filters = []
        if sel_years:  active_filters.append(f"Years: {', '.join(map(str,sel_years))}")
        if sel_bor:    active_filters.append(f"Districts: {', '.join(sel_bor)}")
        if sel_agency: active_filters.append(f"Agencies: {', '.join(sel_agency)}")
        if sel_ctype:  active_filters.append(f"Types: {', '.join(sel_ctype[:2])}{'…' if len(sel_ctype)>2 else ''}")
        st.markdown(f'<div class="fbanner">⚡ FILTERS ACTIVE — showing {len(df):,} of {len(fact):,} records ({pct:.1f}%) · {" | ".join(active_filters)}</div>',
                    unsafe_allow_html=True)

def prob_sol(title, problem, solution, badge_color="b-red", icon="⚠️"):
    st.markdown(f"""
    <div class="prob-sol-card">
      <div style="display:flex;align-items:center;gap:.6rem;margin-bottom:.75rem;">
        <span style="font-size:1.2rem">{icon}</span>
        <div><div class="badge {badge_color}" style="margin-bottom:0">{title}</div></div>
      </div>
      <div class="prob">
        <div class="prob-label">🔴 Problem Identified</div>
        <div class="prob-text">{problem}</div>
      </div>
      <div class="sol">
        <div class="sol-label">✅ Recommended Solution</div>
        <div class="sol-text">{solution}</div>
      </div>
    </div>""", unsafe_allow_html=True)


# ══════════════════════════════════════════════════════
#  GROQ AI INSIGHTS
# ══════════════════════════════════════════════════════

def generate_ai_insights(page_name, df):
    try:
        total_complaints = len(df)
        avg_resolution = round(df["ResolutionDays"].mean(), 2)
        avg_sentiment = round(df["SentimentScore"].mean(), 2)
        top_agency = (
            df.groupby("AgencyName").size().sort_values(ascending=False).index[0]
        )
        top_complaint = (
            df.groupby("ComplaintType").size().sort_values(ascending=False).index[0]
        )
        sla_breach = int((df["SLAStatus"] == "Breached SLA").sum())

        prompt = f"""
You are an expert Telangana governance AI analyst. Analyze this civic complaint data and respond ONLY with a valid JSON object — no preamble, no markdown, no backticks.

PAGE: {page_name}
DATA:
- Total Complaints: {total_complaints}
- Average Resolution Days: {avg_resolution}
- Average Sentiment Score: {avg_sentiment}  (-1=very negative, +1=very positive)
- Top Agency by volume: {top_agency}
- Top Complaint Type: {top_complaint}
- SLA Breaches: {sla_breach}

Return this exact JSON structure:
{{
  "key_insights": [
    {{"title": "...", "detail": "..."}},
    {{"title": "...", "detail": "..."}},
    {{"title": "...", "detail": "..."}}
  ],
  "major_problems": [
    {{"title": "...", "detail": "..."}},
    {{"title": "...", "detail": "..."}}
  ],
  "recommended_actions": [
    {{"title": "...", "detail": "..."}},
    {{"title": "...", "detail": "..."}}
  ],
  "governance_suggestions": [
    {{"title": "...", "detail": "..."}},
    {{"title": "...", "detail": "..."}}
  ]
}}
Keep each detail concise (1–2 sentences). Use specific numbers from the data.
"""

        response = groq_client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.2,
            max_tokens=900,
        )
        raw = response.choices[0].message.content.strip()
        # Strip markdown fences if model wraps in ```json
        raw = raw.replace("```json", "").replace("```", "").strip()
        return json.loads(raw)

    except Exception as e:
        return {"error": str(e)}


def render_ai_insight_cards(data):
    """Render structured AI insight JSON as styled cards."""
    if not data or "error" in data:
        st.error(f"⚠️ Could not generate AI insights: {data.get('error', 'Unknown error')}")
        return

    section_config = {
        "key_insights": {
            "label": "🔍 Key Insights",
            "badge_class": "b-blue",
            "border": "#1565c0",
            "bg": "#eff6ff",
            "icon": "💡",
        },
        "major_problems": {
            "label": "🚨 Major Problems",
            "badge_class": "b-red",
            "border": "#dc2626",
            "bg": "#fef2f2",
            "icon": "⚠️",
        },
        "recommended_actions": {
            "label": "✅ Recommended Actions",
            "badge_class": "b-teal",
            "border": "#0d9488",
            "bg": "#f0fdfa",
            "icon": "🎯",
        },
        "governance_suggestions": {
            "label": "🏛️ Governance Suggestions",
            "badge_class": "b-violet",
            "border": "#7c3aed",
            "bg": "#f5f3ff",
            "icon": "🧠",
        },
    }

    section_keys = list(section_config.keys())
    # Render in 2-column layout: row 1 = insights + problems, row 2 = actions + suggestions
    for row_keys in [section_keys[:2], section_keys[2:]]:
        cols = st.columns(len(row_keys))
        for col, key in zip(cols, row_keys):
            cfg   = section_config[key]
            items = data.get(key, [])
            with col:
                st.markdown(
                    f"""<div style="background:{cfg['bg']};border:1.5px solid {cfg['border']};
                    border-radius:14px;padding:1.1rem 1.2rem;margin-bottom:1rem;
                    box-shadow:0 2px 12px rgba(15,28,46,.07);">
                    <div style="font-size:.62rem;font-weight:700;color:{cfg['border']};
                    text-transform:uppercase;letter-spacing:.18em;
                    font-family:'JetBrains Mono',monospace;margin-bottom:.85rem;">
                    {cfg['label']}</div>""",
                    unsafe_allow_html=True,
                )
                for item in items:
                    title  = item.get("title", "")
                    detail = item.get("detail", "")
                    st.markdown(
                        f"""<div style="background:#ffffff;border:1px solid {cfg['border']}33;
                        border-left:3px solid {cfg['border']};border-radius:8px;
                        padding:.75rem .9rem;margin-bottom:.65rem;">
                        <div style="font-size:.82rem;font-weight:700;color:#0f1c2e;
                        margin-bottom:.3rem;">{cfg['icon']} {title}</div>
                        <div style="font-size:.77rem;color:#3d5068;line-height:1.7;">{detail}</div>
                        </div>""",
                        unsafe_allow_html=True,
                    )
                st.markdown("</div>", unsafe_allow_html=True)
        st.markdown("<br>", unsafe_allow_html=True)


def render_chat_reply_cards(ai_reply: str):
    """Parse and render chat assistant reply as structured cards.
    Falls back to plain text if the reply isn't JSON."""
    try:
        clean = ai_reply.strip().replace("```json", "").replace("```", "").strip()
        data  = json.loads(clean)
        render_ai_insight_cards(data)
    except Exception:
        # Plain-text fallback — wrap in a styled card
        st.markdown(
            f"""<div style="background:#f0f9fc;border:1.5px solid #00bcd4;border-radius:14px;
            padding:1.2rem 1.4rem;font-size:.85rem;color:#0f1c2e;line-height:1.8;
            box-shadow:0 2px 10px rgba(0,188,212,.1);">{ai_reply}</div>""",
            unsafe_allow_html=True,
        )


# ══════════════════════════════════════════════════════
#  LOGIN PAGE
# ══════════════════════════════════════════════════════

def show_login():
    _, mid, _ = st.columns([1, 1.2, 1])
    with mid:
        st.markdown("""
        <div class="login-wrap">
          <div class="login-logo">Civic<span>Pulse</span></div>
          <div class="login-sub">Telangana · Governance Intelligence</div>
        </div>
        """, unsafe_allow_html=True)

        with st.form("login_form"):
            st.markdown("##### Sign in to your account")
            username = st.text_input("Username", placeholder="Enter your username")
            password = st.text_input("Password", type="password", placeholder="Enter your password")
            submitted = st.form_submit_button("Sign In  →", use_container_width=True)

        if submitted:
            if authenticate(username, password):
                role = USERS[username]["role"]
                # For regular users, check free login quota
                if role == "user" and not is_subscribed(username):
                    count = get_login_count(username)
                    if count >= MAX_FREE_LOGINS:
                        st.session_state.login_error = f"⛔ Free login limit reached ({MAX_FREE_LOGINS}/{MAX_FREE_LOGINS}). Please subscribe to continue."
                        log_activity(username, "LOGIN_BLOCKED", "Free login quota exhausted")
                        # Still allow them in to show the subscription page
                        st.session_state.logged_in  = True
                        st.session_state.username   = username
                        st.session_state.role       = role
                        st.session_state.show_subscribe = True
                        st.rerun()
                        return
                    increment_login_count(username)

                st.session_state.logged_in  = True
                st.session_state.username   = username
                st.session_state.role       = role
                st.session_state.login_error = ""
                st.session_state.show_subscribe = False
                log_activity(username, "LOGIN", f"Successful login from role={role}")
                st.rerun()
            else:
                st.session_state.login_error = "Invalid username or password."
                log_activity(username, "LOGIN_FAILED", f"Failed login attempt for '{username}'")

        if st.session_state.login_error and not st.session_state.logged_in:
            st.error(st.session_state.login_error)

        st.markdown("<br>", unsafe_allow_html=True)
        st.markdown("""
        <div style="background:#f8fafc;border:1px solid #dde3ec;border-radius:10px;
        padding:1rem 1.2rem;font-size:0.78rem;color:#3d5068;">
        <b style="color:#0f1c2e;">Demo credentials</b><br><br>
        <span style="font-family:'JetBrains Mono',monospace;">
        🔑 <b>admin</b> / admin123 &nbsp;→&nbsp; Admin role<br>
        🔑 <b>user1</b> / user123 &nbsp;→&nbsp; User role<br>
        🔑 <b>user2</b> / pass456 &nbsp;→&nbsp; User role<br>
        🔑 <b>user3</b> / demo789 &nbsp;→&nbsp; User role
        </span>
        </div>
        """, unsafe_allow_html=True)


# ══════════════════════════════════════════════════════
#  SUBSCRIPTION PAGE (for users)
# ══════════════════════════════════════════════════════

def show_subscription_page(forced=False):
    username    = st.session_state.username
    sub         = get_subscription(username)
    count       = get_login_count(username)
    remaining   = max(0, MAX_FREE_LOGINS - count)
    user_info   = USERS[username]

    if forced:
        st.markdown("""
        <div class="paywall-overlay">
          <div style="font-size:3rem;margin-bottom:1rem;">🔒</div>
          <h2>Free Access Limit Reached</h2>
          <p>You have used all <b style="color:#f59e0b">3 free logins</b>. Subscribe to CivicPulse Pro for unlimited access to all governance intelligence modules.</p>
        </div>
        """, unsafe_allow_html=True)
        st.markdown("<br>", unsafe_allow_html=True)
    else:
        st.markdown("""
        <div class="hero">
          <div class="hero-eye">💎 CivicPulse Pro · Subscription Plans</div>
          <div class="hero-h">Upgrade Your Access</div>
          <div class="hero-p">Unlock unlimited access to all governance intelligence modules — dashboards,
          geospatial maps, SLA tracking, sentiment analysis, and AI insights.</div>
        </div>""", unsafe_allow_html=True)

        if sub and is_subscribed(username):
            expiry = sub["expiry"]
            plan   = sub["plan"]
            st.markdown(f"""<div class="sub-bar-active">
            ✅ ACTIVE SUBSCRIPTION — Plan: <b>{plan}</b> · Expires: <b>{expiry}</b> · Order: <b>{sub['order_id']}</b>
            </div>""", unsafe_allow_html=True)
        else:
            if remaining > 0:
                st.markdown(f"""<div class="sub-bar-free">
                ⚠️ FREE PLAN — <b>{remaining} free login(s) remaining</b> out of {MAX_FREE_LOGINS}. Upgrade now for unlimited access.
                </div>""", unsafe_allow_html=True)
            else:
                st.markdown("""<div class="sub-bar-free">
                🔒 FREE LIMIT REACHED — Subscribe to continue using CivicPulse.
                </div>""", unsafe_allow_html=True)

    # Plan cards
    c1, c2, c3 = st.columns([1, 1, 1])

    with c1:
        st.markdown("""
        <div class="plan-card">
          <div class="plan-name">🆓 Free</div>
          <div class="plan-price">₹0</div>
          <div class="plan-period">forever</div>
          <div class="plan-feature">✅ 3 total logins</div>
          <div class="plan-feature">✅ Home dashboard</div>
          <div class="plan-feature">❌ Command Center</div>
          <div class="plan-feature">❌ Geospatial Maps</div>
          <div class="plan-feature">❌ SLA Tracker</div>
          <div class="plan-feature">❌ Sentiment NLP</div>
          <div class="plan-feature">❌ AI Insights</div>
        </div>""", unsafe_allow_html=True)
        st.markdown("<br>", unsafe_allow_html=True)
        st.button("Current Plan", disabled=True, key="free_btn", use_container_width=True)

    with c2:
        st.markdown("""
        <div class="plan-card">
          <div class="plan-name">📅 Monthly</div>
          <div class="plan-price">₹199<span>/mo</span></div>
          <div class="plan-period">billed monthly · cancel anytime</div>
          <div class="plan-feature">✅ Unlimited logins</div>
          <div class="plan-feature">✅ Home dashboard</div>
          <div class="plan-feature">✅ Command Center</div>
          <div class="plan-feature">✅ Geospatial Maps</div>
          <div class="plan-feature">✅ SLA Tracker</div>
          <div class="plan-feature">✅ Sentiment NLP</div>
          <div class="plan-feature">✅ AI Insights</div>
        </div>""", unsafe_allow_html=True)
        st.markdown("<br>", unsafe_allow_html=True)
        if st.button("Subscribe — ₹199/mo", key="monthly_btn", use_container_width=True):
            order = subscribe_user(username, "Monthly")
            st.session_state.show_subscribe = False
            st.session_state.sub_success = f"🎉 Monthly plan activated! Order ID: **{order}**"
            st.rerun()

    with c3:
        st.markdown("""
        <div class="plan-card recommended">
          <div class="plan-badge">Best Value</div>
          <div class="plan-name">⭐ Yearly</div>
          <div class="plan-price">₹999<span>/yr</span></div>
          <div class="plan-period">billed annually · save 58%</div>
          <div class="plan-feature">✅ Unlimited logins</div>
          <div class="plan-feature">✅ Home dashboard</div>
          <div class="plan-feature">✅ Command Center</div>
          <div class="plan-feature">✅ Geospatial Maps</div>
          <div class="plan-feature">✅ SLA Tracker</div>
          <div class="plan-feature">✅ Sentiment NLP</div>
          <div class="plan-feature">✅ AI Insights</div>
        </div>""", unsafe_allow_html=True)
        st.markdown("<br>", unsafe_allow_html=True)
        if st.button("Subscribe — ₹999/yr", key="yearly_btn", use_container_width=True):
            order = subscribe_user(username, "Yearly")
            st.session_state.show_subscribe = False
            st.session_state.sub_success = f"🎉 Yearly plan activated! Order ID: **{order}**"
            st.rerun()

    st.markdown("<br>", unsafe_allow_html=True)
    # FAQ
    st.markdown("""
    <div style="background:#f8fafc;border:1px solid #dde3ec;border-radius:14px;padding:1.5rem 2rem;">
      <div style="font-family:'Lora',serif;font-size:1rem;font-weight:700;color:#0f1c2e;margin-bottom:1rem;">Frequently Asked Questions</div>
      <div style="display:grid;grid-template-columns:1fr 1fr;gap:1rem;">
        <div><div style="font-size:.8rem;font-weight:700;color:#0f1c2e;margin-bottom:.3rem;">💳 How do I pay?</div>
          <div style="font-size:.75rem;color:#7a8fa6;line-height:1.6;">Click Subscribe and payment is processed securely via Razorpay/UPI. Demo mode activates instantly.</div></div>
        <div><div style="font-size:.8rem;font-weight:700;color:#0f1c2e;margin-bottom:.3rem;">🔄 Can I cancel?</div>
          <div style="font-size:.75rem;color:#7a8fa6;line-height:1.6;">Monthly plans can be cancelled anytime. Access continues until the period ends.</div></div>
        <div><div style="font-size:.8rem;font-weight:700;color:#0f1c2e;margin-bottom:.3rem;">📧 Renewal notices?</div>
          <div style="font-size:.75rem;color:#7a8fa6;line-height:1.6;">You'll receive email reminders 7 days before expiry at your registered address.</div></div>
        <div><div style="font-size:.8rem;font-weight:700;color:#0f1c2e;margin-bottom:.3rem;">🏛️ Government billing?</div>
          <div style="font-size:.75rem;color:#7a8fa6;line-height:1.6;">GST invoices available. Contact billing@civicpulse.gov.in for bulk departmental plans.</div></div>
      </div>
    </div>""", unsafe_allow_html=True)


# ══════════════════════════════════════════════════════
#  DATA LOADER
# ══════════════════════════════════════════════════════

@st.cache_data
def load_data():
    fact   = pd.read_csv("cleaned_fact.csv",  parse_dates=["CreatedDate","ClosedDate"])
    cal    = pd.read_csv("clean_calender.csv")
    geo    = pd.read_csv("Dim_Geography.csv")
    compl  = pd.read_csv("Dim_Complaint.csv")
    agency = pd.read_csv("Dim_Agency.csv")
    fact = fact.merge(geo,    on="ZipCode",      how="left")
    fact = fact.merge(compl,  on="ComplaintType", how="left")
    fact = fact.merge(agency, on="AgencyName",   how="left")
    return fact, cal, geo, compl, agency


# ══════════════════════════════════════════════════════
#  ADMIN HOME PAGE
# ══════════════════════════════════════════════════════

def page_admin_home():
    st.markdown("""
    <div class="hero">
      <div class="hero-eye">🔐 Administration Panel · CivicPulse HQ</div>
      <div class="hero-h">Platform Intelligence Hub</div>
      <div class="hero-p">Complete overview of all users, subscription revenue, activity logs,
      and platform health metrics — all in one authoritative dashboard.</div>
    </div>""", unsafe_allow_html=True)

    logs    = load_logs()
    subs    = load_subs()
    counters= load_counters()

    log_df = pd.DataFrame(logs) if logs else pd.DataFrame(columns=["timestamp","username","role","action","detail"])
    if not log_df.empty:
        log_df["timestamp"] = pd.to_datetime(log_df["timestamp"])

    # ── Build user summary ──
    user_rows = []
    for uname, udata in USERS.items():
        if udata["role"] == "admin":
            continue
        sub      = subs.get(uname, {})
        subbed   = bool(sub) and datetime.strptime(sub["expiry"], "%Y-%m-%d") >= datetime.now() if sub else False
        logins   = get_login_count(uname)
        plan     = sub.get("plan", "Free") if subbed else "Free"
        price    = sub.get("price", 0)     if subbed else 0
        expiry   = sub.get("expiry", "—")  if sub    else "—"
        order    = sub.get("order_id", "—")if sub    else "—"
        start    = sub.get("start_date","—") if sub  else "—"
        last_login = "—"
        if not log_df.empty:
            u_log = log_df[(log_df["username"] == uname) & (log_df["action"] == "LOGIN")]
            if not u_log.empty:
                last_login = u_log["timestamp"].max().strftime("%Y-%m-%d %H:%M")
        user_rows.append({
            "Username":       uname,
            "Display Name":   udata["display_name"],
            "Department":     udata["department"],
            "Email":          udata["email"],
            "Plan":           plan,
            "Status":         "✅ Active" if subbed else "🔴 Free",
            "Revenue (₹)":    price,
            "Start Date":     start,
            "Expiry":         expiry,
            "Order ID":       order,
            "Total Logins":   logins,
            "Free Logins Used": min(logins, MAX_FREE_LOGINS),
            "Last Login":     last_login,
        })
    user_df = pd.DataFrame(user_rows)

    # ── Revenue KPIs ──
    total_rev     = user_df["Revenue (₹)"].sum()
    active_subs   = (user_df["Plan"] != "Free").sum()
    monthly_subs  = (user_df["Plan"] == "Monthly").sum()
    yearly_subs   = (user_df["Plan"] == "Yearly").sum()
    total_users   = len(user_df)
    free_users    = (user_df["Plan"] == "Free").sum()
    conversion_rate = (active_subs / total_users * 100) if total_users > 0 else 0
    mrr           = monthly_subs * 199 + (yearly_subs * 999 / 12)

    k1, k2, k3, k4, k5, k6 = st.columns(6)
    with k1: kpi("Total Revenue", f"₹{total_rev:,}", "All subscriptions", "#00895a", "💰")
    with k2: kpi("Active Subs", f"{active_subs}", f"{conversion_rate:.0f}% conversion", "#1565c0", "⭐")
    with k3: kpi("MRR", f"₹{mrr:,.0f}", "Monthly recurring revenue", "#00897b", "📈")
    with k4: kpi("Monthly Plans", f"{monthly_subs}", f"@ ₹199/mo each", "#5e35b1", "📅")
    with k5: kpi("Yearly Plans", f"{yearly_subs}", f"@ ₹999/yr each", "#d97706", "🗓️")
    with k6: kpi("Free Users", f"{free_users}", f"{total_users} total users", "#e53935", "🆓")

    st.markdown("<div class='div'></div>", unsafe_allow_html=True)

    # ── Revenue & Subscription Charts ──
    r1, r2, r3 = st.columns([2, 2, 1.5])
    with r1:
        sec("Plan Distribution by Users")
        plan_counts = user_df["Plan"].value_counts().reset_index()
        plan_counts.columns = ["Plan", "Users"]
        colors_map  = {"Free": "#b2ebf2", "Monthly": "#1565c0", "Yearly": "#00897b"}
        fig_plan = go.Figure(go.Pie(
            labels=plan_counts["Plan"], values=plan_counts["Users"], hole=0.6,
            marker_colors=[colors_map.get(p, "#5e35b1") for p in plan_counts["Plan"]],
            textinfo="label+percent+value", textfont=dict(color="#3d5068", size=11)
        ))
        fig_plan.update_layout(**{**PB, "height": 270},
            annotations=[dict(text=f"<b>{total_users}</b><br>Users", x=0.5, y=0.5,
                              font=dict(size=13, color="#0f1c2e"), showarrow=False)])
        st.plotly_chart(fig_plan, use_container_width=True)

    with r2:
        sec("Revenue by Plan Type")
        rev_data = pd.DataFrame({
            "Plan": ["Monthly", "Yearly"],
            "Revenue": [monthly_subs * 199, yearly_subs * 999],
            "Subscribers": [monthly_subs, yearly_subs],
        })
        fig_rev = px.bar(rev_data, x="Plan", y="Revenue", color="Plan",
                         color_discrete_map={"Monthly": "#1565c0", "Yearly": "#00897b"},
                         text="Revenue")
        fig_rev.update_traces(texttemplate="₹%{text:,}", textposition="outside",
                              textfont=dict(size=12, color="#0f1c2e"))
        fig_rev.update_layout(**{**PB, "height": 270}, showlegend=False,
                              yaxis_title="Revenue (₹)", xaxis_title="")
        st.plotly_chart(fig_rev, use_container_width=True)

    with r3:
        sec("Revenue Summary")
        st.markdown(f"""
        <div class="rev-card" style="margin-bottom:.75rem;">
          <div class="rev-card-label">💰 Total Revenue Collected</div>
          <div class="rev-card-val">₹{total_rev:,}</div>
          <div class="rev-card-sub">{active_subs} paid subscription(s)</div>
        </div>
        <div class="rev-card" style="background:linear-gradient(135deg,#0d9488,#0f766e);margin-bottom:.75rem;">
          <div class="rev-card-label">📈 Monthly Recurring Revenue</div>
          <div class="rev-card-val">₹{mrr:,.0f}</div>
          <div class="rev-card-sub">Normalized monthly value</div>
        </div>
        <div class="rev-card" style="background:linear-gradient(135deg,#7c3aed,#6d28d9);">
          <div class="rev-card-label">🎯 Conversion Rate</div>
          <div class="rev-card-val">{conversion_rate:.1f}%</div>
          <div class="rev-card-sub">Free → Paid subscribers</div>
        </div>""", unsafe_allow_html=True)

    st.markdown("<div class='div'></div>", unsafe_allow_html=True)

    # ── All Users & Subscriptions Table ──
    sec("All Users & Subscription Details", "Complete user registry with plan status, revenue, and activity")
    st.dataframe(user_df, use_container_width=True, hide_index=True)

    col_dl1, col_dl2 = st.columns(2)
    with col_dl1:
        csv_users = user_df.to_csv(index=False).encode()
        st.download_button("⬇️ Export Users & Subscriptions CSV", csv_users,
                           file_name="civicpulse_users_subscriptions.csv", mime="text/csv")

    st.markdown("<div class='div'></div>", unsafe_allow_html=True)

    # ── Subscription Activity Timeline (from logs) ──
    if not log_df.empty:
        sec("Subscription & Login Activity Timeline")
        sub_logs = log_df[log_df["action"].isin(["SUBSCRIPTION", "LOGIN", "LOGIN_BLOCKED"])].copy()
        if not sub_logs.empty:
            sub_logs["date"] = sub_logs["timestamp"].dt.date
            tl_data = sub_logs.groupby(["date", "action"]).size().reset_index(name="Count")
            fig_tl = px.bar(tl_data, x="date", y="Count", color="action",
                            color_discrete_map={"SUBSCRIPTION": "#00897b", "LOGIN": "#1565c0", "LOGIN_BLOCKED": "#e53935"},
                            barmode="stack")
            fig_tl.update_layout(**{**PB, "height": 240}, xaxis_title="Date", legend_orientation="h", legend_y=-0.22)
            st.plotly_chart(fig_tl, use_container_width=True)

    st.markdown("<div class='div'></div>", unsafe_allow_html=True)

    # ── Monthly vs Yearly Comparison ──
    sec("Plan Economics: Monthly vs Yearly", "Cost comparison and annualised revenue analysis")
    me1, me2, me3, me4 = st.columns(4)
    with me1: kpi("Monthly ARPU", "₹199", "Per user per month", "#1565c0", "📊")
    with me2: kpi("Yearly ARPU", "₹999", "Per user per year", "#f59e0b", "📊")
    with me3: kpi("Yearly Savings", "₹1,389", "vs 12× monthly (58%)", "#00895a", "💸")
    with me4: kpi("Avg Revenue/User", f"₹{total_rev/total_users:.0f}" if total_users else "₹0",
                  "Across all users incl. free", "#5e35b1", "💰")

    st.markdown("<br>", unsafe_allow_html=True)
    st.markdown("""
    <div style="background:#f8fafc;border:1px solid #dde3ec;border-radius:14px;padding:1.2rem 1.8rem;">
    <div style="font-family:'Lora',serif;font-size:.95rem;font-weight:700;color:#0f1c2e;margin-bottom:.8rem;">📐 Plan Projections</div>
    <div style="display:grid;grid-template-columns:repeat(3,1fr);gap:1rem;font-size:.8rem;color:#3d5068;">
      <div style="background:#eff6ff;border:1px solid #bfdbfe;border-radius:10px;padding:1rem;">
        <div style="font-weight:700;color:#2563eb;margin-bottom:.4rem;">If 10 users subscribe monthly</div>
        <div>Monthly Revenue: <b>₹1,990</b></div><div>Annual Revenue: <b>₹23,880</b></div>
      </div>
      <div style="background:#fffbeb;border:1px solid #fde68a;border-radius:10px;padding:1rem;">
        <div style="font-weight:700;color:#d97706;margin-bottom:.4rem;">If 10 users subscribe yearly</div>
        <div>Annual Revenue: <b>₹9,990</b></div><div>Per-month equiv: <b>₹832.50</b></div>
      </div>
      <div style="background:#f0fdf4;border:1px solid #a7f3d0;border-radius:10px;padding:1rem;">
        <div style="font-weight:700;color:#059669;margin-bottom:.4rem;">Break-even at 50 users</div>
        <div>Mixed 50/50 plan split</div><div>Est. Monthly Revenue: <b>₹14,125</b></div>
      </div>
    </div>
    </div>""", unsafe_allow_html=True)

    st.markdown("<div class='div'></div>", unsafe_allow_html=True)

    # ── Full Activity Log ──
    sec("Full Activity Audit Log", "All platform events — most recent first")

    if not log_df.empty:
        la, lb, lc = st.columns(3)
        with la:
            uf = st.multiselect("Filter by User", sorted(log_df["username"].unique()), default=[], key="alg_u", placeholder="All users")
        with lb:
            af = st.multiselect("Filter by Action", sorted(log_df["action"].unique()), default=[], key="alg_a", placeholder="All actions")
        with lc:
            rf = st.multiselect("Filter by Role", sorted(log_df["role"].unique()), default=[], key="alg_r", placeholder="All roles")

        disp = log_df.copy()
        if uf: disp = disp[disp["username"].isin(uf)]
        if af: disp = disp[disp["action"].isin(af)]
        if rf: disp = disp[disp["role"].isin(rf)]

        disp_show = disp.sort_values("timestamp", ascending=False)[
            ["timestamp","username","role","action","detail"]
        ].rename(columns={"timestamp":"Timestamp","username":"User","role":"Role","action":"Action","detail":"Detail"})
        disp_show["Timestamp"] = disp_show["Timestamp"].astype(str)
        st.dataframe(disp_show, use_container_width=True, hide_index=True)

        csv_log = disp_show.to_csv(index=False).encode()
        st.download_button("⬇️ Export Activity Log CSV", csv_log,
                           file_name="civicpulse_activity_log.csv", mime="text/csv")

        # Per-user summary
        st.markdown("<div class='div'></div>", unsafe_allow_html=True)
        sec("Per-User Activity Summary")
        user_sum = log_df.groupby("username").agg(
            Role=("role","first"),
            Total_Events=("action","count"),
            Logins=("action", lambda x:(x=="LOGIN").sum()),
            Blocked_Logins=("action", lambda x:(x=="LOGIN_BLOCKED").sum()),
            Subscriptions=("action", lambda x:(x=="SUBSCRIPTION").sum()),
            Pages_Visited=("action", lambda x:(x=="PAGE_VIEW").sum()),
            Last_Seen=("timestamp","max"),
        ).reset_index().rename(columns={"username":"Username"})
        user_sum["Last_Seen"] = user_sum["Last_Seen"].astype(str)
        st.dataframe(user_sum, use_container_width=True, hide_index=True)
    else:
        st.info("No activity logs recorded yet.")


# ══════════════════════════════════════════════════════
#  MAIN APP (post-login)
# ══════════════════════════════════════════════════════

def show_main_app():
    try:
        fact, cal, geo, compl, agency = load_data()
    except Exception as e:
        st.error(f"⚠️ Could not load data files: {e}")
        st.stop()

    user_info  = USERS[st.session_state.username]
    username   = st.session_state.username
    is_admin   = st.session_state.role == "admin"
    subscribed = is_subscribed(username) if not is_admin else True
    count      = get_login_count(username) if not is_admin else 0
    remaining  = max(0, MAX_FREE_LOGINS - count)

    # ── SIDEBAR ──
    with st.sidebar:
        st.markdown('<div class="sb-logo">Civic<span>Pulse</span></div>', unsafe_allow_html=True)
        st.markdown('<div class="sb-sub">Telangana · Governance Intelligence</div>', unsafe_allow_html=True)

        role_label = "ADMIN" if is_admin else ("PRO" if subscribed else "FREE")
        role_cls   = "role-admin" if is_admin else ("role-pro" if subscribed else "role-user")
        role_ico   = "🔐" if is_admin else ("⭐" if subscribed else "🆓")
        st.markdown(f"""
        <div class="userbar">
          <div>
            <div class="userbar-name">👤 {user_info['display_name']}</div>
            <div class="userbar-dept">{user_info['department']} · <span class="role-badge {role_cls}">{role_ico} {role_label}</span></div>
          </div>
        </div>""", unsafe_allow_html=True)

        # Show subscription status in sidebar for non-admin
        if not is_admin:
            sub = get_subscription(username)
            if subscribed and sub:
                st.markdown(f"""<div style="background:rgba(5,150,105,.12);border:1px solid rgba(5,150,105,.25);border-radius:8px;padding:.4rem .7rem;margin-bottom:.6rem;font-size:.62rem;color:#34d399;font-family:'JetBrains Mono',monospace;">
                ✅ {sub['plan'].upper()} PLAN · Exp: {sub['expiry']}</div>""", unsafe_allow_html=True)
            else:
                st.markdown(f"""<div style="background:rgba(225,29,72,.08);border:1px solid rgba(225,29,72,.2);border-radius:8px;padding:.4rem .7rem;margin-bottom:.6rem;font-size:.62rem;color:#f87171;font-family:'JetBrains Mono',monospace;">
                🆓 FREE — {remaining} login(s) left</div>""", unsafe_allow_html=True)

        st.markdown('<div class="nav-label">Navigation</div>', unsafe_allow_html=True)

        if is_admin:
            pages_map = {"🏠  Admin Home": "admin_home"}
        else:
            pages_map = {
                "🏠  Home":                     "home",
                "💎  Subscription Plans":       "subscribe",
                "📊  Command Center":           "command",
                "🗺️  Geospatial Hotspots":      "geo",
                "🏢  Departmental SLA Tracker": "sla",
                "💬  Citizen Sentiment & NLP":  "nlp",
                "🧠  AI Insights":              "ai",
                "ℹ️  About":                    "about",
                "📞  Contact & Support":        "contact",
            }

        selection = st.radio("", list(pages_map.keys()), label_visibility="collapsed")
        page      = pages_map[selection]

        if not is_admin:
            st.markdown('<div class="div"></div>', unsafe_allow_html=True)
            st.markdown('<div class="nav-label">Global Filters</div>', unsafe_allow_html=True)
            st.markdown('<div class="live-pill"><div class="pulse-dot"></div>LIVE FILTER</div>', unsafe_allow_html=True)

            years_avail    = sorted(fact["Year"].dropna().unique())
            sel_years      = st.multiselect("Year", years_avail, default=[], key="yr", placeholder="All years")
            boroughs       = sorted(fact["Borough"].dropna().unique())
            sel_bor        = st.multiselect("District / Borough", boroughs, default=[], key="bor", placeholder="All districts")
            agencies_avail = sorted(fact["AgencyName"].dropna().unique())
            sel_agency     = st.multiselect("Agency Name", agencies_avail, default=[], key="ag", placeholder="All agencies")
            ctypes_avail   = sorted(fact["ComplaintType"].dropna().unique())
            sel_ctype      = st.multiselect("Complaint Type", ctypes_avail, default=[], key="ct", placeholder="All types")
        else:
            sel_years = sel_bor = sel_agency = sel_ctype = []

        st.markdown('<div class="div"></div>', unsafe_allow_html=True)

        if st.button("🚪 Sign Out"):
            log_activity(username, "LOGOUT", "User signed out")
            for k in ["logged_in","username","role","login_error","show_subscribe","sub_success","last_page","last_filter"]:
                st.session_state[k] = False if k == "logged_in" else ""
            st.rerun()

        st.markdown("""<div style="font-size:.6rem;color:#2d4060;text-align:center;
        font-family:'JetBrains Mono',monospace;">v3.0.0 · 2019–2023 · Telangana Govt.</div>""",
                    unsafe_allow_html=True)

    # ── Subscription success banner ──
    if st.session_state.sub_success:
        st.success(st.session_state.sub_success)
        st.session_state.sub_success = ""

    # ── ADMIN: single page ──
    if is_admin:
        page_admin_home()
        return

    # ── Apply global filters ──
    df = fact.copy()
    filters_active = bool(sel_years or sel_bor or sel_agency or sel_ctype)
    if sel_years:  df = df[df["Year"].isin(sel_years)]
    if sel_bor:    df = df[df["Borough"].isin(sel_bor)]
    if sel_agency: df = df[df["AgencyName"].isin(sel_agency)]
    if sel_ctype:  df = df[df["ComplaintType"].isin(sel_ctype)]

    filter_str = ""
    if filters_active:
        parts = []
        if sel_years:  parts.append(f"years={sel_years}")
        if sel_bor:    parts.append(f"districts={sel_bor}")
        if sel_agency: parts.append(f"agencies={sel_agency}")
        if sel_ctype:  parts.append(f"types={sel_ctype}")
        filter_str = "; ".join(parts)

    if "last_page" not in st.session_state or st.session_state.last_page != page:
        log_activity(username, "PAGE_VIEW", f"page={page}")
        st.session_state.last_page = page

    if filters_active and ("last_filter" not in st.session_state or st.session_state.last_filter != filter_str):
        log_activity(username, "FILTER_APPLIED", filter_str)
        st.session_state.last_filter = filter_str

    def fbanner():
        show_fbanner(df, fact, filters_active, sel_years, sel_bor, sel_agency, sel_ctype)

    # ── Pages that are always accessible ──
    if page == "home":
        st.markdown("""
        <div class="hero">
          <div class="hero-eye">🏛️ Telangana State Government · Citizen Services Intelligence</div>
          <div class="hero-h">CivicPulse Governance Hub</div>
          <div class="hero-p">A unified intelligence platform for monitoring, analysing, and improving
          public service delivery across Telangana's 12 districts.</div>
        </div>""", unsafe_allow_html=True)
        fbanner()

        total=len(df); closed=(df["Status"]=="Closed").sum()
        sla_ok=(df["SLAStatus"]=="Within SLA").sum()
        avg_res=df["ResolutionDays"].mean(); avg_sent=df["SentimentScore"].mean()

        c1,c2,c3,c4,c5=st.columns(5)
        with c1: kpi("Total Complaints",f"{total:,}","All filtered records","#1565c0","📋")
        with c2: kpi("Resolved Cases",f"{closed:,}",f"{closed/total*100:.1f}% resolved","#00897b","✅")
        with c3: kpi("SLA Compliance",f"{sla_ok/total*100:.1f}%",f"{sla_ok:,} within target","#00895a","🎯")
        with c4: kpi("Avg Resolution",f"{avg_res:.1f}d","Mean days to close","#5e35b1","⏱️")
        with c5: kpi("Sentiment Index",f"{avg_sent:+.2f}","−1 negative · +1 positive",
                     "#00895a" if avg_sent>0 else "#e53935","💬")

        if not subscribed:
            st.markdown("<br>", unsafe_allow_html=True)
            st.markdown(f"""
            <div style="background:linear-gradient(135deg,#1a2744,#243056);border-radius:16px;
            padding:1.5rem 2rem;border:1px solid rgba(245,158,11,.3);margin-bottom:1rem;">
              <div style="font-size:.6rem;color:#f59e0b;text-transform:uppercase;letter-spacing:.25em;
              font-family:'JetBrains Mono',monospace;margin-bottom:.5rem;">⚡ UPGRADE TO PRO</div>
              <div style="font-family:'Lora',serif;font-size:1.3rem;font-weight:700;color:#fff;margin-bottom:.4rem;">
                You have <span style="color:#f59e0b">{remaining} free login(s)</span> remaining</div>
              <div style="font-size:.82rem;color:#93adc8;line-height:1.7;">
                Command Center, Maps, SLA Tracker, Sentiment NLP, and AI Insights require a subscription.
                Upgrade from just ₹199/month.</div>
            </div>""", unsafe_allow_html=True)

        st.markdown("<br>", unsafe_allow_html=True)
        sec("Platform Modules","Navigate to any section from the sidebar")
        _modules_locked = [
            ("📊","Command Center","Executive KPIs, complaint trends, and agency resolution status.",not subscribed),
            ("🗺️","Geospatial Mapper","Interactive maps — complaint hotspots by neighbourhood and district.",not subscribed),
            ("🏢","SLA Tracker","Agency accountability — resolution time, breach rates, efficiency.",not subscribed),
            ("💬","Sentiment & NLP","Keyword frequency, gauge, trend lines, and decomposition trees.",not subscribed),
            ("🤖","AI Insights","Deep problem analysis with data-driven solutions and recommendations.",not subscribed),
        ]
        _mod_cards_html = """
        <div style="display:flex;gap:12px;margin-bottom:16px;">
        """
        for _ico, _t, _d, _locked in _modules_locked:
            _lock = "🔒" if _locked else ""
            _mod_cards_html += f"""<div style="flex:1;background:#fff;border:1.5px solid #b8dce8;border-radius:14px;padding:20px 16px 16px 16px;box-shadow:0 2px 10px rgba(10,37,64,0.07);position:relative;overflow:hidden;">
            <div style="position:absolute;top:0;left:0;right:0;height:3px;background:linear-gradient(90deg,#1565c0,#00bcd4);border-radius:14px 14px 0 0;"></div>
            <div style="font-size:28px;margin-bottom:8px;">{_ico}</div>
            <div style="font-size:13px;font-weight:700;color:#0a2540;margin-bottom:5px;">{_lock} {_t}</div>
            <div style="font-size:11px;color:#1a4a6b;line-height:1.6;">{_d}</div>
            </div>"""
        _mod_cards_html += "</div>"
        components.html(_mod_cards_html, height=180, scrolling=False)

        st.markdown("<br>", unsafe_allow_html=True)
        sec("Key Insights at a Glance","Rule-based intelligence derived from the dataset")
        l,r_col=st.columns(2)
        with l:
            ta=df.groupby("AgencyName")["ResolutionDays"].mean().idxmax()
            td=df.groupby("AgencyName")["ResolutionDays"].mean().max()
            wt=df.groupby("ComplaintType")["SentimentScore"].mean().idxmin()
            st.markdown(f"""
            <div class="icard">
              <div class="badge b-red">⚠ Critical</div>
              <div class="icard-t">Slowest Resolution Agency</div>
              <div class="icard-b"><b style="color:#0f1c2e">{ta}</b> averages
              <b style="color:#d97706">{td:.1f} days</b>. Workforce augmentation recommended.</div>
            </div>
            <div class="icard" style="border-left-color:#0d9488">
              <div class="badge b-teal">📌 Pattern</div>
              <div class="icard-t">Most Negative Complaint Category</div>
              <div class="icard-b">Citizens reporting <b style="color:#0f1c2e">"{wt}"</b>
              express the most negative sentiment.</div>
            </div>""", unsafe_allow_html=True)
        with r_col:
            bp=(df["SLAStatus"]=="Breached").mean()*100
            op=(df["Status"]=="Open").mean()*100
            tz=df.groupby("ZipCode").size().idxmax()
            tzc=df.groupby("ZipCode").size().max()
            st.markdown(f"""
            <div class="icard" style="border-left-color:#e11d48">
              <div class="badge b-red">🚨 Alert</div>
              <div class="icard-t">SLA Breach Rate Critical</div>
              <div class="icard-b"><b style="color:#e11d48">{bp:.1f}%</b> breached SLA.
              <b style="color:#0f1c2e">{op:.1f}%</b> still open — backlog escalating.</div>
            </div>
            <div class="icard" style="border-left-color:#059669">
              <div class="badge b-green">📍 Hotspot</div>
              <div class="icard-t">Top Complaint Zip Code: {tz}</div>
              <div class="icard-b"><b style="color:#059669">{tzc:,} complaints</b> here —
              highest density. Deploy rapid-response team.</div>
            </div>""", unsafe_allow_html=True)
        return

    if page == "subscribe":
        show_subscription_page(forced=False)
        return

    if page == "about":
        st.markdown("""<div class="hero">
          <div class="hero-eye">ℹ️ Platform Overview</div>
          <div class="hero-h">About CivicPulse</div>
          <div class="hero-p">The Telangana Governance Intelligence Platform.</div>
        </div>""", unsafe_allow_html=True)
        a1,a2=st.columns([3,2])
        with a1:
            sec("Mission & Vision")
            st.markdown("""<div style="font-size:.9rem;color:#3d5068;line-height:1.9;margin-bottom:1.8rem;
            background:#ffffff;padding:1.2rem 1.4rem;border-radius:12px;border:1px solid #dde3ec;">
            CivicPulse consolidates <b style="color:#0f1c2e">23,000+ service tickets</b> spanning
            <b style="color:#0f1c2e">2019–2023</b> to enable evidence-based resource allocation,
            SLA accountability, and sentiment-driven service improvements across Telangana's 12 districts.
            </div>""", unsafe_allow_html=True)
        with a2:
            sec("Data Overview")
            for ico,lbl,val in [("📋","Total Tickets",f"{len(fact):,}"),("🏢","Agencies",f"{fact['AgencyName'].nunique()}"),
                ("🗺️","Districts",f"{geo['Borough'].nunique()}"),("📆","Date Range","2019–2023")]:
                st.markdown(f"""<div style="display:flex;justify-content:space-between;align-items:center;
                padding:.75rem 1.1rem;background:#ffffff;border:1px solid #dde3ec;border-radius:10px;margin-bottom:.5rem;">
                  <div style="font-size:.8rem;color:#7a8fa6;">{ico} {lbl}</div>
                  <div style="font-family:'Lora',serif;font-weight:700;color:#2563eb;">{val}</div>
                </div>""", unsafe_allow_html=True)
        return

    if page == "contact":
        st.markdown("""<div class="hero">
          <div class="hero-eye">📞 Support & Feedback</div>
          <div class="hero-h">Contact & Support</div>
          <div class="hero-p">Reach the CivicPulse team for technical support or data queries.</div>
        </div>""", unsafe_allow_html=True)
        sec("Get in Touch")
        for ico,lbl,val,note in [
            ("📧","Platform Support","civicpulse@telangana.gov.in","Technical issues, login problems"),
            ("📞","Helpdesk Hotline","1800-599-4599","Mon–Fri 9AM–6PM IST"),
        ]:
            st.markdown(f"""<div style="padding:1rem 1.1rem;background:#ffffff;border:1px solid #dde3ec;
            border-radius:12px;margin-bottom:.65rem;max-width:480px;">
              <div style="font-size:.6rem;color:#b0bfcf;text-transform:uppercase;letter-spacing:.18em;margin-bottom:.25rem;font-family:'JetBrains Mono',monospace;">{ico} {lbl}</div>
              <div style="font-weight:700;color:#2563eb;margin-bottom:.18rem;font-size:.92rem;">{val}</div>
              <div style="font-size:.72rem;color:#7a8fa6;">{note}</div>
            </div>""", unsafe_allow_html=True)
        return

    # ── PAYWALL for premium pages ──
    if not subscribed:
        st.markdown("<br>", unsafe_allow_html=True)
        show_subscription_page(forced=True)
        return


    # ══════════════════════════════════════════════════════
    #  HOME
    # ══════════════════════════════════════════════════════
    if page == "home":
        st.markdown("""
        <div class="hero">
          <div class="hero-eye">🏛️ Telangana State Government · Citizen Services Intelligence</div>
          <div class="hero-h">CivicPulse Governance Hub</div>
          <div class="hero-p">A unified intelligence platform for monitoring, analysing, and improving
          public service delivery across Telangana's 12 districts.</div>
        </div>""", unsafe_allow_html=True)
        fbanner()

        total=len(df); closed=(df["Status"]=="Closed").sum()
        sla_ok=(df["SLAStatus"]=="Within SLA").sum()
        avg_res=df["ResolutionDays"].mean(); avg_sent=df["SentimentScore"].mean()

        c1,c2,c3,c4,c5=st.columns(5)
        with c1: kpi("Total Complaints",f"{total:,}","All filtered records","#1565c0","📋")
        with c2: kpi("Resolved Cases",f"{closed:,}",f"{closed/total*100:.1f}% resolved","#00897b","✅")
        with c3: kpi("SLA Compliance",f"{sla_ok/total*100:.1f}%",f"{sla_ok:,} within target","#00895a","🎯")
        with c4: kpi("Avg Resolution",f"{avg_res:.1f}d","Mean days to close","#5e35b1","⏱️")
        with c5: kpi("Sentiment Index",f"{avg_sent:+.2f}","−1 negative · +1 positive",
                     "#00895a" if avg_sent>0 else "#e53935","💬")

        st.markdown("<br>", unsafe_allow_html=True)
        sec("Platform Modules","Navigate to any section from the sidebar")
        _sub_modules = [
            ("📊","Command Center","Executive KPIs, complaint trends, and agency resolution status."),
            ("🗺️","Geospatial Mapper","Interactive maps — complaint hotspots by neighbourhood and district."),
            ("🏢","SLA Tracker","Agency accountability — resolution time, breach rates, efficiency."),
            ("💬","Sentiment & NLP","Keyword frequency, gauge, trend lines, and decomposition trees."),
            ("🤖","AI Insights","Deep problem analysis with data-driven solutions and recommendations."),
        ]
        _sub_cards_html = """
        <div style="display:flex;gap:12px;margin-bottom:16px;">
        """
        for _ico, _t, _d in _sub_modules:
            _sub_cards_html += f"""<div style="flex:1;background:#fff;border:1.5px solid #b8dce8;border-radius:14px;padding:20px 16px 16px 16px;box-shadow:0 2px 10px rgba(10,37,64,0.07);position:relative;overflow:hidden;">
            <div style="position:absolute;top:0;left:0;right:0;height:3px;background:linear-gradient(90deg,#1565c0,#00bcd4);border-radius:14px 14px 0 0;"></div>
            <div style="font-size:28px;margin-bottom:8px;">{_ico}</div>
            <div style="font-size:13px;font-weight:700;color:#0a2540;margin-bottom:5px;">{_t}</div>
            <div style="font-size:11px;color:#1a4a6b;line-height:1.6;">{_d}</div>
            </div>"""
        _sub_cards_html += "</div>"
        components.html(_sub_cards_html, height=180, scrolling=False)

        st.markdown("<br>", unsafe_allow_html=True)
        sec("Key Insights at a Glance","Rule-based intelligence derived from the dataset")
        l,r=st.columns(2)
        with l:
            ta=df.groupby("AgencyName")["ResolutionDays"].mean().idxmax()
            td=df.groupby("AgencyName")["ResolutionDays"].mean().max()
            wt=df.groupby("ComplaintType")["SentimentScore"].mean().idxmin()
            st.markdown(f"""
            <div class="icard">
              <div class="badge b-red">⚠ Critical</div>
              <div class="icard-t">Slowest Resolution Agency</div>
              <div class="icard-b"><b style="color:#0f1c2e">{ta}</b> averages
              <b style="color:#d97706">{td:.1f} days</b>. Workforce augmentation recommended.</div>
            </div>
            <div class="icard" style="border-left-color:#0d9488">
              <div class="badge b-teal">📌 Pattern</div>
              <div class="icard-t">Most Negative Complaint Category</div>
              <div class="icard-b">Citizens reporting <b style="color:#0f1c2e">"{wt}"</b>
              express the most negative sentiment.</div>
            </div>""", unsafe_allow_html=True)
        with r:
            bp=(df["SLAStatus"]=="Breached").mean()*100
            op=(df["Status"]=="Open").mean()*100
            tz=df.groupby("ZipCode").size().idxmax()
            tzc=df.groupby("ZipCode").size().max()
            st.markdown(f"""
            <div class="icard" style="border-left-color:#e11d48">
              <div class="badge b-red">🚨 Alert</div>
              <div class="icard-t">SLA Breach Rate Critical</div>
              <div class="icard-b"><b style="color:#e11d48">{bp:.1f}%</b> breached SLA.
              <b style="color:#0f1c2e">{op:.1f}%</b> still open — backlog escalating.</div>
            </div>
            <div class="icard" style="border-left-color:#059669">
              <div class="badge b-green">📍 Hotspot</div>
              <div class="icard-t">Top Complaint Zip Code: {tz}</div>
              <div class="icard-b"><b style="color:#059669">{tzc:,} complaints</b> here —
              highest density. Deploy rapid-response team.</div>
            </div>""", unsafe_allow_html=True)

        st.markdown("---")
        st.subheader("🤖 CivicPulse AI Insights")
        if st.button("Generate AI Analysis", key="home_ai"):
            with st.spinner("Analyzing governance data..."):
                insights = generate_ai_insights(page_name="Home Dashboard", df=df)
                render_ai_insight_cards(insights)

 # ══════════════════════════════════════════════════════
    #  COMMAND CENTER
    # ══════════════════════════════════════════════════════
    elif page == "command":
        st.markdown("""
        <div class="hero">
          <div class="hero-eye">📊 Executive Dashboard</div>
          <div class="hero-h">Governance Command Center</div>
          <div class="hero-p">High-level health check — KPIs, complaint trends, SLA compliance,
          and agency-level resolution status.</div>
        </div>""", unsafe_allow_html=True)
        fbanner()

        total=len(df); closed=(df["Status"]=="Closed").sum()
        sla_pct=(df["SLAStatus"]=="Within SLA").mean()*100
        avg_res=df["ResolutionDays"].mean(); avg_sent=df["SentimentScore"].mean()

        c1,c2,c3,c4=st.columns(4)
        with c1: kpi("Total Complaints",f"{total:,}","Filtered dataset","#1565c0","📋")
        with c2: kpi("SLA Compliance",f"{sla_pct:.1f}%",f"{(df['SLAStatus']=='Within SLA').sum():,} within target","#00895a","🎯")
        with c3: kpi("Avg Resolution",f"{avg_res:.1f}d","Mean calendar days to close","#00897b","⏱️")
        with c4: kpi("Sentiment Score",f"{avg_sent:+.3f}","Normalised −1 to +1","#00895a" if avg_sent>0 else "#e53935","💬")

        st.markdown("<br>", unsafe_allow_html=True)
        cl,cr=st.columns([3,2])
        with cl:
            sec("Complaint Volume vs. Resolved Over Time")
            mo=["Jan","Feb","Mar","Apr","May","Jun","Jul","Aug","Sep","Oct","Nov","Dec"]
            monthly=df.groupby(["Year","Month"]).agg(Total=("TicketID","count"),
                Resolved=("Status",lambda x:(x=="Closed").sum())).reset_index()
            monthly["mn"]=monthly["Month"].str[:3].apply(lambda m:mo.index(m) if m in mo else 0)
            monthly=monthly.sort_values(["Year","mn"])
            monthly["Period"]=monthly["Year"].astype(str)+"-"+monthly["Month"].str[:3]
            fig=go.Figure()
            fig.add_trace(go.Scatter(x=monthly["Period"],y=monthly["Total"],mode="lines",name="Total",
                fill="tozeroy",line=dict(color="#1565c0",width=2.5),fillcolor="rgba(21,101,192,0.09)"))
            fig.add_trace(go.Scatter(x=monthly["Period"],y=monthly["Resolved"],mode="lines",name="Resolved",
                fill="tozeroy",line=dict(color="#00897b",width=2.5),fillcolor="rgba(0,137,123,0.08)"))
            fig.update_layout(**{**PB,"height":320},xaxis_tickangle=-40,xaxis_nticks=24)
            st.markdown('<div class="cbox">', unsafe_allow_html=True)
            st.plotly_chart(fig,use_container_width=True)
            st.markdown('</div>', unsafe_allow_html=True)
        with cr:
            sec("Case Status Distribution")
            sc=df["Status"].value_counts().reset_index(); sc.columns=["Status","Count"]
            cmap={"Closed":"#00897b","Open":"#e53935","Pending":"#f9a825"}
            fig2=go.Figure(go.Pie(labels=sc["Status"],values=sc["Count"],hole=0.68,
                marker_colors=[cmap.get(s,"#5e35b1") for s in sc["Status"]],
                textinfo="label+percent",textfont=dict(color="#3d5068",size=11)))
            fig2.update_layout(**{**PB,"height":320},
                annotations=[dict(text=f"<b>{total:,}</b>",x=0.5,y=0.5,
                                  font=dict(size=16,color="#0f1c2e"),showarrow=False)])
            st.plotly_chart(fig2,use_container_width=True)

        st.markdown("<div class='div'></div>", unsafe_allow_html=True)
        sec("Resolved vs. Unresolved Complaints by Agency")
        ags=df.groupby(["AgencyName","Status"]).size().reset_index(name="Count")
        piv=ags.pivot_table(index="AgencyName",columns="Status",values="Count",fill_value=0).reset_index()
        piv["Total"]=piv.drop(columns="AgencyName").sum(axis=1)
        ags2=ags.merge(piv[["AgencyName","Total"]],on="AgencyName").sort_values("Total")
        fig_ag=px.bar(ags2,y="AgencyName",x="Count",color="Status",orientation="h",barmode="stack",
            color_discrete_map={"Closed":"#00897b","Open":"#e53935","Pending":"#f9a825"},text="Count")
        fig_ag.update_traces(texttemplate="%{text:,}",textfont_size=9,textposition="inside",insidetextanchor="middle")
        fig_ag.update_layout(**{**PB,"height":520},yaxis_title="",xaxis_title="Number of Complaints",legend_orientation="h",legend_y=-0.1,bargap=0.25)
        st.plotly_chart(fig_ag,use_container_width=True)

        st.markdown("<br>", unsafe_allow_html=True)
        sec("Agency Resolution Rate Summary Table")
        rt=piv.copy()
        rt["Resolution Rate (%)"]=((rt.get("Closed",0)/rt["Total"])*100).round(1)
        rt["Open Rate (%)"]      =((rt.get("Open",0)/rt["Total"])*100).round(1)
        rt["Pending Rate (%)"]   =((rt.get("Pending",0)/rt["Total"])*100).round(1)
        show=[c for c in ["AgencyName","Total","Closed","Open","Pending","Resolution Rate (%)","Open Rate (%)","Pending Rate (%)"] if c in rt.columns]
        st.dataframe(rt[show].sort_values("Resolution Rate (%)",ascending=False),use_container_width=True,hide_index=True)

        st.markdown("<div class='div'></div>", unsafe_allow_html=True)
        ca,cb=st.columns(2)
        with ca:
            sec("Annual Complaint Trend by Status")
            yr=df.groupby(["Year","Status"]).size().reset_index(name="Count")
            f3=px.bar(yr,x="Year",y="Count",color="Status",barmode="stack",
                      color_discrete_map={"Closed":"#00897b","Open":"#e53935","Pending":"#f9a825"})
            f3.update_layout(**{**PB,"height":290})
            st.plotly_chart(f3,use_container_width=True)
        with cb:
            sec("Top 10 Complaint Types")
            tc=df["ComplaintType"].value_counts().head(10).reset_index(); tc.columns=["Type","Count"]
            f4=px.bar(tc,x="Count",y="Type",orientation="h",color="Count",color_continuous_scale=BLUE_S)
            f4.update_layout(**{**PB,"height":290},coloraxis_showscale=False,yaxis_categoryorder="total ascending")
            st.plotly_chart(f4,use_container_width=True)

        st.markdown("<div class='div'></div>", unsafe_allow_html=True)
        sec("🔍 Automated Insights")
        i1,i2,i3=st.columns(3)
        br=(df["SLAStatus"]=="Breached").mean()*100
        rr=(df["ReopenCount"]>0).mean()*100
        opr=(df["Status"]=="Open").mean()*100
        with i1:
            st.markdown(f"""<div class="icard"><div class="badge {'b-red' if br>30 else 'b-amber'}">SLA BREACH</div>
              <div class="icard-t">{br:.1f}% Tickets Breached SLA</div>
              <div class="icard-b">{'🚨 Critical — over 30% breached.' if br>30 else '⚠ Moderate breach rate.'}</div></div>""", unsafe_allow_html=True)
        with i2:
            st.markdown(f"""<div class="icard" style="border-left-color:#0d9488"><div class="badge b-teal">REOPENS</div>
              <div class="icard-t">{rr:.1f}% Cases Reopened</div>
              <div class="icard-b">Reopen rate above 5% signals first-contact resolution failure.</div></div>""", unsafe_allow_html=True)
        with i3:
            c_="#e53935" if opr>20 else "#00895a"
            st.markdown(f"""<div class="icard" style="border-left-color:{c_}"><div class="badge {'b-red' if opr>20 else 'b-green'}">BACKLOG</div>
              <div class="icard-t">{opr:.1f}% Cases Still Open</div>
              <div class="icard-b">{'High backlog — activate triage protocols.' if opr>20 else 'Backlog under control.'}</div></div>""", unsafe_allow_html=True)

        st.markdown("---")
        st.subheader("🤖 CivicPulse AI Insights")
        if st.button("Generate AI Analysis", key="command_ai"):
            with st.spinner("Analyzing governance data..."):
                insights = generate_ai_insights(page_name="Command Center", df=df)
                render_ai_insight_cards(insights)





# ══════════════════════════════════════════════════════
    #  GEOSPATIAL
    # ══════════════════════════════════════════════════════
    elif page == "geo":
        st.markdown("""
        <div class="hero">
          <div class="hero-eye">🗺️ Geospatial Intelligence</div>
          <div class="hero-h">Telangana District Hotspot Mapper</div>
          <div class="hero-p">Interactive district boundary viewer with live complaint data — all sidebar filters applied. Select Agency, District, Year or Complaint Type to highlight relevant districts on the map.</div>
        </div>""", unsafe_allow_html=True)
        fbanner()

        # ── KPI Cards (filter-aware, same as other pages) ──────
        geo_total    = len(df)
        geo_closed   = (df["Status"] == "Closed").sum()
        geo_sla_ok   = (df["SLAStatus"] == "Within SLA").sum()
        geo_avg_res  = df["ResolutionDays"].mean()
        geo_avg_sent = df["SentimentScore"].mean()
        geo_districts = df["Borough"].nunique()

        gk1, gk2, gk3, gk4, gk5, gk6 = st.columns(6)
        with gk1: kpi("Total Complaints", f"{geo_total:,}", "Filtered records", "#1565c0", "📋")
        with gk2: kpi("Districts Active", f"{geo_districts}", "With complaints", "#00897b", "🗺️")
        with gk3: kpi("Resolved Cases",  f"{geo_closed:,}", f"{geo_closed/geo_total*100:.1f}% resolved", "#00895a", "✅")
        with gk4: kpi("SLA Compliance",  f"{geo_sla_ok/geo_total*100:.1f}%", f"{geo_sla_ok:,} within target", "#5e35b1", "🎯")
        with gk5: kpi("Avg Resolution",  f"{geo_avg_res:.1f}d", "Mean days to close", "#d97706", "⏱️")
        with gk6: kpi("Sentiment Index", f"{geo_avg_sent:+.2f}", "−1 negative · +1 positive",
                      "#00895a" if geo_avg_sent > 0 else "#e53935", "💬")

        st.markdown("<br>", unsafe_allow_html=True)

        # ── Load GeoJSON ────────────────────────────────────────
        with open("TELANGANA_DISTRICTS.geojson", "r", encoding="utf-8") as f:
            local_geojson = json.load(f)

        # ── Build a normalised name → canonical Borough name map ─
        # Normalise: lowercase, strip spaces/hyphens/dots AND remove trailing "district"
        # so "Rangareddy District" == "rangareddy" == "Ranga Reddy"
        def _norm(s):
            s = s.lower().replace(" ", "").replace("-", "").replace(".", "")
            # Strip trailing "district" suffix (common in dataset Borough names)
            if s.endswith("district"):
                s = s[: -len("district")]
            return s.strip()

        # All Borough names that exist in the full (unfiltered) dataset
        all_boroughs = fact["Borough"].dropna().unique()
        # Dict: normalised → original Borough name
        norm_to_borough = {_norm(b): b for b in all_boroughs}

        # For each dtname in GeoJSON, find the best-matching Borough name
        geojson_dtnames = [f["properties"]["dtname"] for f in local_geojson["features"]]
        # dtname → matching Borough name (or None if no match found)
        dtname_to_borough = {}
        unmatched = []
        for dtname in geojson_dtnames:
            key = _norm(dtname)
            if key in norm_to_borough:
                dtname_to_borough[dtname] = norm_to_borough[key]
            else:
                # Fuzzy fallback: check if dtname normalised is a substring of any borough or vice-versa
                matched = None
                for nb, b in norm_to_borough.items():
                    if key in nb or nb in key:
                        matched = b
                        break
                dtname_to_borough[dtname] = matched  # None if truly unmatched
                if matched is None:
                    unmatched.append(dtname)

        # ── Derive active districts from filtered df ────────────
        # This set uses Borough names → we compare via dtname_to_borough mapping
        active_boroughs = set(df["Borough"].dropna().unique())

        # complaint count keyed by Borough name
        borough_counts = df.groupby("Borough").size().to_dict()
        max_count = max(borough_counts.values()) if borough_counts else 1

        # ── Helper: look up complaint count for a GeoJSON feature ─
        def get_count_for_dtname(dtname):
            borough = dtname_to_borough.get(dtname)
            if borough is None:
                return 0
            return borough_counts.get(borough, 0)

        def is_active_dtname(dtname):
            borough = dtname_to_borough.get(dtname)
            if borough is None:
                return False
            return borough in active_boroughs

        # ── Color scale: more complaints → deeper blue ──────────
        def complaint_color(count):
            if count == 0:
                return "#94a3b8"
            ratio = count / max_count
            if ratio > 0.75:
                return "#0a2540"
            elif ratio > 0.5:
                return "#1565c0"
            elif ratio > 0.25:
                return "#1e88e5"
            else:
                return "#64b5f6"

        # ── Enrich GeoJSON features with complaint_count property ─
        # This allows the tooltip to display counts without extra markers
        for feat in local_geojson["features"]:
            dtname = feat["properties"]["dtname"]
            cnt = get_count_for_dtname(dtname)
            feat["properties"]["complaint_count"] = f"{cnt:,}" if cnt > 0 else "No data"
            feat["properties"]["is_active"] = "Yes" if is_active_dtname(dtname) else "No"

        # ── Style function using the mapping ────────────────────
        def style_map(feature):
            dtname = feature["properties"]["dtname"]
            active = is_active_dtname(dtname)
            count  = get_count_for_dtname(dtname)

            if filters_active and not active:
                # Filters applied but this district has no matching data → grey out
                return {
                    "fillColor":   "#e2e8f0",
                    "color":       "#cbd5e1",
                    "weight":      0.6,
                    "fillOpacity": 0.10,
                }
            return {
                "fillColor":   complaint_color(count),
                "color":       "#1e3a8a",
                "weight":      1.8,
                "fillOpacity": 0.55 if active else 0.20,
            }

        # ── Build map ───────────────────────────────────────────
        sec("Interactive District Map", "Districts highlighted based on all active sidebar filters — hover for details")
        st.markdown('<div class="map-card" style="padding: 10px; background: white; border-radius: 8px; box-shadow: 0 4px 6px -1px rgb(0 0 0 / 0.1);">', unsafe_allow_html=True)

        m = folium.Map(location=[17.55, 78.95], zoom_start=7.5, tiles="cartodbpositron")

        folium.GeoJson(
            local_geojson,
            name="Telangana Districts",
            style_function=style_map,
            highlight_function=lambda x: {
                "fillColor":   "#f59e0b",
                "fillOpacity": 0.70,
                "weight":      2.5,
                "color":       "#b45309",
            },
            tooltip=folium.GeoJsonTooltip(
                fields=["dtname", "complaint_count"],
                aliases=["District:", "Complaints:"],
                localize=True,
                style=(
                    "font-family: 'Plus Jakarta Sans', sans-serif; font-size: 13px; "
                    "padding: 10px 14px; border-radius: 8px; "
                    "background: #0a2540; color: #e0f2fe; border: 1px solid #1e3a8a;"
                ),
            ),
        ).add_to(m)

        # ── Circle markers at district centroids (active only) ──
        for feat in local_geojson["features"]:
            dtname = feat["properties"]["dtname"]
            if not is_active_dtname(dtname):
                continue
            count = get_count_for_dtname(dtname)
            borough = dtname_to_borough.get(dtname, dtname)

            # Compute centroid by averaging all polygon ring coordinates
            geom = feat["geometry"]
            if geom["type"] == "Polygon":
                ring = geom["coordinates"][0]
            else:  # MultiPolygon — use the first (largest by point count) ring
                ring = max(geom["coordinates"], key=lambda p: len(p[0]))[0]
            lat = sum(pt[1] for pt in ring) / len(ring)
            lon = sum(pt[0] for pt in ring) / len(ring)

            radius = max(6, min(22, int(count / max_count * 24)))
            folium.CircleMarker(
                location=[lat, lon],
                radius=radius,
                color="#ffffff",
                weight=1.5,
                fill=True,
                fill_color="#f59e0b",
                fill_opacity=0.85,
                tooltip=(
                    f"<b style='color:#0a2540'>{borough}</b><br>"
                    f"<span style='color:#1565c0'>{count:,} complaints</span>"
                ),
            ).add_to(m)

        st_folium(m, width="100%", height=560, returned_objects=[])
        st.markdown('</div>', unsafe_allow_html=True)

        # ── Extra Geospatial Visuals ──────────────────────────
        gdf = df.copy()
        if "Neighborhood" not in gdf.columns:
            gdf["Neighborhood"] = gdf.get("ZipCode", "Unknown").astype(str)
        if "SeverityScore" not in gdf.columns:
            gdf["SeverityScore"] = np.random.uniform(1, 5, len(gdf))
        if "SentimentScore" not in gdf.columns:
            gdf["SentimentScore"] = np.random.uniform(-1, 1, len(gdf))

        top_n = gdf["Neighborhood"].value_counts().head(10).index
        top_c = gdf["ComplaintType"].value_counts().head(8).index

        st.markdown("<div class='div'></div>", unsafe_allow_html=True)
        m1, m2 = st.columns(2)
        with m1:
            sec("Top 15 Neighbourhoods by Complaint Volume")
            nb_vol = gdf.groupby("Neighborhood").size().nlargest(15).reset_index(name="Complaints").sort_values("Complaints")
            fig_nb = px.bar(nb_vol, x="Complaints", y="Neighborhood", orientation="h",
                            color="Complaints", color_continuous_scale=TEAL_S)
            fig_nb.update_layout(**{**PB, "height": 460}, coloraxis_showscale=False,
                                 yaxis_categoryorder="total ascending", yaxis_title="")
            st.plotly_chart(fig_nb, use_container_width=True)
        with m2:
            sec("Top Complaint Types by Neighbourhood")
            ht = gdf[gdf["Neighborhood"].isin(top_n) & gdf["ComplaintType"].isin(top_c)]
            ht_agg = ht.groupby(["Neighborhood", "ComplaintType"]).size().reset_index(name="Count")
            fig_ht = px.density_heatmap(ht_agg, x="Neighborhood", y="ComplaintType", z="Count",
                color_continuous_scale=[[0, "#f0f9ff"], [0.5, "#38bdf8"], [1, "#0369a1"]])
            fig_ht.update_layout(**{**PB, "height": 460}, xaxis_tickangle=-35)
            st.plotly_chart(fig_ht, use_container_width=True)

        st.markdown("<div class='div'></div>", unsafe_allow_html=True)
        d1, d2 = st.columns(2)
        with d1:
            sec("Complaint Volume by District")
            bct = gdf.groupby("Borough").size().reset_index(name="Count").sort_values("Count", ascending=True)
            fig_bct = px.bar(bct, x="Count", y="Borough", orientation="h",
                             color="Count", color_continuous_scale=VIOLET_S)
            fig_bct.update_layout(**{**PB, "height": 360}, coloraxis_showscale=False,
                                  yaxis_title="", xaxis_title="Complaints")
            st.plotly_chart(fig_bct, use_container_width=True)
        with d2:
            sec("Complaint Bubble — Area × Type")
            bb = gdf[gdf["Neighborhood"].isin(top_n) & gdf["ComplaintType"].isin(top_c)]
            bb_agg = bb.groupby(["Neighborhood", "ComplaintType"]).agg(
                Count=("TicketID", "count"), AvgSev=("SeverityScore", "mean")).reset_index()
            fig_bub = px.scatter(bb_agg, x="Neighborhood", y="ComplaintType",
                size="Count", color="AvgSev",
                color_continuous_scale=[[0, "#059669"], [0.5, "#f59e0b"], [1, "#e11d48"]],
                size_max=38, hover_data={"Count": True, "AvgSev": ":.2f"})
            fig_bub.update_layout(**{**PB, "height": 360}, xaxis_tickangle=-30)
            st.plotly_chart(fig_bub, use_container_width=True)

        st.markdown("<div class='div'></div>", unsafe_allow_html=True)
        sec("District-Level Risk Summary")
        bsum = gdf.groupby("Borough").agg(
            Total_Complaints=("TicketID", "count"),
            Avg_Severity=("SeverityScore", "mean"),
            Avg_Resolution_Days=("ResolutionDays", "mean"),
            SLA_Breach_Pct=("SLAStatus", lambda x: (x == "Breached").mean() * 100),
            Avg_Sentiment=("SentimentScore", "mean")
        ).round(2).reset_index().sort_values("Total_Complaints", ascending=False)
        st.dataframe(bsum, use_container_width=True, hide_index=True)

        st.markdown("<div class='div'></div>", unsafe_allow_html=True)
        sec("🔍 Geospatial Insights")
        gi1, gi2 = st.columns(2)
        tb = bsum.iloc[0]
        wb = bsum.loc[bsum["Avg_Sentiment"].idxmin()]
        with gi1:
            st.markdown(f"""<div class="icard">
              <div class="badge b-red">VOLUME HOTSPOT</div>
              <div class="icard-t">{tb['Borough']} — Highest Complaint Density</div>
              <div class="icard-b"><b style="color:#0f1c2e">{int(tb['Total_Complaints']):,} complaints</b>,
              avg severity <b style="color:#d97706">{tb['Avg_Severity']:.2f}</b>,
              SLA breach <b style="color:#e11d48">{tb['SLA_Breach_Pct']:.1f}%</b>.</div>
            </div>""", unsafe_allow_html=True)
        with gi2:
            st.markdown(f"""<div class="icard" style="border-left-color:#e11d48">
              <div class="badge b-red">SENTIMENT ALERT</div>
              <div class="icard-t">{wb['Borough']} — Most Dissatisfied Citizens</div>
              <div class="icard-b">Avg sentiment <b style="color:#e11d48">{wb['Avg_Sentiment']:+.3f}</b>.
              Avg resolution <b style="color:#0f1c2e">{wb['Avg_Resolution_Days']:.1f} days</b>.</div>
            </div>""", unsafe_allow_html=True)

        st.markdown("---")
        st.subheader("🗺️ AI Geo Intelligence")
        if st.button("Analyze Hotspots", key="geo_ai"):
            with st.spinner("Detecting hotspot patterns..."):
                insights = generate_ai_insights(page_name="Geospatial Analysis", df=df)
                render_ai_insight_cards(insights)

    # ══════════════════════════════════════════════════════
    #  SLA TRACKER
    # ══════════════════════════════════════════════════════
    elif page == "sla":
        st.markdown("""
        <div class="hero">
          <div class="hero-eye">🏢 Departmental Accountability</div>
          <div class="hero-h">SLA Performance Tracker</div>
          <div class="hero-p">Hold agencies accountable — resolution time, breach rates, efficiency.</div>
        </div>""", unsafe_allow_html=True)
        fbanner()

        if "SLAGoalDays" not in df.columns:
            ac=[c for c in agency.columns if c in ["AgencyName","SLAGoalDays"]]
            adf=df.merge(agency[ac],on="AgencyName",how="left")
        else:
            adf=df.copy()
        if "SLAGoalDays" not in adf.columns:
            adf["SLAGoalDays"]=7

        ap=adf.groupby("AgencyName").agg(
            Total=("TicketID","count"),Avg_Resolution=("ResolutionDays","mean"),
            SLA_Breached=("SLAStatus",lambda x:(x=="Breached").sum()),
            SLA_Goal=("SLAGoalDays","first"),Avg_Sentiment=("SentimentScore","mean"),
            Avg_Cost=("CostEstimate","mean")
        ).reset_index()
        ap["Breach_Rate"]=(ap["SLA_Breached"]/ap["Total"]*100).round(1)
        ap["Avg_Resolution"]=ap["Avg_Resolution"].round(1)

        c1,c2=st.columns(2)
        with c1:
            sec("Avg Resolution Time vs. SLA Target")
            t20=ap.nlargest(15,"Total")
            fb=go.Figure()
            fb.add_trace(go.Bar(name="Avg Resolution (Days)",x=t20["AgencyName"],y=t20["Avg_Resolution"],
                marker_color="#1565c0",opacity=0.85,marker_line_width=0))
            fb.add_trace(go.Scatter(name="SLA Target",x=t20["AgencyName"],y=t20["SLA_Goal"],
                mode="markers+lines",marker=dict(color="#00bcd4",size=9,symbol="diamond"),
                line=dict(color="#00897b",dash="dot",width=1.5)))
            fb.update_layout(**{**PB,"height":370},xaxis_tickangle=-35,barmode="group",legend_orientation="h",legend_y=-0.28)
            st.plotly_chart(fb,use_container_width=True)
        with c2:
            sec("Complexity vs. Efficiency Scatter")
            fs=px.scatter(ap,x="Total",y="Avg_Resolution",size="Breach_Rate",color="Avg_Sentiment",
                text="AgencyName",color_continuous_scale=SENT,size_max=42,hover_data={"Breach_Rate":True})
            fs.update_traces(textposition="top center",textfont=dict(size=9,color="#3d5068"))
            fs.update_layout(**{**PB,"height":370},xaxis_title="Ticket Volume",yaxis_title="Avg Resolution Days",
                coloraxis_colorbar=dict(title="Sentiment",tickfont_color="#3d5068",title_font_color="#3d5068",bgcolor="rgba(255,255,255,0.9)"))
            st.plotly_chart(fs,use_container_width=True)

        st.markdown("<div class='div'></div>", unsafe_allow_html=True)
        sec("Agency × SLA Status Matrix")
        mx=pd.crosstab(df["AgencyName"],df["SLAStatus"])
        mx["Total"]=mx.sum(axis=1)
        st.dataframe(mx.sort_values("Total",ascending=False),use_container_width=True)

        st.markdown("<div class='div'></div>", unsafe_allow_html=True)
        sec("Agency SLA Breach Rate (%)")
        bbr=ap.sort_values("Breach_Rate",ascending=True)
        fbr=px.bar(bbr,x="Breach_Rate",y="AgencyName",orientation="h",
                   color="Breach_Rate",color_continuous_scale=[[0,"#00897b"],[0.5,"#f9a825"],[1,"#e53935"]])
        fbr.update_layout(**{**PB,"height":440},coloraxis_showscale=False,xaxis_title="Breach Rate (%)",yaxis_title="")
        st.plotly_chart(fbr,use_container_width=True)

        st.markdown("<div class='div'></div>", unsafe_allow_html=True)
        sec("🔍 Departmental Insights")
        slowest=ap.loc[ap["Avg_Resolution"].idxmax()]
        hb=ap.loc[ap["Breach_Rate"].idxmax()]
        mn=ap.loc[ap["Avg_Sentiment"].idxmin()]
        mhv=ap["Total"]>=ap["Total"].quantile(0.5)
        eff=ap.loc[mhv&(ap["Avg_Resolution"]==ap.loc[mhv,"Avg_Resolution"].min())].iloc[0]
        s1,s2,s3,s4=st.columns(4)
        with s1: st.markdown(f"""<div class="icard"><div class="badge b-red">SLOWEST</div><div class="icard-t">{slowest['AgencyName']}</div><div class="icard-b">{slowest['Avg_Resolution']:.1f} avg days vs {slowest['SLA_Goal']:.0f}d target.</div></div>""", unsafe_allow_html=True)
        with s2: st.markdown(f"""<div class="icard" style="border-left-color:#e11d48"><div class="badge b-red">MOST BREACHES</div><div class="icard-t">{hb['AgencyName']}</div><div class="icard-b">{hb['Breach_Rate']:.1f}% breach on {int(hb['Total']):,} tickets.</div></div>""", unsafe_allow_html=True)
        with s3: st.markdown(f"""<div class="icard" style="border-left-color:#7c3aed"><div class="badge b-violet">SENTIMENT</div><div class="icard-t">{mn['AgencyName']}</div><div class="icard-b">Avg sentiment {mn['Avg_Sentiment']:+.3f}.</div></div>""", unsafe_allow_html=True)
        with s4: st.markdown(f"""<div class="icard" style="border-left-color:#059669"><div class="badge b-green">TOP PERFORMER</div><div class="icard-t">{eff['AgencyName']}</div><div class="icard-b">{eff['Avg_Resolution']:.1f} avg days on high volume.</div></div>""", unsafe_allow_html=True)

        st.markdown("---")
        st.subheader("🏢 AI SLA Intelligence")
        if st.button("Analyze SLA Performance", key="sla_ai"):
            with st.spinner("Analyzing SLA and agency data..."):
                insights = generate_ai_insights(page_name="SLA Tracker", df=df)
                render_ai_insight_cards(insights)

    # ══════════════════════════════════════════════════════
    #  SENTIMENT & NLP
    # ══════════════════════════════════════════════════════
    elif page == "nlp":
        st.markdown("""
        <div class="hero">
          <div class="hero-eye">💬 Citizen Voice Intelligence</div>
          <div class="hero-h">Sentiment & NLP Analysis</div>
          <div class="hero-p">Sentiment distribution, keyword frequency, trend lines, decomposition trees.</div>
        </div>""", unsafe_allow_html=True)
        fbanner()

        avg_sent=df["SentimentScore"].mean()
        pos_pct=(df["SentimentScore"]>0.1).mean()*100
        neg_pct=(df["SentimentScore"]<-0.1).mean()*100
        neu_pct=100-pos_pct-neg_pct

        c1,c2,c3,c4=st.columns(4)
        with c1: kpi("Sentiment Index",f"{avg_sent:+.3f}","−1 Negative · +1 Positive","#00895a" if avg_sent>0 else "#e53935","🧭")
        with c2: kpi("Positive",f"{pos_pct:.1f}%","Score > 0.1","#00895a","😊")
        with c3: kpi("Neutral",f"{neu_pct:.1f}%","−0.1 to 0.1","#d97706","😐")
        with c4: kpi("Negative",f"{neg_pct:.1f}%","Score < −0.1","#e53935","😞")

        st.markdown("<br>", unsafe_allow_html=True)
        cg,cd=st.columns([1,2])
        with cg:
            sec("Sentiment Gauge")
            fig_g=go.Figure(go.Indicator(
                mode="gauge+number+delta",value=avg_sent,
                delta={"reference":0,"valueformat":".3f"},
                title={"text":"Avg Sentiment","font":{"color":"#7a8fa6","size":12,"family":"Plus Jakarta Sans"}},
                number={"font":{"color":"#0f1c2e","size":26,"family":"Lora"},"valueformat":"+.3f"},
                gauge={"axis":{"range":[-1,1],"tickcolor":"#dde3ec","tickfont":{"color":"#7a8fa6","size":9}},
                       "bar":{"color":"#1565c0","thickness":0.28},"bgcolor":"#ffffff",
                       "bordercolor":"#dde3ec","borderwidth":1,
                       "steps":[{"range":[-1,-0.3],"color":"rgba(225,29,72,0.1)"},
                                 {"range":[-0.3,0.3],"color":"rgba(217,119,6,0.07)"},
                                 {"range":[0.3,1],"color":"rgba(5,150,105,0.1)"}],
                       "threshold":{"line":{"color":"#00bcd4","width":3},"value":avg_sent}}))
            fig_g.update_layout(paper_bgcolor="rgba(0,0,0,0)",font=dict(color="#7a8fa6",family="Plus Jakarta Sans"),
                                 height=280,margin=dict(l=25,r=25,t=35,b=10))
            st.plotly_chart(fig_g,use_container_width=True)
            zone="🟢 Positive Zone" if avg_sent>0.2 else ("🔴 Negative Zone" if avg_sent<-0.2 else "🟡 Neutral Zone")
            st.markdown(f"""<div style="text-align:center;padding:.65rem;background:#f8fafc;
            border-radius:10px;border:1px solid #dde3ec;font-family:'Lora',serif;
            font-size:.95rem;font-weight:700;color:#0f1c2e;">{zone}</div>""", unsafe_allow_html=True)

            st.markdown("<br>", unsafe_allow_html=True)
            sec("Sentiment Breakdown")
            pie_df=pd.DataFrame({"Zone":["Positive","Neutral","Negative"],"Pct":[pos_pct,neu_pct,neg_pct]})
            fig_pie=go.Figure(go.Pie(labels=pie_df["Zone"],values=pie_df["Pct"],hole=0.55,
                marker_colors=["#00895a","#d97706","#e53935"],textinfo="label+percent",
                textfont=dict(color="#3d5068",size=10)))
            fig_pie.update_layout(**{**PB,"height":220},showlegend=False)
            st.plotly_chart(fig_pie,use_container_width=True)

        with cd:
            sec("Sentiment Score Distribution by Agency")
            top_ag=df.groupby("AgencyName").size().nlargest(10).index
            sag=df[df["AgencyName"].isin(top_ag)]
            fig_box=px.box(sag,x="AgencyName",y="SentimentScore",color="AgencyName",color_discrete_sequence=C)
            fig_box.add_hline(y=0,line_dash="dot",line_color="#dde3ec",line_width=1.5)
            fig_box.update_layout(**{**PB,"height":420},showlegend=False,xaxis_tickangle=-30)
            st.plotly_chart(fig_box,use_container_width=True)

        st.markdown("<div class='div'></div>", unsafe_allow_html=True)
        cw,ct_col=st.columns(2)
        with cw:
            sec("Most Frequent Complaint Keywords")
            words=[]
            for t in df["ComplaintType"].dropna():
                words.extend(t.lower().replace("-"," ").split())
            stop={"of","in","on","the","a","and","to","for","by","is","at","or","an","not","from"}
            wf=Counter([w for w in words if w not in stop and len(w)>2])
            tw=pd.DataFrame(wf.most_common(20),columns=["Word","Count"])
            fig_kw=px.bar(tw,x="Count",y="Word",orientation="h",color="Count",color_continuous_scale=VIOLET_S)
            fig_kw.update_layout(**{**PB,"height":400},coloraxis_showscale=False,yaxis_categoryorder="total ascending")
            st.plotly_chart(fig_kw,use_container_width=True)
        with ct_col:
            sec("Monthly Avg Sentiment Trend")
            st_df=df.groupby(["Year","Month"])["SentimentScore"].mean().reset_index()
            mof=["January","February","March","April","May","June","July","August","September","October","November","December"]
            st_df["mn"]=st_df["Month"].apply(lambda m:mof.index(m)+1 if m in mof else 0)
            st_df=st_df.sort_values(["Year","mn"])
            st_df["Period"]=st_df["Year"].astype(str)+"-"+st_df["Month"].str[:3]
            fig_tr=go.Figure()
            fig_tr.add_hrect(y0=-0.1,y1=0.1,fillcolor="rgba(217,119,6,0.05)",line_width=0)
            fig_tr.add_trace(go.Scatter(x=st_df["Period"],y=st_df["SentimentScore"],
                mode="lines+markers",line=dict(color="#1565c0",width=2.5),
                marker=dict(color="#00bcd4",size=5.5),fill="tozeroy",fillcolor="rgba(37,99,235,0.05)"))
            fig_tr.add_hline(y=0,line_dash="dash",line_color="#dde3ec",line_width=1.5)
            fig_tr.update_layout(**{**PB,"height":210},xaxis_tickangle=-40,xaxis_nticks=24)
            st.plotly_chart(fig_tr,use_container_width=True)

            sec("Avg Sentiment by Year")
            sy=df.groupby("Year")["SentimentScore"].mean().reset_index()
            fig_sy=px.bar(sy,x="Year",y="SentimentScore",color="SentimentScore",color_continuous_scale=SENT)
            fig_sy.add_hline(y=0,line_dash="dot",line_color="#dde3ec",line_width=1.2)
            fig_sy.update_layout(**{**PB,"height":180},coloraxis_showscale=False)
            st.plotly_chart(fig_sy,use_container_width=True)

        st.markdown("<div class='div'></div>", unsafe_allow_html=True)
        sec("Decomposition Tree: Poor Sentiment by Agency → Complaint Type")
        ba=df.groupby("AgencyName")["SentimentScore"].mean().nsmallest(6).index
        dec=df[df["AgencyName"].isin(ba)].groupby(["AgencyName","ComplaintType"])["SentimentScore"].mean().reset_index()
        dec=dec.sort_values("SentimentScore").head(24)
        fig_dc=px.treemap(dec,path=["AgencyName","ComplaintType"],values=dec["SentimentScore"].abs(),
                          color="SentimentScore",color_continuous_scale=SENT,range_color=[-1,0])
        fig_dc.update_layout(paper_bgcolor="rgba(0,0,0,0)",margin=dict(l=0,r=0,t=20,b=0),height=340,
            coloraxis_colorbar=dict(tickfont_color="#3d5068",bgcolor="rgba(255,255,255,0.9)"))
        st.plotly_chart(fig_dc,use_container_width=True)

        st.markdown("<div class='div'></div>", unsafe_allow_html=True)
        sec("🔍 Sentiment Insights")
        wa=df.groupby("AgencyName")["SentimentScore"].mean().idxmin()
        wt=df.groupby("ComplaintType")["SentimentScore"].mean().idxmin()
        ba2=df.groupby("AgencyName")["SentimentScore"].mean().idxmax()
        bv=df.groupby("AgencyName")["SentimentScore"].mean().max()
        n1,n2,n3=st.columns(3)
        with n1: st.markdown(f"""<div class="icard" style="border-left-color:#e11d48"><div class="badge b-red">LOW SATISFACTION</div><div class="icard-t">Most Disliked: {wa}</div><div class="icard-b">Most negative language about this agency.</div></div>""", unsafe_allow_html=True)
        with n2: st.markdown(f"""<div class="icard" style="border-left-color:#d97706"><div class="badge b-amber">PAIN POINT</div><div class="icard-t">{wt[:35]}...</div><div class="icard-b">Highest negativity complaint type.</div></div>""", unsafe_allow_html=True)
        with n3: st.markdown(f"""<div class="icard" style="border-left-color:#059669"><div class="badge b-green">BENCHMARK</div><div class="icard-t">Best Agency: {ba2}</div><div class="icard-b">Avg sentiment {bv:+.3f}. Replicate this model.</div></div>""", unsafe_allow_html=True)

        st.markdown("---")
        st.subheader("💬 AI Sentiment Intelligence")
        if st.button("Analyze Citizen Sentiment", key="nlp_ai"):
            with st.spinner("Analyzing sentiment patterns..."):
                insights = generate_ai_insights(page_name="Citizen Sentiment", df=df)
                render_ai_insight_cards(insights)

    # ══════════════════════════════════════════════════════
    #  AI INSIGHTS
    # ══════════════════════════════════════════════════════
    elif page == "ai":
        st.markdown("""
        <div class="hero">
          <div class="hero-eye">🤖 Data-Driven Intelligence Engine</div>
          <div class="hero-h">AI Insights & Recommendations</div>
          <div class="hero-p">Deep problem-solution analysis drawn from all modules.</div>
        </div>""", unsafe_allow_html=True)
        fbanner()

        total=len(df); closed_pct=(df["Status"]=="Closed").mean()*100
        open_pct=(df["Status"]=="Open").mean()*100; pending_pct=(df["Status"]=="Pending").mean()*100
        breach_pct=(df["SLAStatus"]=="Breached").mean()*100; within_pct=(df["SLAStatus"]=="Within SLA").mean()*100
        avg_res=df["ResolutionDays"].mean(); avg_sent=df["SentimentScore"].mean()
        reopen_pct=(df["ReopenCount"]>0).mean()*100
        total_cost=df["CostEstimate"].sum(); pos_pct_ai=(df["SentimentScore"]>0.1).mean()*100
        neg_pct_ai=(df["SentimentScore"]<-0.1).mean()*100

        ag_res=df.groupby("AgencyName")["ResolutionDays"].mean()
        ag_br=df.groupby("AgencyName").apply(lambda x:(x["SLAStatus"]=="Breached").mean()*100)
        ag_sent=df.groupby("AgencyName")["SentimentScore"].mean()
        ag_vol=df.groupby("AgencyName").size()
        ag_cost=df.groupby("AgencyName")["CostEstimate"].mean()
        ag_reop=df.groupby("AgencyName").apply(lambda x:(x["ReopenCount"]>0).mean()*100)
        ct_vol=df.groupby("ComplaintType").size(); ct_res=df.groupby("ComplaintType")["ResolutionDays"].mean()
        ct_sent=df.groupby("ComplaintType")["SentimentScore"].mean()
        ct_sev=df.groupby("ComplaintType")["SeverityScore"].mean()
        ct_br=df.groupby("ComplaintType").apply(lambda x:(x["SLAStatus"]=="Breached").mean()*100)
        bor_vol=df.groupby("Borough").size()
        bor_br=df.groupby("Borough").apply(lambda x:(x["SLAStatus"]=="Breached").mean()*100)
        bor_sent=df.groupby("Borough")["SentimentScore"].mean()
        bor_res=df.groupby("Borough")["ResolutionDays"].mean()
        yr_vol=df.groupby("Year").size()
        yr_br=df.groupby("Year").apply(lambda x:(x["SLAStatus"]=="Breached").mean()*100)

        slowest_ag=ag_res.idxmax(); slowest_days=ag_res.max()
        fastest_ag=ag_res.idxmin(); fastest_days=ag_res.min()
        highest_br_ag=ag_br.idxmax(); highest_br_pct=ag_br.max()
        lowest_br_ag=ag_br.idxmin(); lowest_br_pct=ag_br.min()
        worst_sent_ag=ag_sent.idxmin(); worst_sent_v=ag_sent.min()
        best_sent_ag=ag_sent.idxmax(); best_sent_v=ag_sent.max()
        highest_vol_ag=ag_vol.idxmax(); highest_vol_v=ag_vol.max()
        highest_reop_ag=ag_reop.idxmax(); highest_reop_v=ag_reop.max()
        worst_ct=ct_sent.idxmin(); worst_ct_s=ct_sent.min()
        top_ct=ct_vol.idxmax(); top_ct_v=ct_vol.max()
        slowest_ct=ct_res.idxmax(); slowest_ct_d=ct_res.max()
        highest_br_ct=ct_br.idxmax(); highest_br_ct_v=ct_br.max()
        hottest_bor=bor_vol.idxmax(); hottest_bor_v=bor_vol.max()
        worst_bor_sent=bor_sent.idxmin(); worst_bor_sv=bor_sent.min()
        highest_br_bor=bor_br.idxmax(); highest_br_bor_v=bor_br.max()
        slowest_bor=bor_res.idxmax(); slowest_bor_d=bor_res.max()
        trend_dir="increasing" if yr_vol.iloc[-1]>yr_vol.iloc[0] else "decreasing"
        breach_trend="worsening" if yr_br.iloc[-1]>yr_br.iloc[0] else "improving"
        high_cost_ag=ag_cost.idxmax(); high_cost_v=ag_cost.max()
        low_cost_ag=ag_cost.idxmin(); low_cost_v=ag_cost.min()

        # Resolved vs Unresolved
        st.markdown("""<div class="ai-section-header">
          <h3>✅ Resolved vs Unresolved: What's Fixed & What's Not</h3>
          <p>Full breakdown of case outcomes, SLA compliance, and root-cause analysis</p>
        </div>""", unsafe_allow_html=True)

        closed_n=(df["Status"]=="Closed").sum()
        open_n=(df["Status"]=="Open").sum()
        pending_n=(df["Status"]=="Pending").sum()

        rv1,rv2,rv3,rv4,rv5=st.columns(5)
        with rv1: kpi("Total Complaints",f"{total:,}","All filtered records","#1565c0","📋")
        with rv2: kpi("✅ Resolved",f"{closed_n:,}",f"{closed_pct:.1f}% closed","#00895a","✅")
        with rv3: kpi("🔴 Open",f"{open_n:,}",f"{open_pct:.1f}% of total","#e53935","🔴")
        with rv4: kpi("🟡 Pending",f"{pending_n:,}",f"{pending_pct:.1f}% in queue","#d97706","⏳")
        with rv5: kpi("🔄 Reopened",f"{(df['ReopenCount']>0).sum():,}",f"{reopen_pct:.1f}% reopen rate","#5e35b1","🔄")

        st.markdown("<br>", unsafe_allow_html=True)
        sv_l,sv_r=st.columns([3,2])
        with sv_l:
            sec("Resolved vs Unresolved by Agency")
            ag_status=df.groupby(["AgencyName","Status"]).size().reset_index(name="Count")
            ag_totals=ag_status.groupby("AgencyName")["Count"].sum().sort_values(ascending=True)
            fig_sv=px.bar(ag_status,y="AgencyName",x="Count",color="Status",orientation="h",barmode="stack",
                          color_discrete_map={"Closed":"#00897b","Open":"#e53935","Pending":"#f9a825"},
                          category_orders={"AgencyName":list(ag_totals.index)})
            fig_sv.update_layout(**{**PB,"height":420},yaxis_title="",xaxis_title="Complaints",legend_orientation="h",legend_y=-0.12,bargap=0.25)
            st.plotly_chart(fig_sv,use_container_width=True)
        with sv_r:
            sec("Why Cases Stay Unresolved")
            unresolved=df[df["Status"]!="Closed"]
            reasons=[]
            reasons.append({"Reason":"SLA Already Breached","Count":int((unresolved["SLAStatus"]=="Breached").sum()),"Color":"#e53935","Icon":"🚨"})
            if "SeverityScore" in unresolved.columns:
                reasons.append({"Reason":"High Severity (Score ≥7)","Count":int((unresolved["SeverityScore"]>=7).sum()),"Color":"#d97706","Icon":"⚡"})
            reasons.append({"Reason":"Reopened & Still Open","Count":int((unresolved["ReopenCount"]>0).sum()),"Color":"#5e35b1","Icon":"🔄"})
            try:
                age=(pd.Timestamp.now()-pd.to_datetime(unresolved["CreatedDate"])).dt.days
                reasons.append({"Reason":f"Age > 2× Avg ({avg_res*2:.0f}d)","Count":int((age>avg_res*2).sum()),"Color":"#0891b2","Icon":"📅"})
            except: pass
            if len(unresolved)>0:
                top_open_ct=unresolved["ComplaintType"].value_counts().idxmax()
                top_open_ct_n=unresolved["ComplaintType"].value_counts().max()
                reasons.append({"Reason":f'Top Stuck: {top_open_ct[:22]}…',"Count":int(top_open_ct_n),"Color":"#00895a","Icon":"📂"})
            for r in reasons:
                pct_of_unresolved=r["Count"]/len(unresolved)*100 if len(unresolved)>0 else 0
                st.markdown(f"""<div style="display:flex;justify-content:space-between;align-items:center;
                padding:.7rem 1rem;background:#f8fafc;border:1px solid #dde3ec;
                border-left:3px solid {r['Color']};border-radius:9px;margin-bottom:.5rem;">
                  <div>
                    <div style="font-size:.82rem;font-weight:700;color:#0f1c2e;">{r['Icon']} {r['Reason']}</div>
                    <div style="font-size:.68rem;color:#7a8fa6;font-family:'JetBrains Mono',monospace;">{pct_of_unresolved:.1f}% of unresolved</div>
                  </div>
                  <div style="font-family:'Lora',serif;font-size:1.15rem;font-weight:700;color:{r['Color']};">{r['Count']:,}</div>
                </div>""", unsafe_allow_html=True)

            fig_res=go.Figure(go.Pie(labels=["Resolved","Open","Pending"],values=[closed_n,open_n,pending_n],
                hole=0.68,marker_colors=["#00895a","#e53935","#d97706"],textinfo="label+percent",textfont=dict(color="#3d5068",size=10)))
            fig_res.update_layout(**{**PB,"height":200},
                annotations=[dict(text=f"<b>{closed_pct:.0f}%</b><br>Closed",x=0.5,y=0.5,font=dict(size=14,color="#0f1c2e"),showarrow=False)])
            st.plotly_chart(fig_res,use_container_width=True)

        st.markdown("<div class='div'></div>", unsafe_allow_html=True)
        sec("SLA Compliance by Complaint Type (Top 12)")
        top12_ct=ct_vol.nlargest(12).index
        sla_ct=df[df["ComplaintType"].isin(top12_ct)].groupby(["ComplaintType","SLAStatus"]).size().reset_index(name="Count")
        fig_sla_ct=px.bar(sla_ct,x="ComplaintType",y="Count",color="SLAStatus",barmode="stack",
                          color_discrete_map={"Within SLA":"#00895a","Breached":"#e53935","Unknown":"#d97706"})
        fig_sla_ct.update_layout(**{**PB,"height":300},xaxis_tickangle=-30,legend_orientation="h",legend_y=-0.2)
        st.plotly_chart(fig_sla_ct,use_container_width=True)

        # Module tabs
        st.markdown("""<div class="ai-section-header">
          <h3>🔬 Module-Wise Insights: Problems & Recommended Solutions</h3>
          <p>Command Centre · Geospatial · SLA Tracker · Sentiment & NLP</p>
        </div>""", unsafe_allow_html=True)

        tab1,tab2,tab3,tab4=st.tabs(["📊 Command Centre","🗺️ Geospatial Hotspots","🏢 Department SLA","💬 Sentiment & NLP"])

        with tab1:
            st.markdown("<br>", unsafe_allow_html=True)
            yr_vol_df2=df.groupby("Year").size().reset_index(name="Volume")
            yr_sla2=df.groupby("Year").apply(lambda x:(x["SLAStatus"]=="Breached").mean()*100).reset_index()
            yr_sla2.columns=["Year","Breach_Rate"]
            yr_merged2=yr_sla2.merge(yr_vol_df2,on="Year")
            fig_cmd=go.Figure()
            fig_cmd.add_trace(go.Bar(x=yr_merged2["Year"],y=yr_merged2["Volume"],name="Total Complaints",marker_color="rgba(37,99,235,0.15)",yaxis="y2"))
            fig_cmd.add_trace(go.Scatter(x=yr_merged2["Year"],y=yr_merged2["Breach_Rate"],name="Breach Rate %",mode="lines+markers+text",line=dict(color="#e53935",width=3),marker=dict(size=10,color="#e53935"),text=yr_merged2["Breach_Rate"].round(1).astype(str)+"%",textposition="top center",textfont=dict(color="#e53935",size=11)))
            PB2={k:v for k,v in PB.items() if k not in ("xaxis","yaxis")}
            fig_cmd.update_layout(**{**PB2,"height":260},legend_orientation="h",legend_y=-0.2,
                yaxis=dict(title="Breach Rate %",gridcolor="#eef2f7",tickfont=dict(color="#7a8fa6",size=10),linecolor="#dde3ec",zerolinecolor="#dde3ec"),
                yaxis2=dict(title="Total Complaints",overlaying="y",side="right",tickfont=dict(color="#3b82f6",size=10),linecolor="#dde3ec",showgrid=False),
                xaxis=dict(gridcolor="#eef2f7",linecolor="#dde3ec",tickfont=dict(color="#7a8fa6",size=10),zerolinecolor="#dde3ec"))
            st.plotly_chart(fig_cmd,use_container_width=True)
            tc1,tc2=st.columns(2)
            with tc1: prob_sol("RISING COMPLAINT VOLUME",f"Volume trend is {trend_dir}. Breach rate is {breach_trend} at {breach_pct:.1f}%.",f"Pre-allocate agency staff for peak months. Benchmark: {fastest_ag} resolves in {fastest_days:.1f} days.","b-red","📈")
            with tc2: prob_sol("HIGH BACKLOG",f"{open_pct:.1f}% open ({open_n:,} tickets). Concentrated in {highest_vol_ag} and {highest_br_ct}.",f"Deploy a 2-week backlog blitz in {highest_br_ag}. Prioritise by SLA breach, severity, reopen.","b-amber","🗂️")
            tc3,tc4=st.columns(2)
            with tc3: prob_sol("SLA BREACH SYSTEM-WIDE",f"{breach_pct:.1f}% breached. Worst: {highest_br_ag} ({highest_br_pct:.1f}%). Best: {lowest_br_ag} ({lowest_br_pct:.1f}%).",f"Tiered SLA: P1=24h, P2=72h, P3=7d. Auto-escalate at 80% of SLA window.","b-red","⚠️")
            with tc4: prob_sol("REOPEN QUALITY FAILURE",f"{reopen_pct:.1f}% reopened. {highest_reop_ag} has {highest_reop_v:.1f}% reopen rate.",f"Supervisor sign-off for severity ≥7. Send 48h confirmation SMS before closing.","b-amber","🔄")

        with tab2:
            st.markdown("<br>", unsafe_allow_html=True)
            bor_agg=df.groupby("Borough").agg(Volume=("TicketID","count"),Breach_Rate=("SLAStatus",lambda x:(x=="Breached").mean()*100),Avg_Sentiment=("SentimentScore","mean"),Avg_Resolution=("ResolutionDays","mean")).round(2).reset_index().sort_values("Volume",ascending=False)
            fig_geo_bar=px.bar(bor_agg,x="Borough",y="Volume",color="Breach_Rate",color_continuous_scale=[[0,"#00897b"],[0.5,"#f9a825"],[1,"#e53935"]],text="Volume")
            fig_geo_bar.update_traces(texttemplate="%{text:,}",textposition="outside",textfont_size=9)
            fig_geo_bar.update_layout(**{**PB,"height":280},coloraxis_colorbar=dict(title="Breach %",tickfont_color="#3d5068",bgcolor="rgba(255,255,255,0.9)"))
            st.plotly_chart(fig_geo_bar,use_container_width=True)
            tg1,tg2=st.columns(2)
            with tg1: prob_sol("VOLUME HOTSPOT DISTRICT",f"{hottest_bor}: {hottest_bor_v:,} tickets ({hottest_bor_v/total*100:.1f}% of all).",f"Deploy 2 additional field teams in {hottest_bor}. Quarterly infrastructure audits.","b-red","📍")
            with tg2: prob_sol("WORST SENTIMENT DISTRICT",f"{worst_bor_sent}: avg sentiment {worst_bor_sv:+.3f}. Avg resolution {bor_res.get(worst_bor_sent,avg_res):.1f}d.",f"Dedicated grievance cell. Monthly Jan Sunwai sessions.","b-red","😤")
            tg3,tg4=st.columns(2)
            with tg3: prob_sol("GEOGRAPHIC SLA HOTSPOT",f"{highest_br_bor}: {highest_br_bor_v:.1f}% SLA breach rate.",f"Map agency-to-complaint ratio. Reallocate cross-agency resources.","b-amber","🗺️")
            with tg4: prob_sol("RESOLUTION TIME DISPARITY",f"{slowest_bor}: {slowest_bor_d:.1f}d vs {avg_res:.1f}d system average.",f"Geographic Equity Index KPI. Target: no district > 1.5× system average.","b-amber","⚖️")

        with tab3:
            st.markdown("<br>", unsafe_allow_html=True)
            ap_tab=df.groupby("AgencyName").agg(Total=("TicketID","count"),Avg_Resolution=("ResolutionDays","mean"),Breach_Rate=("SLAStatus",lambda x:(x=="Breached").mean()*100),Avg_Sentiment=("SentimentScore","mean")).round(2).reset_index()
            fig_sla_sc=px.scatter(ap_tab,x="Avg_Resolution",y="Breach_Rate",size="Total",color="Avg_Sentiment",text="AgencyName",color_continuous_scale=SENT,size_max=45)
            fig_sla_sc.update_traces(textposition="top center",textfont=dict(size=8,color="#3d5068"))
            fig_sla_sc.update_layout(**{**PB,"height":340},coloraxis_colorbar=dict(title="Sentiment",tickfont_color="#3d5068",bgcolor="rgba(255,255,255,0.9)"))
            st.plotly_chart(fig_sla_sc,use_container_width=True)
            ts1,ts2=st.columns(2)
            with ts1: prob_sol("SLOWEST RESOLUTION AGENCY",f"{slowest_ag}: {slowest_days:.1f}d avg ({((slowest_days/avg_res)-1)*100:.0f}% above {avg_res:.1f}d average).",f"Cross-train staff from {fastest_ag} ({fastest_days:.1f}d). 90-day target: under {avg_res*1.2:.0f}d.","b-red","🐢")
            with ts2: prob_sol("HIGHEST SLA BREACH AGENCY",f"{highest_br_ag}: {highest_br_pct:.1f}% breach. Benchmark: {lowest_br_ag} at {lowest_br_pct:.1f}%.",f"P1/P2/P3 triage system. Weekly SLA breach reviews.","b-red","🚨")
            ts3,ts4=st.columns(2)
            with ts3: prob_sol("HIGHEST COST PER COMPLAINT",f"{high_cost_ag}: ₹{high_cost_v:,.0f} avg vs ₹{low_cost_v:,.0f} for {low_cost_ag}.",f"Cost audit. IoT/predictive maintenance. Target: 15% cost reduction in 18 months.","b-amber","💸")
            with ts4: prob_sol("TOP PERFORMING BENCHMARK",f"{fastest_ag}: {fastest_days:.1f}d. {best_sent_ag}: sentiment {best_sent_v:+.3f}.",f"Document SOPs. Mandatory 1-month rotation programme for under-performers.","b-green","🏆")

        with tab4:
            st.markdown("<br>", unsafe_allow_html=True)
            ag_sent_sorted=ag_sent.reset_index().sort_values("SentimentScore")
            ag_sent_sorted.columns=["AgencyName","SentimentScore"]
            ag_sent_sorted["Color"]=ag_sent_sorted["SentimentScore"].apply(lambda x:"#e53935" if x<-0.1 else ("#d97706" if x<0.1 else "#00895a"))
            fig_sb=go.Figure(go.Bar(x=ag_sent_sorted["SentimentScore"],y=ag_sent_sorted["AgencyName"],orientation="h",
                marker_color=ag_sent_sorted["Color"],text=ag_sent_sorted["SentimentScore"].round(3).astype(str),textfont=dict(size=9),textposition="outside"))
            fig_sb.add_vline(x=0,line_color="#dde3ec",line_dash="dash",line_width=1.5)
            fig_sb.update_layout(**{**PB,"height":320},xaxis_title="Avg Sentiment Score",yaxis_title="")
            st.plotly_chart(fig_sb,use_container_width=True)
            tn1,tn2=st.columns(2)
            with tn1: prob_sol("NEGATIVE SENTIMENT DOMINATES",f"{neg_pct_ai:.1f}% negative. Only {pos_pct_ai:.1f}% positive. Avg: {avg_sent:+.3f}.",f"'Closing the Loop' SMS survey. Target: improve to +0.10 in 12 months.","b-red","😔")
            with tn2: prob_sol("WORST AGENCY SENTIMENT",f"{worst_sent_ag}: {worst_sent_v:+.3f}. Model on {best_sent_ag} ({best_sent_v:+.3f}).",f"Soft-skills training. Redesign closure notification with resolution summary.","b-red","🏢")
            tn3,tn4=st.columns(2)
            with tn3: prob_sol("MOST CITIZEN-ANGERING TYPE",f'"{worst_ct}": avg {worst_ct_s:+.3f}. Avg resolution {ct_res.get(worst_ct,avg_res):.1f}d.',f'Dedicated liaison officer. 24h auto-status updates. Target under 5 days.','b-red',"😠")
            with tn4: prob_sol("SLOWEST + HIGHEST BREACH TYPE",f'"{slowest_ct}": {slowest_ct_d:.1f}d. "{highest_br_ct}": {highest_br_ct_v:.1f}% breach.',f'Milestone sub-tasks for "{slowest_ct}". Auto-escalation at 80% SLA window.','b-amber',"⏱️")

        # Strategic Recommendations
        st.markdown("""<div class="ai-section-header">
          <h3>🎯 Strategic Recommendations: Priority Action Plan</h3>
          <p>Top-priority action items ranked by impact and urgency</p>
        </div>""", unsafe_allow_html=True)

        recs=[
            ("🔴","CRITICAL — Immediate","Establish a 24-hour SLA War Room",f"With {breach_pct:.1f}% breach rate and {open_pct:.1f}% open tickets, create a daily triage team. Focus on {highest_br_ag} and {hottest_bor} first."),
            ("🔴","CRITICAL — 30 Days",f"Overhaul {slowest_ag}'s Resolution Process",f"At {slowest_days:.1f} avg days, this agency is the biggest driver of delayed governance. Commission a lean process audit within 30 days."),
            ("🟠","HIGH — 60 Days","Launch Citizen Feedback Loop System",f"Only {pos_pct_ai:.1f}% positive interactions. Auto-send 2-question SMS survey post-closure."),
            ("🟠","HIGH — 60 Days",f"Prioritise '{worst_ct[:30]}' Category",f"Sentiment {worst_ct_s:+.3f}. Dedicated resolution cell with daily supervision."),
            ("🟡","MEDIUM — 90 Days","Geographic Equity Audit",f"{highest_br_bor} at {highest_br_bor_v:.1f}% breach. No district should exceed 1.5× system average."),
            ("🟡","MEDIUM — 90 Days","Cost Efficiency Initiative",f"₹{total_cost/1e7:.1f} Cr estimated handling cost. Identify top 3 automation opportunities in {high_cost_ag}."),
            ("🟢","LOW — 180 Days","Predictive SLA Breach Model","Use historical data to predict breach probability at ticket creation."),
            ("🟢","LOW — 180 Days","Cross-Agency Knowledge Transfer",f"{best_sent_ag} (sentiment {best_sent_v:+.3f}) and {fastest_ag} ({fastest_days:.1f}d) are benchmarks. Institutionalise their SOPs."),
        ]
        for i in range(0,len(recs),2):
            cols_r=st.columns(2)
            for j,col in enumerate(cols_r):
                if i+j<len(recs):
                    emoji,urgency,title,desc=recs[i+j]
                    color="#fef2f2" if "CRITICAL" in urgency else ("#fffbeb" if "HIGH" in urgency else ("#f0fdf4" if "LOW" in urgency else "#eff6ff"))
                    border="#fecaca" if "CRITICAL" in urgency else ("#fde68a" if "HIGH" in urgency else ("#a7f3d0" if "LOW" in urgency else "#bfdbfe"))
                    tc="#dc2626" if "CRITICAL" in urgency else ("#d97706" if "HIGH" in urgency else ("#00895a" if "LOW" in urgency else "#1565c0"))
                    with col:
                        st.markdown(f"""<div style="background:{color};border:1px solid {border};border-radius:12px;padding:1.1rem 1.3rem;margin-bottom:.8rem;">
                          <div style="font-size:.6rem;font-weight:700;color:{tc};text-transform:uppercase;letter-spacing:.16em;font-family:'JetBrains Mono',monospace;margin-bottom:.4rem;">{emoji} {urgency}</div>
                          <div style="font-size:.88rem;font-weight:700;color:#0f1c2e;margin-bottom:.4rem;">{title}</div>
                          <div style="font-size:.79rem;color:#3d5068;line-height:1.7;">{desc}</div>
                        </div>""", unsafe_allow_html=True)

        st.markdown("---")
        st.subheader("🤖 AI Governance Analysis")
        if st.button("Generate AI Governance Report", key="ai_insights_ai"):
            with st.spinner("Generating governance insights..."):
                insights = generate_ai_insights(page_name="AI Governance", df=df)
                render_ai_insight_cards(insights)

        st.markdown("---")
        st.markdown("## 🤖 CivicPulse Governance Assistant")
        st.markdown("""<div style="background:linear-gradient(135deg,#0a2540,#0d3460);border-radius:12px;
        padding:1rem 1.5rem;margin-bottom:1rem;border-left:4px solid #00bcd4;">
        <p style="color:#80cfe8;font-size:.82rem;margin:0;font-family:'JetBrains Mono',monospace;">
        💬 Ask anything about complaints, agencies, SLA performance, hotspots, or governance data.</p>
        </div>""", unsafe_allow_html=True)

        user_query = st.chat_input("Ask about complaints, agencies, SLA, hotspots...")
        if user_query:
            with st.chat_message("user"):
                st.write(user_query)

            # ── Build rich context from the FULL cached/filtered df ──
            total_complaints   = len(df)
            avg_resolution     = round(df["ResolutionDays"].mean(), 2) if "ResolutionDays" in df.columns else "N/A"
            avg_sentiment      = round(df["SentimentScore"].mean(), 2) if "SentimentScore" in df.columns else "N/A"
            sla_breach         = int((df["SLAStatus"] == "Breached SLA").sum()) if "SLAStatus" in df.columns else "N/A"
            sla_within         = int((df["SLAStatus"] == "Within SLA").sum()) if "SLAStatus" in df.columns else "N/A"
            resolved           = int((df["Status"] == "Closed").sum()) if "Status" in df.columns else "N/A"
            resolution_rate    = f"{resolved/total_complaints*100:.1f}%" if isinstance(resolved, int) and total_complaints > 0 else "N/A"

            # Top agencies by volume
            top_agencies = (
                df.groupby("AgencyName").size().sort_values(ascending=False).head(50).to_dict()
                if "AgencyName" in df.columns else {}
            )
            # Top complaint types
            top_complaints = (
                df.groupby("ComplaintType").size().sort_values(ascending=False).head(50).to_dict()
                if "ComplaintType" in df.columns else {}
            )
            # District breakdown
            district_counts = (
                df.groupby("Borough").size().sort_values(ascending=False).head(50).to_dict()
                if "Borough" in df.columns else {}
            )
            # Agency-wise avg resolution days
            agency_resolution = (
                df.groupby("AgencyName")["ResolutionDays"].mean().round(1).sort_values(ascending=False).head(50).to_dict()
                if "AgencyName" in df.columns and "ResolutionDays" in df.columns else {}
            )
            # SLA breach by agency
            sla_by_agency = (
                df[df["SLAStatus"] == "Breached SLA"].groupby("AgencyName").size().sort_values(ascending=False).head(50).to_dict()
                if "SLAStatus" in df.columns and "AgencyName" in df.columns else {}
            )
            # Year-wise trend
            year_trend = (
                df.groupby("Year").size().sort_index().to_dict()
                if "Year" in df.columns else {}
            )
            # Sentiment by agency
            sentiment_by_agency = (
                df.groupby("AgencyName")["SentimentScore"].mean().round(3).sort_values().head(50).to_dict()
                if "AgencyName" in df.columns and "SentimentScore" in df.columns else {}
            )

            context_data = f"""
=== CivicPulse Telangana Governance Data (Full Dataset Summary) ===

OVERVIEW:
- Total Complaints (filtered): {total_complaints:,}
- Resolved / Closed: {resolved} ({resolution_rate})
- Average Resolution Days: {avg_resolution}
- Average Sentiment Score: {avg_sentiment}  (-1 = very negative, +1 = very positive)
- SLA Breaches: {sla_breach}
- SLA Within Target: {sla_within}

TOP 5 AGENCIES BY COMPLAINT VOLUME:
{chr(10).join(f"  {k}: {v} complaints" for k, v in top_agencies.items())}

TOP 5 COMPLAINT TYPES:
{chr(10).join(f"  {k}: {v}" for k, v in top_complaints.items())}

TOP 5 DISTRICTS BY COMPLAINT COUNT:
{chr(10).join(f"  {k}: {v}" for k, v in district_counts.items())}

YEAR-WISE COMPLAINT TREND:
{chr(10).join(f"  {k}: {v} complaints" for k, v in year_trend.items())}

AGENCIES WITH HIGHEST AVG RESOLUTION DAYS (slowest):
{chr(10).join(f"  {k}: {v} days" for k, v in agency_resolution.items())}

AGENCIES WITH MOST SLA BREACHES:
{chr(10).join(f"  {k}: {v} breaches" for k, v in sla_by_agency.items())}

AGENCIES WITH LOWEST SENTIMENT (most citizen dissatisfaction):
{chr(10).join(f"  {k}: {v}" for k, v in sentiment_by_agency.items())}
"""

            try:
                response = groq_client.chat.completions.create(
                    model="llama-3.3-70b-versatile",
                    messages=[
                        {
                            "role": "system",
                            "content": f"""You are CivicPulse, an expert Telangana governance AI assistant with two modes:

MODE 1 — DATASET QUESTIONS:
If the user's question is about complaints, agencies, SLA performance, districts, sentiment scores, resolution times, or any governance topic covered in the dataset below, answer using ONLY the data provided. Be specific, cite exact numbers, and give actionable governance insights. Do NOT make up data not present in the summary.

MODE 2 — GENERAL / OFF-TOPIC QUESTIONS:
If the user's question is NOT related to the dataset (e.g., general knowledge, greetings, coding, history, science, advice, etc.), answer helpfully using your general knowledge and reasonable assumptions. Clearly prefix your answer with: "ℹ️ This is outside the dataset — answering from general knowledge:" so the user knows the source.

RULES:
- Never refuse to answer. Always respond helpfully in one of the two modes above.
- Respond in clear, natural conversational text — no JSON, no bullet-heavy lists, just well-written prose.
- Determine the mode yourself based on the question content.

DATASET SUMMARY:
{context_data}"""
                        },
                        {"role": "user", "content": user_query}
                    ],
                    temperature=0.2,
                    max_tokens=800,
                )
                ai_reply = response.choices[0].message.content
            except Exception as e:
                ai_reply = f"AI Error: {e}"
            with st.chat_message("assistant"):
                st.write(ai_reply)

    # ══════════════════════════════════════════════════════
    #  ABOUT
    # ══════════════════════════════════════════════════════
    elif page == "about":
        st.markdown("""
        <div class="hero">
          <div class="hero-eye">ℹ️ Platform Overview</div>
          <div class="hero-h">About CivicPulse</div>
          <div class="hero-p">The Telangana Governance Intelligence Platform.</div>
        </div>""", unsafe_allow_html=True)

        a1,a2=st.columns([3,2])
        with a1:
            sec("Mission & Vision")
            st.markdown("""<div style="font-size:.9rem;color:#3d5068;line-height:1.9;margin-bottom:1.8rem;
            background:#ffffff;padding:1.2rem 1.4rem;border-radius:12px;border:1px solid #dde3ec;">
            CivicPulse consolidates <b style="color:#0f1c2e">23,000+ service tickets</b> spanning
            <b style="color:#0f1c2e">2019–2023</b> to enable evidence-based resource allocation,
            SLA accountability, and sentiment-driven service improvements across Telangana's 12 districts.
            </div>""", unsafe_allow_html=True)
            sec("Platform Capabilities")
            for ico,t,d in [
                ("📊","Executive Dashboards","Real-time KPI monitoring with automated rule-based alerting."),
                ("🗺️","Geospatial Intelligence","Interactive maps identifying hotspots by neighbourhood."),
                ("🏢","Departmental Accountability","SLA tracking, breach analysis, agency benchmarking."),
                ("💬","Citizen Voice NLP","Sentiment scoring, keyword analysis, decomposition trees."),
                ("🤖","AI Insights","Automated problem identification and strategic recommendations."),
                ("🔐","Admin Audit Log","Full user activity tracking (admin-only)."),
            ]:
                st.markdown(f"""<div class="icard" style="border-left-color:#0d9488;margin-bottom:.6rem;">
                  <div style="display:flex;gap:.9rem;align-items:flex-start;">
                    <span style="font-size:1.3rem">{ico}</span>
                    <div><div class="icard-t">{t}</div><div class="icard-b">{d}</div></div>
                  </div></div>""", unsafe_allow_html=True)
        with a2:
            sec("Data Overview")
            for ico,lbl,val in [
                ("📋","Total Tickets",f"{len(fact):,}"),("🏢","Agencies",f"{fact['AgencyName'].nunique()}"),
                ("🗺️","Districts",f"{geo['Borough'].nunique()}"),("📍","Neighbourhoods",f"{geo['Neighborhood'].nunique()}"),
                ("📂","Complaint Types",f"{compl['ComplaintType'].nunique()}"),("📆","Date Range","2019–2023"),
            ]:
                st.markdown(f"""<div style="display:flex;justify-content:space-between;align-items:center;
                padding:.75rem 1.1rem;background:#ffffff;border:1px solid #dde3ec;border-radius:10px;margin-bottom:.5rem;">
                  <div style="font-size:.8rem;color:#7a8fa6;">{ico} {lbl}</div>
                  <div style="font-family:'Lora',serif;font-weight:700;color:#2563eb;font-size:1rem;">{val}</div>
                </div>""", unsafe_allow_html=True)
            st.markdown("<br>", unsafe_allow_html=True)
            sec("Tech Stack")
            for s in ["Python 3.11","Streamlit","Plotly Express","Pandas","NumPy"]:
                st.markdown(f"""<span style="display:inline-block;margin:.25rem;padding:.28rem .85rem;
                background:#eff6ff;border:1px solid #bfdbfe;border-radius:6px;
                font-size:.72rem;color:#2563eb;font-family:'JetBrains Mono',monospace;">{s}</span>""", unsafe_allow_html=True)
            st.markdown("<br>", unsafe_allow_html=True)
            sec("Platform Roadmap")
            for yr,desc in [
                ("2019","Platform inception and complaint ingestion pipeline."),
                ("2021","Geospatial engine and hotspot mapping."),
                ("2022","SLA tracker and agency accountability module."),
                ("2023","NLP sentiment scoring integrated."),
                ("2024","AI Insights engine launched."),
                ("2025","Role-based access control and audit logging added."),
            ]:
                st.markdown(f"""<div class="tl"><div class="tl-dot"></div>
                <div><div class="tl-y">{yr}</div><div class="tl-d">{desc}</div></div></div>""", unsafe_allow_html=True)

    # ══════════════════════════════════════════════════════
    #  CONTACT & SUPPORT
    # ══════════════════════════════════════════════════════
    elif page == "contact":
        st.markdown("""
        <div class="hero">
          <div class="hero-eye">📞 Support & Feedback</div>
          <div class="hero-h">Contact & Support</div>
          <div class="hero-p">Reach the CivicPulse team for technical support or data queries.</div>
        </div>""", unsafe_allow_html=True)

        cl,cr=st.columns([2,3])
        with cl:
            sec("Get in Touch")
            for ico,lbl,val,note in [
                ("📧","Platform Support","civicpulse@telangana.gov.in","Technical issues, login problems"),
                ("📧","Data Requests","data@telangana.gov.in","New data feeds, API access"),
                ("📧","Policy & Governance","governance@telangana.gov.in","SLA policy, escalations"),
                ("📞","Helpdesk Hotline","1800-599-4599","Mon–Fri 9AM–6PM IST"),
            ]:
                st.markdown(f"""<div style="padding:1rem 1.1rem;background:#ffffff;border:1px solid #dde3ec;
                border-radius:12px;margin-bottom:.65rem;">
                  <div style="font-size:.6rem;color:#b0bfcf;text-transform:uppercase;letter-spacing:.18em;margin-bottom:.25rem;font-family:'JetBrains Mono',monospace;">{ico} {lbl}</div>
                  <div style="font-weight:700;color:#2563eb;margin-bottom:.18rem;font-size:.92rem;">{val}</div>
                  <div style="font-size:.72rem;color:#7a8fa6;">{note}</div>
                </div>""", unsafe_allow_html=True)
        with cr:
            sec("Send a Message")
            with st.form("cf",clear_on_submit=True):
                fc1_,fc2_=st.columns(2)
                with fc1_: name=st.text_input("Full Name *",placeholder="e.g. Rajesh Kumar")
                with fc2_: email=st.text_input("Email Address *",placeholder="you@example.com")
                dept_=st.selectbox("Department / Agency",["— Select —"]+sorted(fact["AgencyName"].unique().tolist()))
                subj=st.selectbox("Subject",["Technical Issue / Bug Report","Data Access Request","Feature Suggestion","SLA Policy Query","Other"])
                pri=st.radio("Priority",["🟢 Low","🟡 Medium","🔴 High"],horizontal=True)
                msg=st.text_area("Message *",height=150,placeholder="Describe your issue or request...")
                sub=st.form_submit_button("Send Message  →")
                if sub:
                    if name and email and msg:
                        ref=np.random.randint(100000,999999)
                        log_activity(st.session_state.username,"SUPPORT_TICKET_SUBMITTED",f"ref=CP-{ref}, subject={subj}, priority={pri}")
                        st.success(f"✅ Thank you **{name}**! {pri.split()[-1]}-priority message submitted. Ref: **CP-{ref}**")
                    else:
                        st.error("Please fill in Name, Email and Message.")


# ══════════════════════════════════════════════════════
#  ENTRY POINT
# ══════════════════════════════════════════════════════

if not st.session_state.logged_in:
    show_login()
else:
    show_main_app()