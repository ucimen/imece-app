import streamlit as st
import streamlit.components.v1 as components
from supabase import create_client, Client
import datetime
import time
import uuid
import extra_streamlit_components as stx 

# --- 1. SAYFA AYARLARI VE TEMA ---
st.set_page_config(page_title="İmece", page_icon="✏️", layout="centered")

# RENK PALETİ
ORANGE = "#FF6700"
BLUE_DARK = "#0F2C4C"
BG_LIGHT = "#f8f9fa"

# --- CSS İLE TEMA GİYDİRME ---
st.markdown(f"""
    <style>
        /* Sayfa üst boşluğunu ayarla */
        .block-container {{
            padding-top: 2rem !important;
            padding-bottom: 5rem !important;
        }}
        
        /* 1. SEKMELERİ (TABS) ÖZELLEŞTİRME */
        /* Sekme metin rengi */
        button[data-baseweb="tab"] > div {{
            color: {BLUE_DARK} !important;
            font-weight: bold;
            font-size: 18px;
        }}
        /* Aktif sekme alt çizgisi */
        button[data-baseweb="tab"] {{
            border-bottom-color: {ORANGE} !important;
        }}
        /* Sekme üzerine gelince */
        button[data-baseweb="tab"]:hover > div {{
            color: {ORANGE} !important;
        }}

        /* 2. BUTONLARI TURUNCU YAPMA */
        div.stButton > button:first-child {{
            background-color: {ORANGE} !important;
            color: white !important;
            border: none;
            font-weight: bold;
            font-size: 16px;
            padding: 10px 20px;
            border-radius: 8px;
            transition: all 0.3s;
        }}
        div.stButton > button:first-child:hover {{
            background-color: #e65c00 !important; /* Koyu turuncu hover */
            transform: scale(1.02);
        }}

        /* 3. GEÇMİŞ KUTUSU STİLİ */
        .history-box {{
            background-color: {BG_LIGHT}; 
            padding: 20px; 
            border-radius: 12px; 
            margin-bottom: 25px; 
            margin-top: 15px;
            border-left: 6px solid {ORANGE};
            box-shadow: 0 2px 5px rgba(0,0,0,0.05);
        }}
        .history-item {{
            margin-bottom: 12px;
            color: {BLUE_DARK};
            font-size: 16px;
            font-family: 'Source Sans Pro', sans-serif;
            display: flex;
            align-items: flex-start;
        }}
        .history-icon {{
            color: {ORANGE};
            margin-right: 10px;
            font-size: 18px;
            margin-top: 2px;
        }}

        /* 4. DİĞER DETAYLAR */
        .stProgress > div > div > div > div {{
            background-color: {ORANGE};
        }}
        h1, h2, h3 {{
            color: {BLUE_DARK} !important;
        }}
    </style>
""", unsafe_allow_html=True)

# --- 2. GİZLİ BİLGİLERİ ALMA ---
try:
    URL = st.secrets["general"]["SUPABASE_URL"]
    KEY = st.secrets["general"]["SUPABASE_KEY"]
except FileNotFoundError:
    st.error("HATA: Secrets dosyası bulunamadı!")
    st.stop()

# --- 3. SUPABASE BAĞLANTISI ---
@st.cache_resource
def init_connection():
    return create_client(URL, KEY)

supabase = init_connection()

# --- 4. KİMLİK YÖNETİMİ ---
def get_manager():
    return stx.CookieManager()

cookie_manager = get_manager()
cookie_id = cookie_manager.get(cookie="imece_user_id")

if 'user_id' not in st.session_state:
    if not cookie_id:
        unique_id = str(uuid.uuid4())
        cookie_manager.set("imece_user_id", unique_id, expires_at=datetime.datetime.now() + datetime.timedelta(days=30))
        st.session_state.user_id = unique_id
    else:
        st.session_state.user_id = cookie_id

# --- 5. YARDIMCI FONKSİYONLAR ---

def countdown_timer(expire_iso_str):
    if not expire_iso_str: return
    expire_time = datetime.datetime.fromisoformat(expire_iso_str.replace('Z', '+00:00'))
    now = datetime.datetime.now(datetime.timezone.utc)
    seconds_left = int((expire_time - now).total_seconds())
    if seconds_left < 0: seconds_left = 0

    components.html(
        f"""
        <div style="background-color:#fff3e0; border:2px solid {ORANGE}; color:{BLUE_DARK}; padding:10px; border-radius:10px; text-align:center; font-family:sans-serif; font-weight:bold; font-size:18px;">
            ⏳ Kalan Süre: <span id="cnt" style="color:{ORANGE}; font-size:22px;">{seconds_left}</span>
        </div>
        <script>
            var s = {seconds_left}; var el = document.getElementById("cnt");
            var i = setInterval(function() {{ s--; if(s<=0){{ clearInterval(i); el.innerHTML="0"; el.parentElement.innerHTML="⌛ SÜRE DOLDU!"; el.parentElement.style.color='red'; el.parentElement.style.borderColor='red'; }} else {{ el.innerHTML=s; }} }}, 1000);
        </script>
        """, height=65
    )

def finish_story_and_archive(story_id, title):
    entries = supabase.table('entries').select("content").eq("story_id", story_id).order("id").execute()
    full_text = " • ".join([e['content'].strip() for e in entries.data])
    supabase.table('archives').insert({"title": title, "full_text": full_text}).execute()
    supabase.table('entries').delete().eq("story_id", story_id).execute()
    supabase.table('stories').update({
        "content_count": 0, "last_entry_text": "Hikaye yeniden başlıyor...",
        "locked_by": None, "lock_expires_at": None, "last_user_id": None
    }).eq("id", story_id).execute()

def vote_story(archive_id, vote_type):
    col = "likes" if vote_type == "like" else "dislikes"
    current = supabase.table('archives').select(col).eq("id", archive_id).execute()
    if current.data:
        new_val = current.data[0][col] + 1
        supabase.table('archives').update({col: new_val}).eq("id", archive_id).execute()

# --- 6. İÇERİK SAYFALARI ---

def page_write():
    response = supabase.table('stories').select("*").order('id').execute()
    stories = response.data
    if not stories: st.error("Hikaye yok."); return

    titles = [s['title'] for s in stories]
    selected_tab = st.selectbox("Bir Tür Seç ve Başla:", titles)
    story = next(s for s in stories if s['title'] == selected_tab)
    
    st.caption(f"Hikaye İlerlemesi: {story['content_count']}/40 Cümle")
    st.progress(story['content_count'] / 40)
    
    # --- SON 2 CÜMLE ---
    recent_entries = supabase.table('entries').select("content").eq("story_id", story['id']).order("id", desc=True).limit(2).execute().data
    recent_entries.reverse() 
    
    content_html = ""
    if recent_entries:
        for entry in recent_entries:
            # Temiz HTML
            content_html += f'<div class="history-item"><div class="history-icon">➤</div> <i>“{entry["content"]}”</i></div>'
    else:
        content_html = '<div style="text-align:center; color:#888; font-style:italic;">Hikaye henüz başlamadı, ilk cümleyi sen yaz!</div>'

    st.markdown(f'<div class="history-box"><div style="color:{BLUE_DARK}; font-size:12px; font-weight:bold; text-align:center; margin-bottom:15px; letter-spacing:1px;">ÖNCEKİ YAZARLAR DEDİ Kİ:</div>{content_html}</div>', unsafe_allow_html=True)
    
    # --- KONTROLLER ---
    current_user = st.session_state.user_id
    is_locked = story['locked_by'] is not None
    locked_by_me = story['locked_by'] == current_user
    last_writer_is_me = story.get('last_user_id') == current_user
    
    if is_locked and story['lock_expires_at']:
        expire_time = datetime.datetime.fromisoformat(story['lock_expires_at'].replace('Z', '+00:00'))
        if datetime.datetime.now(datetime.timezone.utc) > expire_time:
            supabase.table('stories').update({"locked_by": None}).eq("id", story['id']).execute()
            st.rerun()

    if locked_by_me:
        countdown_timer(story['lock_expires_at'])
        with st.form(key="write_form"):
            user_text = st.text_input("Devamını getir (Max 50 karakter):", max_chars=50, placeholder="Buraya yaz...")
            if st.form_submit_button("🚀 Gönder", use_container_width=True):
                if user_text.strip():
                    supabase.table('entries').insert({"story_id": story['id'], "user_id": current_user, "content": user_text}).execute()
                    new_count = story['content_count'] + 1
                    if new_count >= 40:
                        finish_story_and_archive(story['id'], story['title'])
                        st.balloons()
                        st.success("Hikaye bitti! 🎉")
                    else:
                        supabase.table('stories').update({"content_count": new_count, "last_entry_text": user_text, "locked_by": None, "lock_expires_at": None, "last_user_id": current_user}).eq("id", story['id']).execute()
                        st.success("Eklendi!")
                    time.sleep(1)
                    st.rerun()
                else: st.error("Boş metin olmaz.")
    elif is_locked:
        st.warning("🔒 Şu an başkası yazıyor...")
        if st.button("🔄 Yenile", use_container_width=True): st.rerun()
    elif last_writer_is_me:
        st.info("✋ Son cümleyi sen yazdın! Sıranı bekle.")
        if st.button("🔄 Kontrol Et", use_container_width=True): st.rerun()
    else:
        if st.button("✍️ Ben Devam Ettireyim", use_container_width=True):
            check = supabase.table('stories').select("locked_by").eq("id", story['id']).execute()
            if check.data[0]['locked_by'] is None:
                expire_time = datetime.datetime.utcnow() + datetime.timedelta(seconds=30)
                supabase.table('stories').update({"locked_by": current_user, "lock_expires_at": expire_time.isoformat()}).eq("id", story['id']).execute()
                st.rerun()
            else: st.error("Tüh, başkası kaptı!"); time.sleep(1); st.rerun()

    st.divider()
    with st.expander("ℹ️ Kurallar & Taktikler"):
        st.markdown("* **Süre:** 30sn | **Limit:** 50krktr | **Kural:** Peş peşe yazmak yok.")

def page_read():
    st.header("📚 Arşiv: Biten Hikayeler")
    cats = ["Tümü", "Macera", "Komedi", "Bilim Kurgu"]
    filter_cat = st.selectbox("Kategori Filtrele", cats)
    query = supabase.table('archives').select("*").order('finished_at', desc=True)
    if filter_cat != "Tümü": query = query.eq('title', filter_cat)
    archives = query.execute().data
    
    if not archives: st.info("Henüz bitmiş hikaye yok."); return

    for arc in archives:
        with st.expander(f"📄 {arc['title']} - {arc['finished_at'][:10]}"):
            # Arşiv metni stili
            st.markdown(f"<div style='color:{BLUE_DARK}; font-size:16px; line-height:1.6;'>{arc['full_text']}</div>", unsafe_allow_html=True)
            st.divider()
            c1, c2 = st.columns([1, 5])
            if c1.button(f"🧡 {arc['likes']}", key=f"l_{arc['id']}"): vote_story(arc['id'], "like"); st.rerun()

# --- 7. ANA YAPI (LOGO VE TABS) ---

# 1. Logoyu En Tepeye Koyuyoruz
st.image("logo.png", width=180)

# 2. Native Tabs Kullanıyoruz (Asla Kaybolmaz)
tab1, tab2 = st.tabs(["✍️ HİKAYE YAZ", "📚 ARŞİVİ OKU"])

with tab1:
    page_write()

with tab2:
    page_read()
