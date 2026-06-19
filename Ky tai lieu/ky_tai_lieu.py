"""
Ứng dụng ký tài liệu
- Upload 1 hoặc nhiều file (PDF/ảnh/Excel/Word), tự động tìm vị trí ký theo từ khóa
- Hỗ trợ AI Vision (Claude API) tìm vị trí khi không quét được, xuất ZIP
"""

import io, zipfile
import numpy as np
import streamlit as st
from PIL import Image, ImageDraw
from pathlib import Path

st.set_page_config(page_title="Ký tài liệu", page_icon="✍️", layout="wide")
st.title("✍️ Ký tài liệu")

# ─── HẰNG SỐ ──────────────────────────────────────────────────────────────────
_APP_DIR = Path(__file__).parent
CHU_KY_DIR = _APP_DIR / "chu_ky"
CHU_KY_DIR.mkdir(exist_ok=True)
CHU_KY_SAVE_PATH = CHU_KY_DIR / "chu_ky.png"
RENDER_DPI = 130
HA_PRIORITY_MAX = 4   # Từ khóa ưu tiên <= 4 mới được xem là của Hoàng An
PT_TO_PX = RENDER_DPI / 72

TU_KHOA_FILE = _APP_DIR / "tu_khoa.txt"

def _load_keywords() -> list:
    """Đọc tu_khoa.txt. Cột 4 là số ưu tiên (nhỏ = ưu tiên cao hơn)."""
    result = []
    if TU_KHOA_FILE.exists():
        for line in TU_KHOA_FILE.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            parts = [p.strip() for p in line.split("|")]
            if len(parts) >= 2:
                kw       = parts[0]
                place    = parts[1].lower() if parts[1].lower() in ("below","above") else "below"
                label    = parts[2] if len(parts) >= 3 else kw
                try:
                    priority = int(parts[3]) if len(parts) >= 4 else 5
                except ValueError:
                    priority = 5
                try:
                    v_offset = float(parts[4]) if len(parts) >= 5 else None
                except ValueError:
                    v_offset = None
                result.append({"kw": kw, "label": label, "place": place,
                               "priority": priority, "v_offset": v_offset})
    if not result:
        result = [
            {"kw": "CÔNG TY HOÀNG AN",      "label": "Công ty Hoàng An",       "place": "above", "priority": 1},
            {"kw": "XÁC NHẬN",             "label": "XÁC NHẬN",               "place": "below", "priority": 2},
            {"kw": "Xác nhận đơn đặt hàng","label": "Xác nhận đơn đặt hàng", "place": "below", "priority": 3},
            {"kw": "Xác nhận của bên sản xuất","label": "Xác nhận bên SX",    "place": "below", "priority": 3},
            {"kw": "Xác nhận của nhà sản xuất","label": "Xác nhận nhà SX",    "place": "below", "priority": 3},
            {"kw": "Nguyễn Minh Hoàng",    "label": "Nguyễn Minh Hoàng",     "place": "above", "priority": 4},
            {"kw": "(Ký, họ tên)",          "label": "(Ký, họ tên)",           "place": "below", "priority": 5},
            {"kw": "Tổng Giám đốc",         "label": "Tổng Giám đốc",          "place": "above", "priority": 6},
        ]
    return result

SIGN_KEYWORDS = _load_keywords()

def _strip_accents(s: str) -> str:
    import unicodedata
    return unicodedata.normalize('NFD', s.lower()).encode('ascii', 'ignore').decode('ascii')

# labels không trùng để hiển thị dropdown
_UNIQUE_LABELS = list(dict.fromkeys(e["label"] for e in SIGN_KEYWORDS))
_LABEL_TO_ENTRY = {}
for e in SIGN_KEYWORDS:
    _LABEL_TO_ENTRY.setdefault(e["label"], e)

# ─── SESSION STATE ────────────────────────────────────────────────────────────
for k, v in {
    "sig_active": None, "canvas_key": 0, "show_change_sig": False,
    "batch_results": [], "batch_orig_bytes": {},
}.items():
    if k not in st.session_state:
        st.session_state[k] = v

# ═══════════════════════════════════════════════════════════════════════════════
# HELPERS
# ═══════════════════════════════════════════════════════════════════════════════

def _find_chu_ky():
    for pat in ["*.png","*.jpg","*.jpeg","*.PNG","*.JPG"]:
        for f in sorted(CHU_KY_DIR.glob(pat)):
            try: return Image.open(f).convert("RGBA")
            except: continue
    return None

def remove_white_bg(img: Image.Image, threshold=230) -> Image.Image:
    img = img.convert("RGBA"); data = np.array(img)
    m = (data[:,:,0]>threshold)&(data[:,:,1]>threshold)&(data[:,:,2]>threshold)
    data[m,3] = 0
    return Image.fromarray(data,"RGBA")

def save_chu_ky(img: Image.Image):
    img.save(CHU_KY_SAVE_PATH,"PNG"); st.session_state.sig_active = img

# ── Tải file từ đường dẫn (vd ổ Drive đã mount: H:\... hoặc /storage/...) ─────

def load_bytes_from_path(path_str: str):
    """Đọc bytes từ đường dẫn local/đường dẫn ổ Drive đã mount.
    Trả về (bytes, filename) hoặc (None, lỗi)."""
    if not path_str or not path_str.strip():
        return None, None
    p = Path(path_str.strip().strip('"').strip("'"))
    if not p.exists():
        return None, f"Không tìm thấy đường dẫn: `{p}`"
    if p.is_dir():
        return None, f"Đây là thư mục, không phải file: `{p}`"
    try:
        return p.read_bytes(), p.name
    except Exception as e:
        return None, f"Lỗi đọc file: {e}"

# ── Tự động load chữ ký đã lưu trước đó ──────────────────────────────────────
if st.session_state.sig_active is None:
    st.session_state.sig_active = _find_chu_ky()

# ── PDF helpers ───────────────────────────────────────────────────────────────

def render_pdf_page(pdf_bytes: bytes, page_num: int) -> Image.Image:
    import fitz
    doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    pix = doc[page_num].get_pixmap(matrix=fitz.Matrix(PT_TO_PX,PT_TO_PX), alpha=False)
    return Image.frombytes("RGB",[pix.width,pix.height],pix.samples)

def render_pdf_page_hq(pdf_bytes: bytes, page_num: int, dpi: int = 200) -> Image.Image:
    """Render độ phân giải cao hơn — dùng riêng cho AI đọc chữ rõ hơn."""
    import fitz
    doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    ratio = dpi / 72
    pix = doc[page_num].get_pixmap(matrix=fitz.Matrix(ratio, ratio), alpha=False)
    return Image.frombytes("RGB", [pix.width, pix.height], pix.samples)

def scan_page_for_keywords(pdf_bytes: bytes, page_num: int) -> list:
    import fitz
    doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    page = doc[page_num]; found, seen = [], []
    for entry in SIGN_KEYWORDS:
        try: rects = page.search_for(entry["kw"])
        except: continue
        for rect in rects:
            if any(abs(rect.y0-s[0])<8 and abs(rect.x0-s[1])<20 for s in seen): continue
            seen.append((rect.y0,rect.x0))
            found.append({
                "keyword":  entry["kw"],
                "label":    entry["label"],
                "place":    entry["place"],
                "priority": entry.get("priority", 5),
                "v_offset": entry.get("v_offset"),  # None = dùng slider
                "pt": (rect.x0, rect.y0, rect.x1, rect.y1),
                "px": (rect.x0*PT_TO_PX, rect.y0*PT_TO_PX,
                       rect.x1*PT_TO_PX, rect.y1*PT_TO_PX),
            })
    # Ưu tiên nhỏ nhất trước; cùng ưu tiên thì theo Y từ trên xuống
    found.sort(key=lambda a: (a.get("priority", 5), a["pt"][1]))
    return found

def find_content_bottom(page) -> tuple:
    """Trả về (y_bottom, x_center_of_content) — vùng trống ngay dưới nội dung cuối trang."""
    import fitz
    blocks = page.get_text("blocks")
    pw, ph = page.rect.width, page.rect.height
    if not blocks:
        return ph * 0.75, pw / 2
    # Y dưới cùng của nội dung
    y_bottom = max(b[3] for b in blocks)
    # X trung tâm của toàn bộ nội dung (trung bình giữa x0 và x1 của tất cả blocks)
    x_centers = [(b[0] + b[2]) / 2 for b in blocks]
    x_mid = sum(x_centers) / len(x_centers)
    return y_bottom, x_mid


def sign_pdf_bottom_center(pdf_bytes: bytes, sig_img, pages: list,
                           width_pct: float, v_offset: float = 15) -> tuple:
    """Ký ở vùng trống bên dưới nội dung, căn giữa trang — dùng khi không có từ khóa HA."""
    import fitz
    buf = io.BytesIO(); sig_img.save(buf, "PNG"); sig_png = buf.getvalue()
    ar = sig_img.width / sig_img.height
    doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    signed = []
    for i, page in enumerate(doc):
        if (i + 1) not in pages:
            continue
        pw, ph = page.rect.width, page.rect.height
        sw = pw * width_pct / 100
        sh = sw / ar
        y_bottom, x_mid = find_content_bottom(page)
        x = max(0, min((pw - sw) / 2, pw - sw))   # căn giữa trang
        y = max(0, min(y_bottom + v_offset, ph - sh))
        page.insert_image(fitz.Rect(x, y, x + sw, y + sh), stream=sig_png)
        signed.append(i + 1)
    out = io.BytesIO(); doc.save(out)
    return out.getvalue(), signed


def auto_find_keyword_in_doc(pdf_bytes: bytes):
    """Quét tài liệu, trả về (kw, place) của từ khóa Hoàng An tốt nhất.
    Chỉ chấp nhận keyword có priority <= HA_PRIORITY_MAX.
    Trả về (None, None) nếu không tìm thấy → báo hiệu dùng fallback bottom-center."""
    import fitz
    doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    candidates = []
    for pg_i, page in enumerate(doc):
        for entry in SIGN_KEYWORDS:
            p = entry.get("priority", 5)
            if p > HA_PRIORITY_MAX:
                continue
            try:
                rects = page.search_for(entry["kw"])
                if rects:
                    candidates.append((p, pg_i, rects[0].y0,
                                       entry["kw"], entry["place"],
                                       entry.get("v_offset")))  # None = dùng default
            except:
                continue
    if not candidates:
        return None, None, None   # → fallback bottom-center
    candidates.sort(key=lambda c: (c[0], c[1], c[2]))
    best = candidates[0]
    return best[3], best[4], best[5]  # kw, place, v_offset

def get_total_pages(pdf_bytes: bytes) -> int:
    import fitz
    doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    return doc.page_count

def _sig_xy_pt(area, sig_h_pt, v_offset):
    x0,y0,x1,y1 = area["pt"]
    return (x0, y1+v_offset) if area["place"]=="below" else (x0, y0-sig_h_pt-v_offset)

def _sig_xy_px(area, sig_h_px, v_offset_px):
    x0,y0,x1,y1 = area["px"]
    return (x0, y1+v_offset_px) if area["place"]=="below" else (x0, y0-sig_h_px-v_offset_px)

def _manual_xy(bw, bh, sw, sh, position, margin):
    m = margin
    return {"Trên trái":(m,m),"Trên phải":(bw-sw-m,m),
            "Dưới trái":(m,bh-sh-m),"Dưới phải":(bw-sw-m,bh-sh-m),
            "Giữa trang":((bw-sw)//2,(bh-sh)//2),
            "Giữa dưới":((bw-sw)//2,bh-sh-m)}.get(position,(bw-sw-m,bh-sh-m))

# ── Ghép chữ ký ───────────────────────────────────────────────────────────────

def overlay_sig(base: Image.Image, sig: Image.Image,
                x_px, y_px, sw_px, highlight_px=None) -> Image.Image:
    bw,bh = base.size
    sw = max(30, min(sw_px, bw)); sh = int(sig.height*sw/sig.width)
    sig_r = sig.resize((sw,sh),Image.LANCZOS).convert("RGBA")
    px = max(0,min(int(x_px),bw-sw)); py = max(0,min(int(y_px),bh-sh))
    result = base.convert("RGBA")
    if highlight_px:
        hl = Image.new("RGBA",result.size,(0,0,0,0)); draw = ImageDraw.Draw(hl)
        x0,y0,x1,y1 = [int(v) for v in highlight_px]
        draw.rectangle([x0,y0,x1,y1],outline=(255,140,0,230),width=3)
        result = Image.alpha_composite(result,hl)
    result.paste(sig_r,(px,py),mask=sig_r)
    return result.convert("RGB")

def sign_pdf_auto(pdf_bytes, sig_img, pages, keyword, place, width_pct, v_offset):
    import fitz
    buf=io.BytesIO(); sig_img.save(buf,"PNG"); sig_png=buf.getvalue()
    ar=sig_img.width/sig_img.height
    doc=fitz.open(stream=pdf_bytes,filetype="pdf")
    signed,skipped=[],[]
    for i,page in enumerate(doc):
        pg=i+1
        if pg not in pages: continue
        pw,ph=page.rect.width,page.rect.height
        sw=pw*width_pct/100; sh=sw/ar
        rects=page.search_for(keyword)
        if not rects: skipped.append(pg); continue
        r=rects[0]
        area={"place":place,"pt":(r.x0,r.y0,r.x1,r.y1)}
        x,y=_sig_xy_pt(area,sh,float(v_offset))
        x=max(0,min(x,pw-sw)); y=max(0,min(y,ph-sh))
        page.insert_image(fitz.Rect(x,y,x+sw,y+sh),stream=sig_png)
        signed.append(pg)
    out=io.BytesIO(); doc.save(out)
    return out.getvalue(), signed, skipped

def create_zip(results: list) -> bytes:
    """Tạo ZIP từ danh sách kết quả ký hàng loạt."""
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        for r in results:
            if r.get("bytes"):
                zf.writestr(r.get("out_name", r["name"]), r["bytes"])
    return buf.getvalue()

def _ext(name: str) -> str:
    return Path(name).suffix.lower()

def convert_to_pdf(name: str, data: bytes) -> tuple:
    """Chuyển file sang PDF bytes. Trả về (pdf_bytes, pdf_name, error_msg)."""
    ext = _ext(name)
    stem = Path(name).stem
    pdf_name = stem + ".pdf"

    if ext == ".pdf":
        return data, name, None

    # ── Ảnh → PDF bằng Pillow ─────────────────────────────────────────────────
    if ext in (".png", ".jpg", ".jpeg"):
        try:
            img = Image.open(io.BytesIO(data)).convert("RGB")
            buf = io.BytesIO()
            img.save(buf, "PDF", resolution=150)
            return buf.getvalue(), pdf_name, None
        except Exception as e:
            return None, pdf_name, f"Lỗi chuyển ảnh → PDF: {e}"

    # ── Word / Excel → PDF bằng LibreOffice ───────────────────────────────────
    if ext in (".docx", ".xlsx", ".xls"):
        try:
            import subprocess, tempfile, os
            with tempfile.TemporaryDirectory() as tmp:
                in_path = os.path.join(tmp, name)
                with open(in_path, "wb") as f:
                    f.write(data)
                r = subprocess.run(
                    ["libreoffice", "--headless", "--convert-to", "pdf",
                     "--outdir", tmp, in_path],
                    capture_output=True, timeout=90,
                    env={**os.environ, "HOME": tmp}  # tránh lock profile LibreOffice
                )
                pdf_path = os.path.join(tmp, pdf_name)
                if os.path.exists(pdf_path):
                    with open(pdf_path, "rb") as f:
                        return f.read(), pdf_name, None
                err = r.stderr.decode("utf-8", errors="replace")[:300]
                return None, pdf_name, f"LibreOffice không tạo được PDF: {err}"
        except FileNotFoundError:
            return None, pdf_name, ("LibreOffice chưa được cài. "
                                     "Kiểm tra packages.txt có dòng 'libreoffice'.")
        except Exception as e:
            return None, pdf_name, f"Lỗi chuyển {ext} → PDF: {e}"

    return None, pdf_name, f"Định dạng {ext} chưa hỗ trợ."


def process_one_file(name: str, data: bytes, sig_img, kw, place,
                     pages_mode: str, width_pct: float, v_offset: float,
                     kw_v_offset=None,
                     img_position: str = "Dưới phải", img_margin: int = 35) -> dict:
    """Chuyển file sang PDF → tìm từ khóa → ký → trả về dict kết quả."""
    try:
        # ── Bước 1: Chuyển sang PDF ───────────────────────────────────────────
        pdf_bytes, pdf_name, err = convert_to_pdf(name, data)
        if err:
            return {"name": name, "status": "❌ Lỗi chuyển PDF",
                    "detail": err, "bytes": None, "out_name": name}

        # ── Bước 2: Ký PDF ────────────────────────────────────────────────────
        total = get_total_pages(pdf_bytes)
        pages = list(range(1, total + 1)) if pages_mode == "Tất cả trang" else [total]

        if kw is None:
            out, signed = sign_pdf_bottom_center(pdf_bytes, sig_img, pages, width_pct)
            detail = f"Ký {len(signed)} trang (vùng trống cuối)"
        else:
            effective_offset = kw_v_offset if kw_v_offset is not None else v_offset
            out, signed, skipped = sign_pdf_auto(pdf_bytes, sig_img, pages, kw, place,
                                                  width_pct, effective_offset)
            offset_note = f" [kc={int(effective_offset)}pt]" if kw_v_offset is not None else ""
            detail = f"Ký {len(signed)} trang theo [{kw}]{offset_note}"
            if skipped:
                detail += f" | bỏ qua trang {skipped}"

        ext_orig = _ext(name)
        if ext_orig != ".pdf":
            detail = f"→PDF + " + detail

        return {"name": name, "status": "✅ OK", "detail": detail,
                "bytes": out, "out_name": pdf_name}

    except Exception as e:
        return {"name": name, "status": "❌ Lỗi", "detail": str(e),
                "bytes": None, "out_name": name}

# ═══════════════════════════════════════════════════════════════════════════════
# SIDEBAR — Chữ ký
# ═══════════════════════════════════════════════════════════════════════════════
with st.sidebar:
    st.header("✍️ Chữ ký")
    if st.session_state.sig_active and not st.session_state.show_change_sig:
        st.success("Đang dùng chữ ký đã lưu")
        st.image(st.session_state.sig_active, use_container_width=True)
        if st.button("🔄 Đổi chữ ký", use_container_width=True):
            st.session_state.show_change_sig = True; st.rerun()
    else:
        if st.session_state.show_change_sig: st.info("Chọn chữ ký mới:")
        tab_up, tab_draw = st.tabs(["📤 Upload ảnh","🖊 Vẽ tay"])
        new_sig = None
        with tab_up:
            sf = st.file_uploader("Ảnh chữ ký (PNG/JPG)", type=["png","jpg","jpeg"])
            sig_path = st.text_input(
                "...hoặc dán đường dẫn file (ổ Drive đã mount, vd H:\\...\\chu_ky.png)",
                key="sig_path_input")
            loaded = None
            if sf:
                loaded = Image.open(sf)
            elif sig_path:
                _b, _name_or_err = load_bytes_from_path(sig_path)
                if _b:
                    loaded = Image.open(io.BytesIO(_b))
                elif _name_or_err:
                    st.error(_name_or_err)
            if loaded:
                rm = st.checkbox("Xóa nền trắng", value=True)
                new_sig = remove_white_bg(loaded) if rm else loaded.convert("RGBA")
                st.image(new_sig, use_container_width=True)
        with tab_draw:
            try:
                from streamlit_drawable_canvas import st_canvas
                c1,c2=st.columns([4,1])
                with c2:
                    if st.button("Xóa",use_container_width=True):
                        st.session_state.canvas_key+=1; st.rerun()
                cr=st_canvas(stroke_width=3,stroke_color="#111111",
                             background_color="#f5f5f5",height=150,
                             drawing_mode="freedraw",
                             key=f"cv_{st.session_state.canvas_key}",
                             display_toolbar=False)
                if cr.image_data is not None:
                    arr=cr.image_data.astype(np.uint8)
                    if (arr[:,:,:3].min(axis=2)<180).any():
                        new_sig=remove_white_bg(Image.fromarray(arr[:,:,:3]),200)
            except ImportError:
                st.info("Tính năng vẽ tay không khả dụng.")
        if new_sig is not None:
            st.divider()
            if st.button("💾 Lưu & dùng chữ ký này",type="primary",use_container_width=True):
                save_chu_ky(new_sig); st.session_state.show_change_sig=False; st.rerun()
        if st.session_state.show_change_sig:
            if st.button("↩️ Giữ chữ ký cũ",use_container_width=True):
                st.session_state.show_change_sig=False; st.rerun()

# ═══════════════════════════════════════════════════════════════════════════════
# MAIN
# ═══════════════════════════════════════════════════════════════════════════════
if st.session_state.sig_active is None:
    st.info("Chưa có chữ ký — upload hoặc vẽ chữ ký ở thanh bên trái rồi lưu.")
    st.stop()

# ═══════════════════════════════════════════════════════════════════════════════
# TAB 2 — Ký hàng loạt
# ═══════════════════════════════════════════════════════════════════════════════
col_b1, col_b2 = st.columns([1,1], gap="large")

with col_b1:
    # ── Chọn file ────────────────────────────────────────────────
    uploaded_many = st.file_uploader(
        "📂 Chọn file cần ký (PDF, ảnh, Excel, Word)",
        type=["pdf","png","jpg","jpeg","xlsx","xls","docx"],
        accept_multiple_files=True, key="b_upload")

    files_data = []
    if uploaded_many:
        files_data = [(f.name, f.read()) for f in uploaded_many]

    if files_data:
        st.success(f"✅ {len(files_data)} file sẵn sàng")
        with st.expander(f"Danh sách {len(files_data)} file"):
            for name, data in files_data:
                st.text(f"  • {name}  ({len(data)//1024} KB)")

    # ── Cài đặt (mặc định đóng) ──────────────────────────────────────
    with st.expander("⚙️ Cài đặt ký", expanded=False):
        kw_mode = st.radio("Từ khóa tìm vị trí",
                          ["🤖 Tự động", "🎯 Chọn cụ thể"],
                          horizontal=True, key="b_kwmode")

        specific_kw, specific_place = None, None
        if kw_mode == "🎯 Chọn cụ thể":
            chosen_label = st.selectbox("Từ khóa", _UNIQUE_LABELS, key="b_kwsel")
            entry = _LABEL_TO_ENTRY[chosen_label]
            specific_kw, specific_place = entry["kw"], entry["place"]

        pages_mode = st.radio("Trang ký PDF",["Tất cả trang","Chỉ trang cuối"],
                             horizontal=True, key="b_pgmode")

        _cw1, _cw2 = st.columns(2)
        with _cw1:
            b_width = st.slider("Kích thước (%rộng)",5,60,22,key="b_w")
        with _cw2:
            b_voffset = st.slider("Khoảng cách (pt)",-30,80,4,key="b_vo")

        _cw3, _cw4 = st.columns(2)
        with _cw3:
            b_img_pos = st.selectbox("Vị trí ảnh/Excel",
                ["Dưới phải","Dưới trái","Giữa dưới","Trên phải","Trên trái"],key="b_ipos")
        with _cw4:
            b_margin = st.slider("Lề ảnh (px)",5,150,35,key="b_mg")

    # ── Bắt đầu ký ───────────────────────────────────────────────────
    ready = bool(files_data)
    if not ready:
        st.caption("Upload file để bắt đầu.")

    if ready and st.button("▶️ Bắt đầu ký hàng loạt",type="primary",
                           use_container_width=True, key="b_go"):
        sig = st.session_state.sig_active
        results = []
        progress_bar = st.progress(0, text="Đang xử lý...")
        status_box = st.empty()

        for i, (name, data) in enumerate(files_data):
            status_box.text(f"Đang xử lý: {name}  ({i+1}/{len(files_data)})")

            # Tìm keyword
            if kw_mode == "🤖 Tự động":
                kw, place, kw_voff = auto_find_keyword_in_doc(data)
            else:
                kw, place, kw_voff = specific_kw, specific_place, None

            r = process_one_file(name, data, sig, kw, place,
                                 pages_mode, b_width, b_voffset,
                                 kw_v_offset=kw_voff,
                                 img_position=b_img_pos, img_margin=b_margin)
            results.append(r)
            progress_bar.progress((i+1)/len(files_data),
                                  text=f"Xong {i+1}/{len(files_data)}: {name}")

        st.session_state.batch_results = results
        st.session_state.batch_orig_bytes = {name: data for name, data in files_data}
        status_box.empty()
        progress_bar.progress(1.0, text="Hoàn tất!")

with col_b2:
    st.subheader("📊 Kết quả & xem trước")
    results = st.session_state.batch_results

    if not results:
        st.info("Kết quả sẽ hiển thị ở đây sau khi ký xong.")
    else:
        ok   = [r for r in results if r["status"] == "✅ OK"]
        skip = [r for r in results if "Bỏ qua" in r["status"]]
        err  = [r for r in results if r["status"] == "❌ Lỗi"]

        c1, c2, c3 = st.columns(3)
        c1.metric("✅ Thành công", len(ok))
        c2.metric("⏭️ Bỏ qua",    len(skip))
        c3.metric("❌ Lỗi",        len(err))

        import pandas as pd
        df = pd.DataFrame([{"File": r["name"], "Trạng thái": r["status"],
                             "Chi tiết": r["detail"]} for r in results])
        st.dataframe(df, use_container_width=True, hide_index=True)

        # ── Xem trước kết quả ────────────────────────────────────────────
        if ok:
            st.divider()
            st.markdown("**👁 Xem trước file đã ký**")
            prev_names = [r["name"] for r in ok]
            prev_sel = st.selectbox("Chọn file để xem trước",
                                    prev_names, key="b_prev_sel")
            sel_r = next(r for r in ok if r["name"] == prev_sel)
            ext_p = _ext(sel_r["name"])

            if ext_p == ".pdf":
                try:
                    total_p = get_total_pages(sel_r["bytes"])
                    if total_p > 1:
                        pg_sel = st.select_slider(
                            "Trang", options=list(range(1, total_p+1)),
                            value=total_p, key="b_pg_prev")
                    else:
                        pg_sel = 1
                    prev_img = render_pdf_page(sel_r["bytes"], pg_sel - 1)
                    st.image(prev_img, use_container_width=True,
                             caption=f"{sel_r['name']} — Trang {pg_sel}/{total_p}")
                except Exception as e:
                    st.error(f"Lỗi xem trước: {e}")

            elif ext_p in (".png", ".jpg", ".jpeg"):
                st.image(sel_r["bytes"], use_container_width=True,
                         caption=sel_r["name"])

            else:
                st.info(f"📄 File **{ext_p.upper()}** sẽ được chuyển sang PDF tự động trước khi ký.")

            # ── Chỉnh vị trí cho file đang xem ──────────────────────────
            _orig_b = st.session_state.batch_orig_bytes.get(sel_r["name"])
            if _orig_b:
                with st.expander("✏️ Chỉnh vị trí chữ ký cho file này"):
                    _sig_e = st.session_state.sig_active

                    _key_ok = bool(_get_anthropic_key())
                    st.caption("🔑 AI Vision: " + ("✅ Đã cấu hình API key" if _key_ok
                              else "❌ Chưa thấy API key (kiểm tra Secrets + Reboot app)"))

                    # ── 🤖 AI tìm vị trí (chạy TRƯỚC khi tạo slider để set session_state an toàn)
                    if ext_p == ".pdf":
                        _epg_preview = st.session_state.get("b_epg", get_total_pages(_orig_b))
                    if st.button("🤖 Dùng AI tìm vị trí", use_container_width=True, key="b_ai_find"):
                        with st.spinner("Đang hỏi AI..."):
                            try:
                                if ext_p == ".pdf":
                                    _ai_img = render_pdf_page_hq(_orig_b, _epg_preview - 1)
                                else:
                                    _ai_img = Image.open(io.BytesIO(_orig_b)).convert("RGB")
                                _ai_width = st.session_state.get("b_ew", 22)
                                _ai_res, _ai_err = ai_find_signature_position(
                                    _ai_img, _sig_e, _ai_width)
                            except Exception as _ai_ex:
                                _ai_res, _ai_err = None, str(_ai_ex)
                        if _ai_res:
                            st.session_state["b_ex"] = round(_ai_res["x_pct"])
                            st.session_state["b_ey"] = round(_ai_res["y_pct"])
                            st.session_state["_b_ai_reason"] = _ai_res.get("reason", "")
                        elif _ai_err:
                            st.session_state["_b_ai_reason"] = None
                            st.error(_ai_err)
                    if st.session_state.get("_b_ai_reason"):
                        st.success(f"🤖 AI đã định vị: {st.session_state['_b_ai_reason']}")

                    _ce1, _ce2 = st.columns(2)
                    with _ce1:
                        _ew = st.slider("Kích thước (% chiều rộng)", 5, 60, 22, key="b_ew")
                    with _ce2:
                        # Tính tổng trang từ file gốc (PDF) hoặc sau convert
                        if ext_p == ".pdf":
                            _etotal = get_total_pages(_orig_b)
                        else:
                            _etotal = 1  # ảnh/Word/Excel convert sang 1+ trang, dùng 1 để preview
                        if _etotal > 1:
                            _epg = st.selectbox("Trang", list(range(1, _etotal+1)),
                                                index=_etotal-1, key="b_epg")
                        else:
                            _epg = 1
                    _ex = st.slider("↔ Ngang (% từ trái)", 0, 95, 65, key="b_ex")
                    _ey = st.slider("↕ Dọc (% từ trên)",   0, 95, 70, key="b_ey")

                    # Preview cập nhật realtime khi kéo slider
                    try:
                        if ext_p == ".pdf":
                            _base_e = render_pdf_page(_orig_b, _epg - 1)
                        elif ext_p in (".png", ".jpg", ".jpeg"):
                            _base_e = Image.open(io.BytesIO(_orig_b)).convert("RGB")
                        else:
                            st.caption("Preview không khả dụng cho Word/Excel — xem kết quả sau khi ký.")
                            _base_e = None
                        if _base_e:
                            _bwe, _bhe = _base_e.size
                            _swe = max(30, int(_bwe * _ew / 100))
                            _xe  = int(_bwe * _ex / 100)
                            _ye  = int(_bhe * _ey / 100)
                            st.image(overlay_sig(_base_e, _sig_e, _xe, _ye, _swe),
                                     use_container_width=True,
                                     caption="Kéo slider → xem trước cập nhật ngay")
                    except Exception as _ep:
                        st.warning(f"Không xem trước được: {_ep}")

                    if st.button("💾 Lưu vị trí này vào file",
                                 type="primary", use_container_width=True, key="b_esave"):
                        try:
                            # Convert sang PDF trước nếu chưa phải PDF
                            _pdf_b, _pdf_n, _pdf_err = convert_to_pdf(
                                sel_r["name"], _orig_b)
                            if _pdf_err:
                                st.error(f"Lỗi convert: {_pdf_err}")
                            else:
                                _doc_e = __import__("fitz").open(stream=_pdf_b, filetype="pdf")
                                _all_pages_e = list(range(1, _doc_e.page_count + 1))
                                _new_b = sign_pdf_at_xy_pct(_pdf_b, _sig_e, _all_pages_e,
                                                            _ex, _ey, _ew)
                                for _r_e in st.session_state.batch_results:
                                    if _r_e["name"] == sel_r["name"]:
                                        _r_e["bytes"] = _new_b
                                        _r_e["out_name"] = _pdf_n
                                        _r_e["detail"] += " [đã chỉnh vị trí]"
                                        break
                                st.success("Đã cập nhật! Tải file ZIP bên dưới để lấy bản mới.")
                                st.rerun()
                        except Exception as _ee:
                            st.error(f"Lỗi: {_ee}")

            # ── Tải về ───────────────────────────────────────────────────
            st.divider()
            # CSS làm nút/link tải nổi bật
            st.markdown("""<style>
                [data-testid="stDownloadButton"] button {
                    background-color: #22c55e !important;
                    color: white !important;
                    font-weight: bold !important;
                    font-size: 1.1em !important;
                    border: none !important;
                    padding: 0.6em 1em !important;
                }
                .dl-link {
                    display: block; text-align: center; padding: 14px;
                    background: #22c55e; color: white !important;
                    border-radius: 8px; font-weight: bold; font-size: 1.1em;
                    text-decoration: none; margin: 6px 0;
                }
                .dl-link:active { background: #15803d; }
                .dl-link-small {
                    display: inline-block; padding: 8px 16px;
                    background: #3b82f6; color: white !important;
                    border-radius: 6px; text-decoration: none;
                    font-size: 0.9em; margin: 4px 0;
                }
            </style>""", unsafe_allow_html=True)

            import base64
            zip_bytes = create_zip(ok)
            _b64_zip = base64.b64encode(zip_bytes).decode()

            # Link tải chính (hoạt động trên cả iOS PWA và PC)
            st.markdown(
                f'<a class="dl-link" href="data:application/zip;base64,{_b64_zip}" '
                f'download="da_ky_hang_loat.zip">⬇️ Tải tất cả {len(ok)} file đã ký (ZIP)</a>',
                unsafe_allow_html=True)

            st.info(
                "📱 **iPhone**: Bấm link trên → chọn **Tải về** hoặc **Mở bằng Files**.\n\n"
                "💻 **Máy tính**: File tự tải vào thư mục **Downloads**."
            )

            with st.expander("Tải từng file riêng"):
                for r in ok:
                    ext = _ext(r["name"])
                    _mime = ("application/pdf" if ext == ".pdf" else
                            "image/png" if ext in (".png",".jpg",".jpeg") else
                            "application/vnd.openxmlformats-officedocument.wordprocessingml.document" if ext == ".docx" else
                            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
                    _fname = r.get("out_name", r["name"])
                    _b64 = base64.b64encode(r["bytes"]).decode()
                    st.markdown(
                        f'<a class="dl-link-small" href="data:{_mime};base64,{_b64}" '
                        f'download="{_fname}">⬇️ {_fname}</a>',
                        unsafe_allow_html=True)
