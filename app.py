import base64
import hmac
from datetime import datetime
from pathlib import Path
import pandas as pd
import streamlit as st

# ---------------------------------------------------------------------------
# Sayfa Yapılandırması & Özel Stil
# ---------------------------------------------------------------------------
st.set_page_config(
    page_title="Robot Paletleme RFQ Asistanı",
    page_icon="🤖",
    layout="wide",
    initial_sidebar_state="expanded",
)

ASSETS_DIR = Path(__file__).parent / "assets"

CUSTOM_CSS = """
<style>
    .main .block-container {
        padding-top: 1.5rem;
        padding-bottom: 2.5rem;
        max-width: 1280px;
    }
    .rfq-header {
        background: linear-gradient(135deg, #0f172a 0%, #1e3a5f 100%);
        color: #ffffff;
        padding: 1.4rem 1.8rem;
        border-radius: 14px;
        margin-bottom: 1.25rem;
        box-shadow: 0 6px 20px rgba(15, 23, 42, 0.14);
    }
    .rfq-header h1 {
        margin: 0;
        font-size: 1.65rem;
        font-weight: 700;
        letter-spacing: -0.02em;
        color: #ffffff;
    }
    .rfq-header p {
        margin: 0.35rem 0 0 0;
        font-size: 0.95rem;
        color: #cbd5e1;
    }
    .step-badge {
        display: inline-block;
        padding: 0.25rem 0.7rem;
        border-radius: 999px;
        font-size: 0.78rem;
        font-weight: 600;
        letter-spacing: 0.02em;
        margin-bottom: 0.45rem;
    }
    .badge-cobot {
        background-color: #dcfce7;
        color: #166534;
        border: 1px solid #86efac;
    }
    .badge-industrial {
        background-color: #fef3c7;
        color: #92400e;
        border: 1px solid #fcd34d;
    }
    .badge-info {
        background-color: #e0f2fe;
        color: #075985;
        border: 1px solid #7dd3fc;
    }
    .badge-fence-yes {
        background-color: #fee2e2;
        color: #991b1b;
        border: 1px solid #fca5a5;
    }
    .badge-fence-no {
        background-color: #dcfce7;
        color: #166534;
        border: 1px solid #86efac;
    }
    .hero-decision {
        border-radius: 14px;
        padding: 1.35rem 1.6rem;
        margin-bottom: 1.2rem;
        border-left: 6px solid;
    }
    .hero-cobot {
        background: linear-gradient(135deg, #f0fdf4 0%, #ecfeff 100%);
        border-left-color: #16a34a;
        border-top: 1px solid #bbf7d0;
        border-right: 1px solid #bbf7d0;
        border-bottom: 1px solid #bbf7d0;
    }
    .hero-industrial {
        background: linear-gradient(135deg, #fffbeb 0%, #fef2f2 100%);
        border-left-color: #d97706;
        border-top: 1px solid #fde68a;
        border-right: 1px solid #fde68a;
        border-bottom: 1px solid #fde68a;
    }
    .excluded-box {
        background-color: #f8fafc;
        border: 1px dashed #94a3b8;
        border-radius: 12px;
        padding: 1.1rem 1.3rem;
        margin-top: 0.8rem;
    }
    .price-highlight {
        background: linear-gradient(135deg, #0f172a 0%, #1e293b 100%);
        color: #ffffff;
        border-radius: 14px;
        padding: 1.3rem 1.5rem;
        margin-bottom: 1rem;
    }
    .price-highlight .label {
        font-size: 0.85rem;
        color: #94a3b8;
        text-transform: uppercase;
        letter-spacing: 0.05em;
    }
    .price-highlight .value {
        font-size: 2.05rem;
        font-weight: 800;
        color: #38bdf8;
        margin-top: 0.2rem;
    }
</style>
"""
st.markdown(CUSTOM_CSS, unsafe_allow_html=True)

# ---------------------------------------------------------------------------
# Giriş Şifresi Kontrolü
# ---------------------------------------------------------------------------
DEFAULT_LOCAL_PASSWORD = "rfq2026"


def get_app_password() -> str:
    try:
        if "APP_PASSWORD" in st.secrets:
            return str(st.secrets["APP_PASSWORD"])
    except Exception:
        pass
    return DEFAULT_LOCAL_PASSWORD


def require_login() -> None:
    if st.session_state.get("authenticated", False):
        return

    st.markdown(
        """
        <div class="rfq-header">
            <h1>🔒 Robot Paletleme RFQ Asistanı — Ekip Girişi</h1>
            <p>Devam etmek için satış ekibi giriş şifresini girin.</p>
        </div>
        """,
        unsafe_allow_html=True,
    )

    _, center, _ = st.columns([1, 1.2, 1])
    with center:
        with st.container(border=True):
            with st.form("login_form", clear_on_submit=False):
                entered = st.text_input(
                    "Giriş Şifresi",
                    type="password",
                    placeholder="Şifreyi girin...",
                )
                submitted = st.form_submit_button("Giriş Yap", type="primary", use_container_width=True)

                if submitted:
                    expected = get_app_password()
                    if hmac.compare_digest(entered, expected):
                        st.session_state["authenticated"] = True
                        st.rerun()
                    else:
                        st.error("Şifre hatalı, lütfen tekrar deneyin.")

    st.stop()


require_login()

# ---------------------------------------------------------------------------
# Sabitler, Kurallar ve Fiyatlandırma Verileri
# ---------------------------------------------------------------------------
WEIGHT_THRESHOLD_KG = 12.0
CAPACITY_THRESHOLD_PPM = 10.0

ROBOT_SPECS = {
    "Kolaboratif": {
        "title": "Kolaboratif Tip Robot (Cobot)",
        "image": "cobot.png",
        "width_m": 1.5,
        "length_m": 0.75,
        "area_text": "1.5 m × 0.75 m",
        "area_m2": 1.5 * 0.75,
        "fence_required": False,
        "fence_text": "Güvenlik çiti gerekmez",
        "base_cost_eur": 90_000,
        "included_scope": "Gripper, kurulum, yazılım ve otomasyon dahil",
    },
    "Endüstriyel": {
        "title": "Endüstriyel Tip Robot",
        "image": "industrial.png",
        "width_m": 4.2,
        "length_m": 4.2,
        "area_text": "4.2 m × 4.2 m",
        "area_m2": 4.2 * 4.2,
        "fence_required": True,
        "fence_text": "Güvenlik çiti zorunludur (fiyata dahil)",
        "base_cost_eur": 80_000,
        "included_scope": "Güvenlik çiti, kurulum, gripper, yazılım ve otomasyon dahil",
    },
}

GRIPPER_SPECS = {
    "Vakumlu": {
        "image": "gripper_vakum.png",
        "desc": "Düz üst yüzeyli koliler ve vakum tutuşuna uygun paketler için idealdir.",
    },
    "Yandan Tutmalı": {
        "image": "gripper_yandan.png",
        "desc": "Üstten vakumlanamayan veya yan yüzeyden kavranması gereken ürünler için uygundur.",
    },
    "Alttan Tutmalı": {
        "image": "gripper_alttan.png",
        "desc": "Shrinkli, ağır, açık üstlü veya alt destek gerektiren ürünler için tercih edilir.",
    },
}

STRETCH_SPECS = {
    "Tam Otomatik": {
        "image": "strec_tam_otomatik.png",
        "width_m": 5.0,
        "length_m": 7.0,
        "area_text": "5.0 m × 7.0 m",
        "area_m2": 5.0 * 7.0,
        "base_cost_eur": 100_000,
        "included_scope": "Saha kurulumu, yazılım ve otomasyon dahil",
    },
    "Yarı Otomatik": {
        "image": "strec_yari_otomatik.png",
        "width_m": 2.0,
        "length_m": 2.0,
        "area_text": "2.0 m × 2.0 m",
        "area_m2": 2.0 * 2.0,
        "base_cost_eur": 40_000,
        "included_scope": "Saha kurulumu, yazılım ve otomasyon dahil",
    },
}

EXCLUDED_ITEMS = [
    "Palet konveyörleri",
    "Ürün biriktirme konveyörleri",
    "Reject sistemi",
    "Ek güvenlik ve yazılım ekipmanları",
]

PAGES = [
    "1. Ürün Bilgileri & Kapasite",
    "2. Robot Tipi & Ekipman Önerisi",
    "3. Maliyet & Satış Fiyatlama",
]


# ---------------------------------------------------------------------------
# İş Mantığı ve Yardımcı Fonksiyonlar
# ---------------------------------------------------------------------------
def init_state() -> None:
    defaults = {
        "active_page": PAGES[0],
        "customer_name": "",
        "rfq_code": f"RFQ-{datetime.now().strftime('%Y%m%d')}-01",
        "sales_rep": "",
        "length_mm": 400,
        "width_mm": 300,
        "height_mm": 250,
        "weight_kg": 8.5,
        "product_type": "Koli",
        "product_shape_note": "Düz yüzeyli standart kapalı koli, üstten tutmaya uygun",
        "gripper_type": "Vakumlu",
        "capacity_ppm": 8.0,
        "interlayer": "Hayır",
        "stretch_needed": "Hayır",
        "stretch_type": "Yarı Otomatik",
        "margin_pct": 20.0,
        "discount_pct": 0.0,
        "extra_cost_eur": 0.0,
    }
    for k, v in defaults.items():
        if k not in st.session_state:
            st.session_state[k] = v


def evaluate_rfq(state: dict | None = None) -> dict:
    src = state if state is not None else st.session_state
    weight = float(src["weight_kg"])
    capacity = float(src["capacity_ppm"])
    gripper = src["gripper_type"]
    stretch_needed = src["stretch_needed"] == "Evet"
    stretch_type = src["stretch_type"] if stretch_needed else None

    heavy_trigger = weight > WEIGHT_THRESHOLD_KG
    speed_trigger = capacity > CAPACITY_THRESHOLD_PPM

    robot_key = "Endüstriyel" if (heavy_trigger or speed_trigger) else "Kolaboratif"

    reasons = []
    if heavy_trigger:
        reasons.append(
            f"Ürün ağırlığı ({weight:.1f} kg), 12 kg sınırının üstünde olduğu için Endüstriyel robot gereklidir."
        )
    else:
        reasons.append(
            f"Ürün ağırlığı ({weight:.1f} kg), 12 kg kolaboratif sınırının altında/dahilindedir."
        )

    if speed_trigger:
        reasons.append(
            f"Hedef kapasite ({capacity:.1f} ürün/dk), 10 ürün/dk sınırının üstünde olduğu için Endüstriyel robot gereklidir."
        )
    else:
        reasons.append(
            f"Hedef kapasite ({capacity:.1f} ürün/dk), 10 ürün/dk kolaboratif sınırının altında/dahilindedir."
        )

    robot_spec = ROBOT_SPECS[robot_key]
    gripper_spec = GRIPPER_SPECS[gripper]
    stretch_spec = STRETCH_SPECS[stretch_type] if stretch_type else None

    total_area_m2 = robot_spec["area_m2"] + (stretch_spec["area_m2"] if stretch_spec else 0.0)
    robot_cost = robot_spec["base_cost_eur"]
    stretch_cost = stretch_spec["base_cost_eur"] if stretch_spec else 0
    total_base_cost = robot_cost + stretch_cost

    return {
        "robot_key": robot_key,
        "robot_spec": robot_spec,
        "gripper_type": gripper,
        "gripper_spec": gripper_spec,
        "stretch_needed": stretch_needed,
        "stretch_type": stretch_type,
        "stretch_spec": stretch_spec,
        "heavy_trigger": heavy_trigger,
        "speed_trigger": speed_trigger,
        "reasons": reasons,
        "total_area_m2": total_area_m2,
        "robot_cost_eur": robot_cost,
        "stretch_cost_eur": stretch_cost,
        "total_base_cost_eur": total_base_cost,
        "hourly_capacity": capacity * 60.0,
        "cycle_time_sec": (60.0 / capacity) if capacity > 0 else 0.0,
    }


def format_eur(amount: float) -> str:
    return f"{amount:,.0f} €".replace(",", ".")


def get_image_path(filename: str) -> Path:
    return ASSETS_DIR / filename


def image_to_base64(filename: str) -> str:
    path = get_image_path(filename)
    if not path.exists():
        return ""
    return base64.b64encode(path.read_bytes()).decode("utf-8")


def build_html_report(result: dict, pricing: dict, state: dict | None = None) -> str:
    src = state if state is not None else st.session_state
    robot_b64 = image_to_base64(result["robot_spec"]["image"])
    gripper_b64 = image_to_base64(result["gripper_spec"]["image"])
    stretch_html = ""
    if result["stretch_needed"] and result["stretch_spec"]:
        stretch_b64 = image_to_base64(result["stretch_spec"]["image"])
        stretch_html = f"""
        <div class="box">
            <h3>Streçleme Ünitesi: {result['stretch_type']}</h3>
            <img src="data:image/png;base64,{stretch_b64}" alt="Streçleme" />
            <p><strong>Kapladığı Alan:</strong> {result['stretch_spec']['area_text']} ({result['stretch_spec']['area_m2']:.2f} m²)</p>
            <p><strong>Ham Maliyet:</strong> {format_eur(result['stretch_cost_eur'])}</p>
        </div>
        """

    excluded_li = "".join(f"<li>{item}</li>" for item in EXCLUDED_ITEMS)
    reasons_li = "".join(f"<li>{r}</li>" for r in result["reasons"])

    return f"""<!DOCTYPE html>
<html lang="tr">
<head>
<meta charset="UTF-8" />
<title>Robot Paletleme RFQ Özeti - {src['rfq_code']}</title>
<style>
    body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; color: #0f172a; max-width: 960px; margin: 24px auto; padding: 0 20px; }}
    .hdr {{ background: #0f172a; color: #fff; padding: 20px 24px; border-radius: 10px; }}
    .hdr h1 {{ margin: 0; font-size: 22px; }}
    .hdr p {{ margin: 6px 0 0; color: #cbd5e1; font-size: 13px; }}
    .grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(260px, 1fr)); gap: 16px; margin-top: 18px; }}
    .box {{ border: 1px solid #cbd5e1; border-radius: 10px; padding: 14px; background: #fff; }}
    .box img {{ max-width: 100%; max-height: 210px; object-fit: contain; display: block; margin: 10px auto; }}
    table {{ width: 100%; border-collapse: collapse; margin-top: 12px; }}
    th, td {{ border: 1px solid #cbd5e1; padding: 8px 10px; text-align: left; font-size: 13px; }}
    th {{ background: #f1f5f9; }}
    .num {{ text-align: right; font-weight: 600; }}
    .excl {{ background: #f8fafc; border: 1px dashed #64748b; padding: 12px 16px; border-radius: 8px; margin-top: 16px; }}
</style>
</head>
<body>
    <div class="hdr">
        <h1>Robot Paletleme RFQ Teknik & Maliyet Özeti</h1>
        <p>RFQ Kodu: {src['rfq_code']} | Müşteri: {src['customer_name'] or '-'} | Satış Temsilcisi: {src['sales_rep'] or '-'} | Tarih: {datetime.now().strftime('%d.%m.%Y %H:%M')}</p>
    </div>

    <h2>1. Ürün ve Kapasite Girdileri</h2>
    <table>
        <tr><th>Ürün Boyutları (L×W×H)</th><td>{src['length_mm']} × {src['width_mm']} × {src['height_mm']} mm</td><th>Ürün Ağırlığı</th><td>{src['weight_kg']:.1f} kg</td></tr>
        <tr><th>Ürün Tipi</th><td>{src['product_type']}</td><th>Kapasite</th><td>{src['capacity_ppm']:.1f} ürün/dk ({result['hourly_capacity']:.0f} ürün/saat)</td></tr>
        <tr><th>Gripper Tipi</th><td>{src['gripper_type']}</td><th>Ara Layer</th><td>{src['interlayer']}</td></tr>
        <tr><th>Tutma / Şekil Notu</th><td colspan="3">{src['product_shape_note'] or '-'}</td></tr>
    </table>

    <h2>2. Önerilen Sistem: {result['robot_spec']['title']}</h2>
    <ul>{reasons_li}</ul>
    <p><strong>Güvenlik Çiti:</strong> {result['robot_spec']['fence_text']} | <strong>Toplam Tahmini Alan:</strong> {result['total_area_m2']:.2f} m²</p>

    <div class="grid">
        <div class="box">
            <h3>{result['robot_spec']['title']}</h3>
            <img src="data:image/png;base64,{robot_b64}" alt="Robot" />
            <p><strong>Kapladığı Alan:</strong> {result['robot_spec']['area_text']} ({result['robot_spec']['area_m2']:.2f} m²)</p>
        </div>
        <div class="box">
            <h3>Gripper: {result['gripper_type']}</h3>
            <img src="data:image/png;base64,{gripper_b64}" alt="Gripper" />
            <p>{result['gripper_spec']['desc']}</p>
        </div>
        {stretch_html}
    </div>

    <h2>3. Maliyet ve Satış Fiyatlandırma Özeti</h2>
    <table>
        <tr><th>Kalem</th><th>Kapsam</th><th class="num">Tutar (€)</th></tr>
        <tr><td>{result['robot_spec']['title']}</td><td>{result['robot_spec']['included_scope']}</td><td class="num">{format_eur(result['robot_cost_eur'])}</td></tr>
        {f"<tr><td>{result['stretch_type']} Streçleme</td><td>{result['stretch_spec']['included_scope']}</td><td class='num'>{format_eur(result['stretch_cost_eur'])}</td></tr>" if result['stretch_needed'] else ""}
        {f"<tr><td>Ek Maliyet / Opsiyon</td><td>Satış ekibi tarafından eklenen tutar</td><td class='num'>{format_eur(pricing['extra_cost'])}</td></tr>" if pricing['extra_cost'] > 0 else ""}
        <tr><th colspan="2">Toplam Ham Maliyet</th><th class="num">{format_eur(pricing['total_cost'])}</th></tr>
        <tr><td colspan="2">Satış Kâr Marjı (%{pricing['margin_pct']:.1f})</td><td class="num">{format_eur(pricing['margin_amount'])}</td></tr>
        <tr><td colspan="2">İskonto (%{pricing['discount_pct']:.1f})</td><td class="num">-{format_eur(pricing['discount_amount'])}</td></tr>
        <tr><th colspan="2">Önerilen Net Satış Fiyatı</th><th class="num">{format_eur(pricing['net_sales_price'])}</th></tr>
    </table>

    <div class="excl">
        <strong>Kapsam Dışı Kalemler:</strong>
        <ul>{excluded_li}</ul>
    </div>
</body>
</html>"""


# ---------------------------------------------------------------------------
# Başlatma & Üst Başlık
# ---------------------------------------------------------------------------
init_state()

st.markdown(
    """
    <div class="rfq-header">
        <h1>🤖 Robot Paletleme & Hat Sonu RFQ Asistanı</h1>
        <p>Satış ekibi için hızlı teknik veri girişi, otomatik Kolaboratif / Endüstriyel robot seçimi ve anlık maliyet-fiyatlandırma demosu</p>
    </div>
    """,
    unsafe_allow_html=True,
)

# ---------------------------------------------------------------------------
# Kenar Çubuğu: Sayfa Gezinme + Adaptif Hızlı Değiştirme Paneli
# ---------------------------------------------------------------------------
with st.sidebar:
    st.markdown("### 🧭 Adımlar")
    selected_page = st.radio(
        "Sayfa seçin",
        PAGES,
        index=PAGES.index(st.session_state["active_page"]),
        label_visibility="collapsed",
    )
    st.session_state["active_page"] = selected_page

    if st.session_state["active_page"] != PAGES[0]:
        st.divider()
        st.markdown("### ⚡ Hızlı Adaptif Ayarlar")
        st.caption("Parametreleri buradan değiştirip görselleri ve maliyeti anlık güncelleyebilirsiniz.")

        st.number_input(
            "Ürün Ağırlığı (kg)",
            min_value=0.1,
            max_value=250.0,
            step=0.5,
            key="weight_kg",
        )
        st.number_input(
            "Kapasite (ürün/dakika)",
            min_value=0.5,
            max_value=120.0,
            step=0.5,
            key="capacity_ppm",
        )
        st.selectbox(
            "Gripper Tipi",
            ["Vakumlu", "Yandan Tutmalı", "Alttan Tutmalı"],
            key="gripper_type",
        )
        st.radio(
            "Streçleme İsteniyor mu?",
            ["Hayır", "Evet"],
            horizontal=True,
            key="stretch_needed",
        )
        if st.session_state["stretch_needed"] == "Evet":
            st.selectbox(
                "Streçleme Tipi",
                ["Tam Otomatik", "Yarı Otomatik"],
                key="stretch_type",
            )

    live_eval = evaluate_rfq()
    st.divider()
    st.markdown("#### 📌 Anlık Öneri")
    if live_eval["robot_key"] == "Kolaboratif":
        st.success(f"**{live_eval['robot_spec']['title']}**")
    else:
        st.warning(f"**{live_eval['robot_spec']['title']}**")
    if st.session_state["active_page"] == PAGES[2]:
        st.caption(f"Ham Maliyet: **{format_eur(live_eval['total_base_cost_eur'])}**")
    st.caption(f"Tahmini Alan: **{live_eval['total_area_m2']:.2f} m²**")

    st.divider()
    if st.button("🚪 Çıkış Yap", use_container_width=True):
        st.session_state["authenticated"] = False
        st.rerun()


result = evaluate_rfq()

# ---------------------------------------------------------------------------
# SAYFA 1: Ürün Bilgileri & Kapasite
# ---------------------------------------------------------------------------
if st.session_state["active_page"] == PAGES[0]:
    st.subheader("1. Ürün Bilgileri ve Kapasite Girdileri")
    st.caption("Satış temsilcisinin müşteri görüşmesinde hızlıca dolduracağı tüm teknik veriler (sonraki sayfalarda da anlık güncellenebilir).")

    col_left, col_right = st.columns([1.45, 1.0], gap="large")

    with col_left:
        with st.container(border=True):
            st.markdown("#### 📋 Proje Kimliği (Opsiyonel)")
            c1, c2, c3 = st.columns(3)
            with c1:
                st.text_input("Müşteri / Firma Adı", key="customer_name", placeholder="Örn: ABC Gıda A.Ş.")
            with c2:
                st.text_input("RFQ Kodu", key="rfq_code")
            with c3:
                st.text_input("Satış Temsilcisi", key="sales_rep", placeholder="Ad Soyad")

        with st.container(border=True):
            st.markdown("#### 📦 Ürün Boyutları ve Ağırlık")
            d1, d2, d3 = st.columns(3)
            with d1:
                st.number_input("Uzunluk L (mm)", min_value=50, max_value=2000, step=10, key="length_mm")
            with d2:
                st.number_input("Genişlik W (mm)", min_value=50, max_value=2000, step=10, key="width_mm")
            with d3:
                st.number_input("Yükseklik H (mm)", min_value=20, max_value=1500, step=10, key="height_mm")

            w_col, t_col = st.columns(2)
            with w_col:
                st.number_input(
                    "Paletlenecek Ürün Ağırlığı (kg)",
                    min_value=0.1,
                    max_value=250.0,
                    step=0.5,
                    key="weight_kg",
                    help="12 kg üstü otomatik olarak Endüstriyel robot seçer.",
                )
            with t_col:
                st.radio(
                    "Paletlenecek Ürün Tipi",
                    ["Koli", "Shrinkli Ürün"],
                    horizontal=True,
                    key="product_type",
                )

        with st.container(border=True):
            st.markdown("#### 🦾 Ürün Şekli ve Gripper Seçimi")
            st.text_input(
                "Ürünün Şekli ve Tutma Şekli (Gripper tipi için not)",
                key="product_shape_note",
                placeholder="Örn: Üstü kapalı standart koli / shrinkli şişe paketi / hassas yüzey",
            )
            st.selectbox(
                "Gripper Tipi",
                ["Vakumlu", "Yandan Tutmalı", "Alttan Tutmalı"],
                key="gripper_type",
            )
            if st.session_state["product_type"] == "Shrinkli Ürün" and st.session_state["gripper_type"] == "Vakumlu":
                st.info("İpucu: Shrinkli ürünlerde hava kaçışı olabileceği için genellikle **Yandan Tutmalı** veya **Alttan Tutmalı** gripper tercih edilir.")

        with st.container(border=True):
            st.markdown("#### ⚙️ Kapasite, Ara Layer ve Streçleme")
            cap_col, layer_col = st.columns(2)
            with cap_col:
                st.number_input(
                    "Paletlenecek Ürün Kapasitesi (ürün/dakika)",
                    min_value=0.5,
                    max_value=120.0,
                    step=0.5,
                    key="capacity_ppm",
                    help="10 ürün/dakika üstü otomatik olarak Endüstriyel robot seçer.",
                )
            with layer_col:
                st.radio(
                    "Ara Layer (Kat Arası Karton) İsteniyor mu?",
                    ["Hayır", "Evet"],
                    horizontal=True,
                    key="interlayer",
                )

            str_col1, str_col2 = st.columns(2)
            with str_col1:
                st.radio(
                    "Streçleme İsteniyor mu?",
                    ["Hayır", "Evet"],
                    horizontal=True,
                    key="stretch_needed",
                )
            with str_col2:
                if st.session_state["stretch_needed"] == "Evet":
                    st.radio(
                        "Streçleme Tipi",
                        ["Tam Otomatik", "Yarı Otomatik"],
                        horizontal=True,
                        key="stretch_type",
                    )
                else:
                    st.markdown(
                        "<div style='padding-top:1.7rem;color:#64748b;font-size:0.9rem;'>Streçleme ünitesi eklenmeyecek.</div>",
                        unsafe_allow_html=True,
                    )

    with col_right:
        with st.container(border=True):
            st.markdown("#### 📊 Canlı Kapasite & Eşik Kontrolü")
            m1, m2 = st.columns(2)
            m1.metric("Saatlik Kapasite", f"{result['hourly_capacity']:.0f} ürün/saat")
            m2.metric("Çevrim Süresi", f"{result['cycle_time_sec']:.1f} sn/ürün")

            vol_l = (
                st.session_state["length_mm"]
                * st.session_state["width_mm"]
                * st.session_state["height_mm"]
                / 1_000_000
            )
            m3, m4 = st.columns(2)
            m3.metric("Ürün Hacmi", f"{vol_l:.1f} litre")
            m4.metric("Tahmini Alan", f"{result['total_area_m2']:.2f} m²")

            st.divider()
            st.markdown("**Karar Kuralları Durumu**")
            w_val = st.session_state["weight_kg"]
            c_val = st.session_state["capacity_ppm"]

            if w_val > WEIGHT_THRESHOLD_KG:
                st.warning(f"Ağırlık: **{w_val:.1f} kg** (> 12 kg → Endüstriyel)")
            else:
                st.success(f"Ağırlık: **{w_val:.1f} kg** (≤ 12 kg → Kolaboratif uygun)")

            if c_val > CAPACITY_THRESHOLD_PPM:
                st.warning(f"Kapasite: **{c_val:.1f} ürün/dk** (> 10 ürün/dk → Endüstriyel)")
            else:
                st.success(f"Kapasite: **{c_val:.1f} ürün/dk** (≤ 10 ürün/dk → Kolaboratif uygun)")

            st.divider()
            badge_cls = "badge-cobot" if result["robot_key"] == "Kolaboratif" else "badge-industrial"
            st.markdown(
                f"""
                <div>
                    <span class="step-badge {badge_cls}">ÖNERİLEN TİP</span>
                    <div style="font-size:1.25rem;font-weight:700;color:#0f172a;margin-top:0.2rem;">
                        {result['robot_spec']['title']}
                    </div>
                    <div style="font-size:0.9rem;color:#475569;margin-top:0.25rem;">
                        {result['robot_spec']['fence_text']}
                    </div>
                </div>
                """,
                unsafe_allow_html=True,
            )

        st.button(
            "2. Sayfaya Geç: Robot & Görsel Önerisi →",
            type="primary",
            use_container_width=True,
            on_click=lambda: st.session_state.update(active_page=PAGES[1]),
        )


# ---------------------------------------------------------------------------
# SAYFA 2: Robot Tipi, Gripper & Streçleme Önerisi
# ---------------------------------------------------------------------------
elif st.session_state["active_page"] == PAGES[1]:
    st.subheader("2. Önerilen Robot Tipi, Gripper ve Hat Sonu Ekipmanları")

    hero_cls = "hero-cobot" if result["robot_key"] == "Kolaboratif" else "hero-industrial"
    badge_cls = "badge-cobot" if result["robot_key"] == "Kolaboratif" else "badge-industrial"
    fence_cls = "badge-fence-yes" if result["robot_spec"]["fence_required"] else "badge-fence-no"

    reasons_html = "".join(f"<li>{r}</li>" for r in result["reasons"])
    st.markdown(
        f"""
        <div class="hero-decision {hero_cls}">
            <span class="step-badge {badge_cls}">SEÇİLEN ROBOT TİPİ</span>
            <span class="step-badge {fence_cls}" style="margin-left:0.4rem;">{result['robot_spec']['fence_text'].upper()}</span>
            <span class="step-badge badge-info" style="margin-left:0.4rem;">ARA LAYER: {st.session_state['interlayer'].upper()}</span>
            <h2 style="margin:0.3rem 0 0.5rem 0;color:#0f172a;">{result['robot_spec']['title']}</h2>
            <ul style="margin:0;padding-left:1.2rem;color:#334155;font-size:0.95rem;">
                {reasons_html}
            </ul>
        </div>
        """,
        unsafe_allow_html=True,
    )

    v1, v2, v3 = st.columns(3, gap="medium")

    with v1:
        with st.container(border=True):
            st.markdown(f"#### 🤖 {result['robot_spec']['title']}")
            img_path = get_image_path(result["robot_spec"]["image"])
            if img_path.exists():
                st.image(str(img_path), use_container_width=True)
            st.markdown(f"**Kapladığı Alan:** {result['robot_spec']['area_text']} (**{result['robot_spec']['area_m2']:.2f} m²**)")
            st.markdown(f"**Güvenlik Çiti:** {result['robot_spec']['fence_text']}")
            st.caption(result["robot_spec"]["included_scope"])

    with v2:
        with st.container(border=True):
            st.markdown(f"#### 🦾 Gripper: {result['gripper_type']}")
            g_path = get_image_path(result["gripper_spec"]["image"])
            if g_path.exists():
                st.image(str(g_path), use_container_width=True)
            st.markdown(f"**Ürün Tipi:** {st.session_state['product_type']}")
            st.markdown(f"**Tutma Notu:** {st.session_state['product_shape_note'] or '-'}")
            st.caption(result["gripper_spec"]["desc"])

    with v3:
        with st.container(border=True):
            if result["stretch_needed"] and result["stretch_spec"]:
                st.markdown(f"#### 📦 {result['stretch_type']} Streçleme")
                s_path = get_image_path(result["stretch_spec"]["image"])
                if s_path.exists():
                    st.image(str(s_path), use_container_width=True)
                st.markdown(
                    f"**Kapladığı Alan:** {result['stretch_spec']['area_text']} (**{result['stretch_spec']['area_m2']:.2f} m²**)"
                )
                st.caption(result["stretch_spec"]["included_scope"])
            else:
                st.markdown("#### 📦 Streçleme Ünitesi")
                st.info("Bu RFQ için streçleme ünitesi talep edilmedi.")
                st.caption("Gerekirse sol menüden veya 1. sayfadan Tam Otomatik / Yarı Otomatik streçleme ekleyebilirsiniz.")

    st.markdown("#### 📐 Yerleşim Alanı ve Teknik Özet")
    area_rows = [
        {
            "Ekipman": result["robot_spec"]["title"],
            "Ölçü (m)": result["robot_spec"]["area_text"],
            "Alan (m²)": f"{result['robot_spec']['area_m2']:.2f}",
            "Not": result["robot_spec"]["fence_text"],
        }
    ]
    if result["stretch_needed"] and result["stretch_spec"]:
        area_rows.append(
            {
                "Ekipman": f"{result['stretch_type']} Streçleme",
                "Ölçü (m)": result["stretch_spec"]["area_text"],
                "Alan (m²)": f"{result['stretch_spec']['area_m2']:.2f}",
                "Not": result["stretch_spec"]["included_scope"],
            }
        )
    area_rows.append(
        {
            "Ekipman": "TOPLAM TAHMİNİ ALAN",
            "Ölçü (m)": "-",
            "Alan (m²)": f"{result['total_area_m2']:.2f}",
            "Not": f"Ara Layer: {st.session_state['interlayer']} | Ürün: {st.session_state['length_mm']}×{st.session_state['width_mm']}×{st.session_state['height_mm']} mm",
        }
    )
    st.dataframe(pd.DataFrame(area_rows), use_container_width=True, hide_index=True)

    nav1, _, nav2 = st.columns([1, 1.5, 1])
    with nav1:
        st.button(
            "← 1. Sayfaya Dön",
            use_container_width=True,
            on_click=lambda: st.session_state.update(active_page=PAGES[0]),
        )
    with nav2:
        st.button(
            "3. Sayfaya Geç: Maliyet & Fiyatlama →",
            type="primary",
            use_container_width=True,
            on_click=lambda: st.session_state.update(active_page=PAGES[2]),
        )


# ---------------------------------------------------------------------------
# SAYFA 3: Maliyet & Satış Fiyatlandırma
# ---------------------------------------------------------------------------
elif st.session_state["active_page"] == PAGES[2]:
    st.subheader("3. Maliyet Analizi ve Satış Fiyatlandırma")
    st.caption("Seçilen robot ve streçleme sisteminin ham maliyetleri üzerinden hızlı satış fiyatlaması yapın.")

    col_cost, col_price = st.columns([1.3, 1.0], gap="large")

    with col_cost:
        with st.container(border=True):
            st.markdown("#### 💶 Ham Maliyet Kalemleri (€)")
            cost_rows = [
                {
                    "Kalem": result["robot_spec"]["title"],
                    "Dahil Olan Kapsam": result["robot_spec"]["included_scope"],
                    "Ham Maliyet (€)": format_eur(result["robot_cost_eur"]),
                }
            ]
            if result["stretch_needed"] and result["stretch_spec"]:
                cost_rows.append(
                    {
                        "Kalem": f"{result['stretch_type']} Streçleme",
                        "Dahil Olan Kapsam": result["stretch_spec"]["included_scope"],
                        "Ham Maliyet (€)": format_eur(result["stretch_cost_eur"]),
                    }
                )
            if st.session_state["extra_cost_eur"] > 0:
                cost_rows.append(
                    {
                        "Kalem": "Ek Konveyör / Opsiyon Maliyeti",
                        "Dahil Olan Kapsam": "Satış ekibi tarafından manuel eklenen opsiyon",
                        "Ham Maliyet (€)": format_eur(st.session_state["extra_cost_eur"]),
                    }
                )
            st.dataframe(pd.DataFrame(cost_rows), use_container_width=True, hide_index=True)

            total_cost = result["total_base_cost_eur"] + float(st.session_state["extra_cost_eur"])
            st.metric("Toplam Bize Maliyet (Ham)", format_eur(total_cost))

        excluded_md = "\n".join(f"- **{item}**" for item in EXCLUDED_ITEMS)
        st.markdown(
            """
            <div class="excluded-box">
                <div style="font-weight:700;color:#0f172a;margin-bottom:0.4rem;">⚠️ Kapsam Dışı Kalemler (Ham Fiyata Dahil Değildir)</div>
                <div style="color:#475569;font-size:0.92rem;">Aşağıdaki ekipmanlar proje gereksinimlerine göre ayrıca fiyatlandırılmalıdır:</div>
            </div>
            """,
            unsafe_allow_html=True,
        )
        st.markdown(excluded_md)

    with col_price:
        with st.container(border=True):
            st.markdown("#### 🎯 Satış Fiyatlandırma Simülatörü")
            margin_pct = st.slider(
                "Hedef Kâr Marjı (%)",
                min_value=0.0,
                max_value=60.0,
                step=1.0,
                key="margin_pct",
            )
            discount_pct = st.slider(
                "Müşteri İskontosu (%)",
                min_value=0.0,
                max_value=25.0,
                step=0.5,
                key="discount_pct",
            )
            extra_cost = st.number_input(
                "Opsiyonel Ek Maliyet (Konveyör / Reject vb.) (€)",
                min_value=0.0,
                max_value=500_000.0,
                step=2_500.0,
                key="extra_cost_eur",
            )

            total_cost = result["total_base_cost_eur"] + float(extra_cost)
            margin_amount = total_cost * (margin_pct / 100.0)
            list_price = total_cost + margin_amount
            discount_amount = list_price * (discount_pct / 100.0)
            net_sales_price = list_price - discount_amount
            net_profit = net_sales_price - total_cost

            pricing = {
                "extra_cost": float(extra_cost),
                "total_cost": total_cost,
                "margin_pct": margin_pct,
                "margin_amount": margin_amount,
                "discount_pct": discount_pct,
                "discount_amount": discount_amount,
                "net_sales_price": net_sales_price,
                "net_profit": net_profit,
            }

            st.markdown(
                f"""
                <div class="price-highlight">
                    <div class="label">Önerilen Net Satış Fiyatı</div>
                    <div class="value">{format_eur(net_sales_price)}</div>
                </div>
                """,
                unsafe_allow_html=True,
            )

            p1, p2 = st.columns(2)
            p1.metric("Liste Fiyatı", format_eur(list_price))
            p2.metric("Net Kâr", format_eur(net_profit))

            st.divider()
            st.markdown("#### 📥 RFQ Özeti Dışa Aktar")
            html_report = build_html_report(result, pricing)

            csv_df = pd.DataFrame(
                [
                    {
                        "RFQ_Kodu": st.session_state["rfq_code"],
                        "Musteri": st.session_state["customer_name"],
                        "Satis_Temsilcisi": st.session_state["sales_rep"],
                        "Urun_L_mm": st.session_state["length_mm"],
                        "Urun_W_mm": st.session_state["width_mm"],
                        "Urun_H_mm": st.session_state["height_mm"],
                        "Agirlik_kg": st.session_state["weight_kg"],
                        "Urun_Tipi": st.session_state["product_type"],
                        "Gripper_Tipi": st.session_state["gripper_type"],
                        "Kapasite_urun_dk": st.session_state["capacity_ppm"],
                        "Ara_Layer": st.session_state["interlayer"],
                        "Strec_Gerekli": st.session_state["stretch_needed"],
                        "Strec_Tipi": result["stretch_type"] or "Yok",
                        "Onerilen_Robot": result["robot_spec"]["title"],
                        "Guvenlik_Citi": "Evet" if result["robot_spec"]["fence_required"] else "Hayır",
                        "Toplam_Alan_m2": round(result["total_area_m2"], 2),
                        "Ham_Maliyet_EUR": total_cost,
                        "Kar_Marji_Yuzde": margin_pct,
                        "Iskonto_Yuzde": discount_pct,
                        "Net_Satis_Fiyati_EUR": round(net_sales_price, 2),
                    }
                ]
            )

            dl1, dl2 = st.columns(2)
            with dl1:
                st.download_button(
                    "📄 HTML Teklif Özeti",
                    data=html_report.encode("utf-8"),
                    file_name=f"{st.session_state['rfq_code']}_ozet.html",
                    mime="text/html",
                    use_container_width=True,
                )
            with dl2:
                st.download_button(
                    "📊 CSV Veri İndir",
                    data=csv_df.to_csv(index=False).encode("utf-8-sig"),
                    file_name=f"{st.session_state['rfq_code']}_veri.csv",
                    mime="text/csv",
                    use_container_width=True,
                )

    st.button(
        "← 2. Sayfaya Dön: Robot & Görseller",
        on_click=lambda: st.session_state.update(active_page=PAGES[1]),
    )
