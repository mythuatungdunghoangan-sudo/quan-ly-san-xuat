"""
Ứng dụng ký tài liệu
- Ký một file: PDF/ảnh, tự động tìm vị trí hoặc chọn thủ công
- Ký hàng loạt: nhiều file hoặc cả thư mục, xuất ZIP
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
    "sig_areas": [], "selected_area_idx": 0, "last_file_id": None,
    "batch_results": [], "batch_files": [], "batch_orig_bytes": {},
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

if st.session_state.sig_active is None:
    st.session_state.sig_active = _find_chu_ky()

# ── PDF helpers ───────────────────────────────────────────────────────────────

def render_pdf_page(pdf_bytes: bytes, page_num: int) -> Image.Image:
    import fitz
    doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    pix = doc[page_num].get_pixmap(matrix=fitz.Matrix(PT_TO_PX,PT_TO_PX), alpha=False)
    return Image.frombytes("RGB",[pix.width,pix.height],pix.samples)

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

def sign_pdf_manual(pdf_bytes, sig_img, pages, position, width_pct, margin):
    import fitz
    buf=io.BytesIO(); sig_img.save(buf,"PNG"); sig_png=buf.getvalue()
    ar=sig_img.width/sig_img.height
    doc=fitz.open(stream=pdf_bytes,filetype="pdf")
    for i,page in enumerate(doc):
        if (i+1) not in pages: continue
        pw,ph=page.rect.width,page.rect.height
        sw=pw*width_pct/100; sh=sw/ar; m=float(margin)
        pos={"Trên trái":(m,m),"Trên phải":(pw-sw-m,m),
             "Dưới trái":(m,ph-sh-m),"Dưới phải":(pw-sw-m,ph-sh-m),
             "Giữa trang":((pw-sw)/2,(ph-sh)/2),"Giữa dưới":((pw-sw)/2,ph-sh-m)}
        x,y=pos.get(position,(pw-sw-m,ph-sh-m))
        page.insert_image(fitz.Rect(x,y,x+sw,y+sh),stream=sig_png)
    out=io.BytesIO(); doc.save(out); return out.getvalue()

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

def sign_image_file(img_bytes: bytes, img_name: str, sig_img,
                    position: str, width_pct: float, margin: int) -> bytes:
    """Ghép chữ ký lên file ảnh, trả về PNG bytes."""
    base = Image.open(io.BytesIO(img_bytes)).convert("RGB")
    bw, bh = base.size
    sw = max(30, int(bw * width_pct / 100))
    sh = int(sig_img.height * sw / sig_img.width)
    x, y = _manual_xy(bw, bh, sw, sh, position, margin)
    result = overlay_sig(base, sig_img, x, y, sw)
    buf = io.BytesIO()
    result.save(buf, "PNG")
    return buf.getvalue()

def scan_image_for_keywords(img: Image.Image) -> list:
    """OCR ảnh để tìm vị trí từ khóa. Trả về cùng format với scan_page_for_keywords."""
    try:
        import pytesseract
    except ImportError:
        return []
    # Chỉ đường dẫn Tesseract + tessdata tiếng Việt nằm trong thư mục app
    import sys, os
    if sys.platform == "win32":
        _tess = r"C:\Program Files\Tesseract-OCR\tesseract.exe"
        if os.path.exists(_tess):
            pytesseract.pytesseract.tesseract_cmd = _tess
    _local_tessdata = str(_APP_DIR / "tessdata")
    if os.path.isdir(_local_tessdata):
        os.environ["TESSDATA_PREFIX"] = _local_tessdata
        lang_str = 'vie+eng'
    else:
        try:
            langs = pytesseract.get_languages()
            lang_str = 'vie+eng' if 'vie' in langs else 'eng'
        except Exception:
            lang_str = 'eng'
    try:
        data = pytesseract.image_to_data(img, output_type=pytesseract.Output.DICT,
                                          lang=lang_str, config='--psm 6')
    except Exception:
        return []
    from collections import defaultdict
    lines = defaultdict(lambda: {'texts': [], 'boxes': []})
    for i in range(len(data['text'])):
        if int(data['conf'][i]) < 0:
            continue
        key = (data['page_num'][i], data['block_num'][i],
               data['par_num'][i],  data['line_num'][i])
        t = data['text'][i].strip()
        if t:
            lines[key]['texts'].append(t)
            lines[key]['boxes'].append((
                data['left'][i], data['top'][i],
                data['left'][i] + data['width'][i],
                data['top'][i] + data['height'][i],
            ))
    found, seen = [], []
    for key in sorted(lines.keys()):
        ld = lines[key]
        if not ld['texts']:
            continue
        line_norm = _strip_accents(' '.join(ld['texts']))
        for entry in SIGN_KEYWORDS:
            if _strip_accents(entry['kw']) in line_norm:
                x0 = min(b[0] for b in ld['boxes'])
                y0 = min(b[1] for b in ld['boxes'])
                x1 = max(b[2] for b in ld['boxes'])
                y1 = max(b[3] for b in ld['boxes'])
                if any(abs(y0 - s) < 8 for s in seen):
                    continue
                seen.append(y0)
                found.append({
                    'keyword': entry['kw'], 'label': entry['label'],
                    'place': entry['place'], 'priority': entry.get('priority', 5),
                    'v_offset': entry.get('v_offset'),
                    'px': (x0, y0, x1, y1), 'pt': (x0, y0, x1, y1),
                })
                break
    found.sort(key=lambda a: (a.get('priority', 5), a['px'][1]))
    return found

def sign_image_auto(img_bytes: bytes, sig_img, area: dict,
                    width_pct: float, v_offset: float) -> bytes:
    """Ký ảnh theo vị trí từ khóa OCR."""
    base = Image.open(io.BytesIO(img_bytes)).convert("RGB")
    bw, bh = base.size
    sw = max(30, int(bw * width_pct / 100))
    sh = int(sig_img.height * sw / sig_img.width)
    eff_v = area['v_offset'] if area.get('v_offset') is not None else v_offset
    x_px, y_px = _sig_xy_px(area, sh, eff_v)
    result = overlay_sig(base, sig_img, x_px, y_px, sw)
    buf = io.BytesIO()
    result.save(buf, "PNG")
    return buf.getvalue()

_SIGN_KW_XL = [
    "công ty hoàng an", "cong ty hoang an",
    "nguyễn minh hoàng", "nguyen minh hoang",
    "bên sản xuất", "nhà sản xuất", "xác nhận nhà sản xuất",
]

def find_excel_sig_position(excel_bytes: bytes) -> tuple:
    """Tìm row/col/colOff để ký ngay dưới keyword, căn giữa vùng merge.
    Trả về (row_1based, col_0based, found_text, col_off_emu)."""
    from openpyxl import load_workbook
    try:
        # load_workbook không save → không corrupt file
        wb = load_workbook(io.BytesIO(excel_bytes), data_only=True)
        ws = wb.active

        target_row = target_col = None
        target_text = ""
        for row_cells in ws.iter_rows():
            for cell in row_cells:
                if not (cell.value and isinstance(cell.value, str)):
                    continue
                val = cell.value.strip()
                for kw in _SIGN_KW_XL:
                    if kw in val.lower():
                        target_row  = cell.row      # 1-based
                        target_col  = cell.column   # 1-based
                        target_text = val[:50]
                        break
                if target_row:
                    break
            if target_row:
                break

        if not target_row:
            wb.close()
            return None, None, None, 0

        # Tìm vùng merge chứa cell này
        min_col, max_col = target_col, target_col
        for merge in ws.merged_cells.ranges:
            if (merge.min_row <= target_row <= merge.max_row and
                    merge.min_col <= target_col <= merge.max_col):
                min_col = merge.min_col
                max_col = merge.max_col
                break

        # Tính tổng chiều rộng vùng merge → đặt chữ ký căn giữa
        def _col_emu(col_idx):
            from openpyxl.utils import get_column_letter
            letter = get_column_letter(col_idx)
            dim = ws.column_dimensions.get(letter)
            px = int((dim.width if dim and dim.width else 8.43) * 7 + 5)
            return px * 9525

        total_w_emu = sum(_col_emu(c) for c in range(min_col, max_col + 1))
        sig_w_emu   = 160 * 9525
        col_off_emu = max(0, (total_w_emu - sig_w_emu) // 2)

        wb.close()
        # row 1-based (dòng ký = ngay dưới keyword), col 0-based
        return target_row, min_col - 1, target_text, col_off_emu

    except Exception:
        pass
    return None, None, None, 0


def sign_excel_file(excel_bytes: bytes, sig_img, position: str,
                    width_px: int = 160, height_px: int = 80) -> tuple:
    """
    Chèn chữ ký vào xlsx bằng zipfile trực tiếp.
    - Tự tìm vị trí keyword (CÔNG TY HOÀNG AN, v.v.)
    - oneCellAnchor + giữ đúng tỉ lệ ảnh → không méo
    - Không dùng openpyxl save → không corrupt drawing cũ
    Trả về (bytes, info_str).
    """
    import zipfile, re
    from openpyxl import load_workbook

    # ── Tìm vị trí ký trong file ──────────────────────────────────────────────
    sig_row_0, sig_col_0, found_text, col_off_emu = find_excel_sig_position(excel_bytes)

    if sig_row_0 is None:
        # Fallback: dùng position tham số
        try:
            wb_ro = load_workbook(io.BytesIO(excel_bytes), read_only=True)
            max_row = max((ws.max_row or 30 for ws in wb_ro.worksheets), default=30)
            wb_ro.close()
        except Exception:
            max_row = 40
        col_map = {"Dưới phải":7,"Trên phải":7,"Dưới trái":0,"Trên trái":0,
                   "Giữa trang":3,"Giữa dưới":3}
        row_map = {"Dưới phải":max_row,"Dưới trái":max_row,"Giữa dưới":max_row,
                   "Trên phải":0,"Trên trái":0,"Giữa trang":max(0,max_row//2)}
        sig_col_0   = col_map.get(position, 7)
        sig_row_0   = row_map.get(position, max_row)
        col_off_emu = 0
        info = f"Không tìm thấy keyword → đặt theo vị trí {position}"
    else:
        info = f"Tìm thấy [{found_text}] → ký row {sig_row_0+1}, căn giữa (offset {col_off_emu//9525}px)"

    # ── Chuẩn bị ảnh, giữ đúng tỉ lệ (oneCellAnchor) ─────────────────────────
    sig_buf = io.BytesIO()
    sig_img.convert("RGBA").save(sig_buf, "PNG")
    sig_png = sig_buf.getvalue()
    # EMU: dùng width cố định, tính height theo tỉ lệ ảnh
    w_emu = width_px * 9525
    h_emu = int(sig_img.height / sig_img.width * w_emu)

    in_buf = io.BytesIO(excel_bytes)
    out_buf = io.BytesIO()

    with zipfile.ZipFile(in_buf, 'r') as zin:
        all_names = zin.namelist()

        # Tên ảnh mới tránh trùng
        existing_imgs = [n for n in all_names if n.startswith('xl/media/image')]
        new_idx = len(existing_imgs) + 1
        new_img_path = f"xl/media/image{new_idx}.png"
        while new_img_path in all_names:
            new_idx += 1; new_img_path = f"xl/media/image{new_idx}.png"
        new_img_base = new_img_path.split('/')[-1]

        drw_path = next(
            (n for n in all_names
             if n.startswith('xl/drawings/drawing') and n.endswith('.xml')
             and '_rels' not in n), None)
        if drw_path is None:
            return excel_bytes, "Không có drawing trong file"

        drw_rels_path = f"xl/drawings/_rels/{drw_path.split('/')[-1]}.rels"
        drw_xml  = zin.read(drw_path).decode('utf-8')
        drw_rels = (zin.read(drw_rels_path).decode('utf-8') if drw_rels_path in all_names
                    else '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
                         '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
                         '</Relationships>')

        used_rids  = [int(x) for x in re.findall(r'Id="rId(\d+)"', drw_rels)]
        new_rid    = f"rId{max(used_rids, default=0) + 1}"
        used_ids   = [int(x) for x in re.findall(r'\bid="(\d+)"', drw_xml)]
        new_pic_id = max(used_ids, default=1) + 1

        # oneCellAnchor: ảnh kích thước cố định, không bị kéo dãn
        anchor = (
            f'<xdr:oneCellAnchor>'
            f'<xdr:from>'
            f'<xdr:col>{sig_col_0}</xdr:col><xdr:colOff>{col_off_emu}</xdr:colOff>'
            f'<xdr:row>{sig_row_0}</xdr:row><xdr:rowOff>57150</xdr:rowOff>'
            f'</xdr:from>'
            f'<xdr:ext cx="{w_emu}" cy="{h_emu}"/>'
            f'<xdr:pic><xdr:nvPicPr>'
            f'<xdr:cNvPr id="{new_pic_id}" name="ChuKyHoangAn"/>'
            f'<xdr:cNvPicPr><a:picLocks noChangeAspect="1"/></xdr:cNvPicPr>'
            f'</xdr:nvPicPr><xdr:blipFill>'
            f'<a:blip xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"'
            f' r:embed="{new_rid}"/>'
            f'<a:stretch><a:fillRect/></a:stretch>'
            f'</xdr:blipFill><xdr:spPr>'
            f'<a:xfrm><a:off x="0" y="0"/><a:ext cx="{w_emu}" cy="{h_emu}"/></a:xfrm>'
            f'<a:prstGeom prst="rect"><a:avLst/></a:prstGeom>'
            f'</xdr:spPr></xdr:pic><xdr:clientData/>'
            f'</xdr:oneCellAnchor>'
        )
        new_drw_xml  = drw_xml.replace('</xdr:wsDr>', anchor + '</xdr:wsDr>')
        new_rel      = (f'<Relationship Id="{new_rid}"'
                        f' Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/image"'
                        f' Target="../media/{new_img_base}"/>')
        new_drw_rels = drw_rels.replace('</Relationships>', new_rel + '</Relationships>')

        with zipfile.ZipFile(out_buf, 'w', zipfile.ZIP_DEFLATED) as zout:
            for name in all_names:
                if name == drw_path:
                    zout.writestr(name, new_drw_xml.encode('utf-8'))
                elif name == drw_rels_path:
                    zout.writestr(name, new_drw_rels.encode('utf-8'))
                else:
                    zout.writestr(name, zin.read(name))
            zout.writestr(new_img_path, sig_png)

    return out_buf.getvalue(), info

def sign_word_file(docx_bytes: bytes, sig_img, width_cm: float = 4.0) -> tuple:
    """Chèn chữ ký vào Word (.docx). Tìm keyword rồi thêm ảnh sau đó, hoặc cuối tài liệu."""
    from docx import Document
    from docx.shared import Cm
    from docx.oxml import OxmlElement
    from docx.text.paragraph import Paragraph as DocxParagraph

    doc = Document(io.BytesIO(docx_bytes))

    sig_buf = io.BytesIO()
    sig_img.convert("RGB").save(sig_buf, "PNG")
    sig_buf.seek(0)

    target_para = None
    found_kw = None

    def _search(paras):
        nonlocal target_para, found_kw
        for para in paras:
            t = para.text.lower()
            for kw in _SIGN_KW_XL:
                if kw in t:
                    target_para = para; found_kw = kw; return True
        return False

    _search(doc.paragraphs)
    if not target_para:
        for table in doc.tables:
            for row in table.rows:
                for cell in row.cells:
                    if _search(cell.paragraphs): break
                if target_para: break
            if target_para: break

    if target_para:
        new_p = OxmlElement('w:p')
        target_para._p.addnext(new_p)
        new_para = DocxParagraph(new_p, target_para._parent)
        run = new_para.add_run()
        run.add_picture(sig_buf, width=Cm(width_cm))
        info = f"Tìm thấy [{found_kw}] → ký ngay dưới"
    else:
        para = doc.add_paragraph()
        run = para.add_run()
        run.add_picture(sig_buf, width=Cm(width_cm))
        info = "Không tìm thấy keyword → ký ở cuối tài liệu"

    out_buf = io.BytesIO()
    doc.save(out_buf)
    return out_buf.getvalue(), info

def create_zip(results: list) -> bytes:
    """Tạo ZIP từ danh sách kết quả ký hàng loạt."""
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        for r in results:
            if r.get("bytes"):
                zf.writestr(r.get("out_name", f"da_ky_{r['name']}"), r["bytes"])
    return buf.getvalue()

def _ext(name: str) -> str:
    return Path(name).suffix.lower()

def process_one_file(name: str, data: bytes, sig_img, kw, place,
                     pages_mode: str, width_pct: float, v_offset: float,
                     kw_v_offset=None,
                     img_position: str = "Dưới phải", img_margin: int = 35) -> dict:
    """Ký một file (PDF / ảnh / Excel). Trả về dict kết quả."""
    ext = _ext(name)
    try:
        if ext == ".pdf":
            total = get_total_pages(data)
            pages = list(range(1, total+1)) if pages_mode == "Tất cả trang" else [total]
            if kw is None:
                out, signed = sign_pdf_bottom_center(data, sig_img, pages, width_pct)
                detail = f"Ký {len(signed)} trang (vùng trống cuối — không có từ khóa HA)"
            else:
                # Ưu tiên v_offset từ keyword (tu_khoa.txt), sau đó mới dùng slider
                effective_offset = kw_v_offset if kw_v_offset is not None else v_offset
                out, signed, skipped = sign_pdf_auto(data, sig_img, pages, kw, place,
                                                      width_pct, effective_offset)
                offset_note = f" [kc={int(effective_offset)}pt]" if kw_v_offset is not None else ""
                detail = f"Ký {len(signed)} trang theo [{kw}]{offset_note}"
                if skipped:
                    detail += f" | bỏ qua trang {skipped}"
            out_name = f"da_ky_{name}"
        elif ext in (".png", ".jpg", ".jpeg"):
            _base_img = Image.open(io.BytesIO(data)).convert("RGB")
            _img_areas = scan_image_for_keywords(_base_img)
            _ha = [a for a in _img_areas if a.get("priority", 5) <= HA_PRIORITY_MAX]
            if _ha:
                out = sign_image_auto(data, sig_img, _ha[0], width_pct, v_offset)
                detail = f"OCR: [{_ha[0]['keyword']}] → ký bên dưới"
            else:
                out = sign_image_file(data, name, sig_img, img_position, width_pct, img_margin)
                detail = "Ghép chữ ký (vị trí thủ công)"
            out_name = f"da_ky_{Path(name).stem}.png"
        elif ext in (".xlsx", ".xls"):
            out, xl_info = sign_excel_file(data, sig_img, img_position)
            detail = xl_info
            out_name = f"da_ky_{name}"
        elif ext == ".docx":
            out, word_info = sign_word_file(data, sig_img)
            detail = word_info
            out_name = f"da_ky_{name}"
        else:
            return {"name": name, "status": "⏭️ Bỏ qua",
                    "detail": f"Định dạng {ext} chưa hỗ trợ", "bytes": None, "out_name": name}

        return {"name": name, "status": "✅ OK", "detail": detail,
                "bytes": out, "out_name": out_name}
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
            if sf:
                loaded = Image.open(sf)
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

tab_single, tab_batch = st.tabs(["📄 Ký một file", "📚 Ký hàng loạt"])

# ═══════════════════════════════════════════════════════════════════════════════
# TAB 1 — Ký một file
# ═══════════════════════════════════════════════════════════════════════════════
with tab_single:
    uploaded_doc = st.file_uploader(
        "Tải lên tài liệu cần ký (PDF, ảnh, Excel hoặc Word)",
        type=["pdf","png","jpg","jpeg","xlsx","xls","docx"], key="single_upload")
    if not uploaded_doc:
        st.info("Tải lên file để bắt đầu.")
    else:
        doc_bytes = uploaded_doc.read()
        _ext_s    = uploaded_doc.name.lower()
        is_pdf    = _ext_s.endswith(".pdf")
        is_excel  = _ext_s.endswith((".xlsx", ".xls"))
        is_word   = _ext_s.endswith(".docx")
        file_id   = uploaded_doc.name + str(len(doc_bytes))
        if st.session_state.last_file_id != file_id:
            st.session_state.last_file_id  = file_id
            st.session_state.sig_areas     = []
            st.session_state.selected_area_idx = 0

        if is_pdf:
            import fitz as _fitz
            _tmp = _fitz.open(stream=doc_bytes, filetype="pdf")
            total_pages = _tmp.page_count
            _tmp.close()

        st.divider()
        col_left, col_right = st.columns([1, 2], gap="large")

        # ══════════════════════════════════════════════════════════════════════
        # EXCEL — Tab 1
        # ══════════════════════════════════════════════════════════════════════
        if is_excel:
            sig = st.session_state.sig_active
            # Tìm vị trí ký ngay lúc upload (read-only, không corrupt)
            xl_row, xl_col, xl_text, xl_off = find_excel_sig_position(doc_bytes)

            with col_left:
                st.subheader("📊 Vị trí chữ ký trong Excel")
                if xl_row:
                    st.success(f"Tìm thấy: **\"{xl_text}\"**")
                    st.info(f"Chữ ký sẽ đặt ngay bên dưới, **Row {xl_row + 1}**, căn giữa ô đó.")
                else:
                    st.warning("Không tìm thấy keyword Hoàng An trong file.")
                    st.caption("Sẽ đặt chữ ký ở cuối trang theo vị trí chọn bên dưới.")
                    xl_pos = st.selectbox("Vị trí fallback",
                        ["Dưới phải","Dưới trái","Giữa dưới"], key="s_xl_pos")

                st.divider()
                st.subheader("📥 Xuất file")
                if st.button("🖊 Xuất Excel đã ký", type="primary",
                             use_container_width=True, key="s_xl_export"):
                    stem = Path(uploaded_doc.name).stem
                    with st.spinner("Đang xử lý..."):
                        try:
                            pos_arg = "Dưới phải" if xl_row else locals().get("xl_pos","Dưới phải")
                            out, xl_info = sign_excel_file(doc_bytes, sig, pos_arg)
                            st.download_button(
                                "⬇️ Tải Excel đã ký", data=out,
                                file_name=f"da_ky_{stem}.xlsx",
                                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                                use_container_width=True)
                            st.success(xl_info)
                        except Exception as e:
                            st.error(f"Lỗi: {e}")

            with col_right:
                st.subheader("👁 Xem trước nội dung Excel")
                try:
                    import pandas as pd
                    from openpyxl import load_workbook as _lw
                    _wb = _lw(io.BytesIO(doc_bytes), read_only=True, data_only=True)
                    _ws = _wb.active
                    _rows = [[c.value for c in r]
                             for r in _ws.iter_rows(max_row=min(_ws.max_row or 50, 60))]
                    _wb.close()
                    _df = pd.DataFrame(_rows).fillna("")
                    st.dataframe(_df, use_container_width=True, hide_index=True)
                    if xl_row:
                        st.caption(f"🟢 Chữ ký đặt tại **Row {xl_row + 1}** "
                                   f"(ngay dưới \"{xl_text}\"), căn giữa ô merge.")
                except Exception as ep:
                    st.info(f"Không hiển thị được bảng: {ep}")

        # ══════════════════════════════════════════════════════════════════════
        # WORD — Tab 1
        # ══════════════════════════════════════════════════════════════════════
        elif is_word:
            sig = st.session_state.sig_active
            with col_left:
                st.subheader("📝 Ký file Word")
                width_cm = st.slider("Kích thước chữ ký (cm)", 2.0, 10.0, 4.0, 0.5, key="s_word_w")
                st.divider()
                st.subheader("📥 Xuất file")
                if st.button("🖊 Xuất Word đã ký", type="primary",
                             use_container_width=True, key="s_word_export"):
                    stem = Path(uploaded_doc.name).stem
                    with st.spinner("Đang xử lý..."):
                        try:
                            out, word_info = sign_word_file(doc_bytes, sig, width_cm)
                            st.download_button(
                                "⬇️ Tải Word đã ký", data=out,
                                file_name=f"da_ky_{stem}.docx",
                                mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                                use_container_width=True)
                            st.success(word_info)
                        except Exception as e:
                            st.error(f"Lỗi: {e}")
            with col_right:
                st.subheader("👁 Xem trước")
                st.info("Word không hỗ trợ xem trước. Xuất file rồi mở bằng Word để kiểm tra.")

        # ══════════════════════════════════════════════════════════════════════
        # PDF + ẢNH — Tab 1
        # ══════════════════════════════════════════════════════════════════════
        else:
            with col_left:
                if is_pdf:
                    st.subheader("📋 Trang ký")
                    apply_all = st.checkbox(f"Ký tất cả {total_pages} trang", value=False, key="s_all")
                    selected_pages = (list(range(1, total_pages+1)) if apply_all else
                                     st.multiselect("Chọn trang", list(range(1, total_pages+1)),
                                                   default=[total_pages],
                                                   format_func=lambda p: f"Trang {p}", key="s_pages"))
                    preview_page = st.selectbox("Trang xem trước", list(range(1, total_pages+1)),
                                               index=(selected_pages[-1]-1) if selected_pages else 0,
                                               format_func=lambda p: f"Trang {p}", key="s_prev")
                else:
                    selected_pages, preview_page = [], 1

                st.divider()
                st.subheader("⚙️ Vị trí chữ ký")
                mode = st.radio("Chế độ", ["🤖 Tự động tìm vị trí", "✋ Chọn vị trí thủ công"],
                               label_visibility="collapsed", key="s_mode")
                width_pct = st.slider("Kích thước (% chiều rộng trang)", 5, 60, 22, key="s_w")

                chosen_area = None; v_offset = 4; position = "Dưới phải"; margin = 35
                x_pct = y_pct = 0

                if mode == "🤖 Tự động tìm vị trí":
                    if not is_pdf:
                        if st.button("🔍 Quét ảnh tìm vị trí ký (OCR)", use_container_width=True, key="s_scan"):
                            with st.spinner("Đang OCR..."):
                                try:
                                    _base_scan = Image.open(io.BytesIO(doc_bytes)).convert("RGB")
                                    areas = scan_image_for_keywords(_base_scan)
                                except Exception as _ex:
                                    areas = []
                                    st.error(f"OCR lỗi: {_ex}")
                            st.session_state.sig_areas = areas
                            st.session_state.selected_area_idx = 0
                            if not areas:
                                st.warning("Không tìm thấy từ khóa (cần cài Tesseract). Dùng thủ công.")
                    else:
                        if st.button("🔍 Quét tài liệu tìm vị trí ký", use_container_width=True, key="s_scan"):
                            with st.spinner("Đang quét..."):
                                areas = scan_page_for_keywords(doc_bytes, preview_page - 1)
                            st.session_state.sig_areas = areas
                            st.session_state.selected_area_idx = 0
                            if not areas:
                                st.warning("Không tìm thấy từ khóa nào. Thử thủ công.")
                    areas = st.session_state.sig_areas
                    if areas:
                        st.success(f"Tìm thấy **{len(areas)}** vị trí")
                        if is_pdf:
                            labels = [f"{a['label']}  (dòng {int(a['pt'][1])} pt)" for a in areas]
                        else:
                            labels = [f"{a['label']}  (y={int(a['px'][1])} px)" for a in areas]
                        idx = st.radio("Chọn vị trí đặt chữ ký", range(len(labels)),
                                      format_func=lambda i: labels[i],
                                      index=min(st.session_state.selected_area_idx, len(areas)-1),
                                      key="s_area")
                        st.session_state.selected_area_idx = idx
                        chosen_area = areas[idx]
                        hint = "bên dưới" if chosen_area["place"] == "below" else "bên trên"
                        kw_default_offset = chosen_area.get("v_offset")
                        unit = "px" if not is_pdf else "điểm PDF"
                        if kw_default_offset is not None:
                            st.caption(f"Chữ ký sẽ đặt **{hint}** — khoảng cách mặc định: **{int(kw_default_offset)} {unit}**")
                        else:
                            st.caption(f"Chữ ký sẽ đặt **{hint}** dòng chữ này.")
                        default_slider = int(kw_default_offset) if kw_default_offset is not None else 4
                        v_offset = st.slider(f"Điều chỉnh khoảng cách ({unit})", -30, 120,
                                            default_slider, key="s_vo",
                                            help="Dương = dịch ra xa | Âm = dịch vào gần")
                else:
                    if not is_pdf:
                        st.markdown("**📍 Di chuyển chữ ký tự do**")
                        img_pos_mode = st.radio("Kiểu đặt vị trí",
                            ["🎯 Kéo thả tự do (X/Y)", "📌 Chọn góc cố định"],
                            horizontal=True, key="s_img_posmode")
                        if img_pos_mode == "🎯 Kéo thả tự do (X/Y)":
                            x_pct = st.slider("↔ Vị trí ngang (% từ trái)", 0, 95, 65, key="s_xpct")
                            y_pct = st.slider("↕ Vị trí dọc  (% từ trên)", 0, 95, 70, key="s_ypct")
                            position = "__FREE__"
                            margin = 0
                        else:
                            position = st.selectbox("Vị trí",
                                ["Dưới phải","Dưới trái","Giữa dưới","Trên phải","Trên trái","Giữa trang"], key="s_pos")
                            margin = st.slider("Khoảng cách lề", 5, 150, 35, key="s_mg")
                    else:
                        position = st.selectbox("Vị trí",
                            ["Dưới phải","Dưới trái","Giữa dưới","Trên phải","Trên trái","Giữa trang"], key="s_pos")
                        margin = st.slider("Khoảng cách lề", 5, 150, 35, key="s_mg")

                st.divider(); st.subheader("📥 Xuất file")
                can_export = True
                if is_pdf and not selected_pages:
                    st.warning("Chưa chọn trang."); can_export = False
                if mode == "🤖 Tự động tìm vị trí" and not chosen_area:
                    st.info("Quét và chọn vị trí trước."); can_export = False

                if can_export and st.button("🖊 Xuất file đã ký", type="primary",
                                            use_container_width=True, key="s_export"):
                    stem = Path(uploaded_doc.name).stem
                    sig  = st.session_state.sig_active
                    with st.spinner("Đang xử lý..."):
                        try:
                            if is_pdf:
                                if mode == "🤖 Tự động tìm vị trí" and chosen_area:
                                    out, signed, skipped = sign_pdf_auto(
                                        doc_bytes, sig, selected_pages,
                                        chosen_area["keyword"], chosen_area["place"], width_pct, v_offset)
                                    st.download_button("⬇️ Tải PDF đã ký", data=out,
                                        file_name=f"da_ky_{stem}.pdf", mime="application/pdf",
                                        use_container_width=True)
                                    if signed: st.success(f"Đã ký {len(signed)} trang: {signed}")
                                    if skipped: st.warning(f"Không tìm thấy từ khóa ở trang {skipped}.")
                                else:
                                    out = sign_pdf_manual(doc_bytes, sig, selected_pages,
                                                          position, width_pct, margin)
                                    st.download_button("⬇️ Tải PDF đã ký", data=out,
                                        file_name=f"da_ky_{stem}.pdf", mime="application/pdf",
                                        use_container_width=True)
                                    st.success(f"Đã ký {len(selected_pages)} trang.")
                            else:
                                if mode == "🤖 Tự động tìm vị trí" and chosen_area:
                                    out = sign_image_auto(doc_bytes, sig, chosen_area, width_pct, v_offset)
                                    st.download_button("⬇️ Tải ảnh đã ký", data=out,
                                        file_name=f"da_ky_{stem}.png", mime="image/png",
                                        use_container_width=True)
                                    st.success(f"Đã ký theo [{chosen_area['keyword']}].")
                                else:
                                    base = Image.open(io.BytesIO(doc_bytes)).convert("RGB")
                                    bw, bh = base.size
                                    sw = max(30, int(bw * width_pct / 100))
                                    sh = int(sig.height * sw / sig.width)
                                    if position == "__FREE__":
                                        x, y = int(bw * x_pct / 100), int(bh * y_pct / 100)
                                    else:
                                        x, y = _manual_xy(bw, bh, sw, sh, position, margin)
                                    result = overlay_sig(base, sig, x, y, sw)
                                    buf = io.BytesIO(); result.save(buf, "PNG")
                                    st.download_button("⬇️ Tải ảnh đã ký", data=buf.getvalue(),
                                        file_name=f"da_ky_{stem}.png", mime="image/png",
                                        use_container_width=True)
                                    st.success("Xong.")
                        except Exception as e:
                            st.error(f"Lỗi: {e}")

            with col_right:
                st.subheader("👁 Xem trước")
                sig = st.session_state.sig_active
                try:
                    base_img = (render_pdf_page(doc_bytes, preview_page - 1) if is_pdf
                               else Image.open(io.BytesIO(doc_bytes)).convert("RGB"))
                    bw, bh = base_img.size
                    sw_px = max(30, int(bw * width_pct / 100))
                    sh_px = int(sig.height * sw_px / sig.width)
                    if mode == "🤖 Tự động tìm vị trí" and chosen_area:
                        v_off_px = v_offset if not is_pdf else v_offset * PT_TO_PX
                        x_px, y_px = _sig_xy_px(chosen_area, sh_px, v_off_px)
                        preview = overlay_sig(base_img, sig, x_px, y_px, sw_px,
                                             highlight_px=chosen_area["px"])
                        st.image(preview, use_container_width=True)
                        st.caption("🟠 Khung cam = từ khóa tìm thấy  |  chữ ký đặt "
                                  + ("bên dưới" if chosen_area["place"] == "below" else "bên trên"))
                    else:
                        if not is_pdf and position == "__FREE__":
                            x_px, y_px = int(bw * x_pct / 100), int(bh * y_pct / 100)
                        else:
                            x_px, y_px = _manual_xy(bw, bh, sw_px, sh_px, position, margin)
                        preview = overlay_sig(base_img, sig, x_px, y_px, sw_px)
                        st.image(preview, use_container_width=True)
                        if mode == "🤖 Tự động tìm vị trí":
                            areas = st.session_state.sig_areas
                            if areas:
                                ha_areas = [a for a in areas if a.get("priority", 5) <= HA_PRIORITY_MAX]
                                if not ha_areas and is_pdf:
                                    st.warning("Không có từ khóa Hoàng An → chữ ký sẽ đặt ở **vùng trống cuối trang, căn giữa**.")
                            else:
                                st.info("Nhấn **Quét** để tìm vị trí tự động.")
                except Exception as e:
                    st.error(f"Lỗi xem trước: {e}")

# ═══════════════════════════════════════════════════════════════════════════════
# TAB 2 — Ký hàng loạt
# ═══════════════════════════════════════════════════════════════════════════════
with tab_batch:
    st.markdown("Ký nhiều file PDF cùng lúc — chọn file upload hoặc nhập đường dẫn thư mục.")
    col_b1, col_b2 = st.columns([1,1], gap="large")

    with col_b1:
        # ── Nguồn file ───────────────────────────────────────────────────────
        st.subheader("📂 Nguồn file")
        source = st.radio("Chọn cách lấy file",
                         ["📤 Upload nhiều file","🗂️ Nhập đường dẫn thư mục"],
                         label_visibility="collapsed", key="b_source")

        files_data = []  # list of (name, bytes)

        if source == "📤 Upload nhiều file":
            uploaded_many = st.file_uploader(
                "Chọn nhiều file (PDF, ảnh, Excel, Word)",
                type=["pdf","png","jpg","jpeg","xlsx","xls","docx"],
                accept_multiple_files=True, key="b_upload")
            if uploaded_many:
                files_data = [(f.name, f.read()) for f in uploaded_many]
                st.success(f"Đã chọn {len(files_data)} file")
                with st.expander("Danh sách file"):
                    for name, data in files_data:
                        st.text(f"  • {name}  ({len(data)//1024} KB)")
        else:
            folder_input = st.text_input(
                "Đường dẫn thư mục",
                placeholder=r"Ví dụ: D:\OneDrive\DonHang",
                key="b_folder")
            recursive = st.checkbox("Bao gồm thư mục con", value=False, key="b_rec")

            if st.button("🔎 Quét thư mục", use_container_width=True, key="b_scan_folder"):
                p = Path(folder_input.strip().strip('"').strip("'"))
                if not p.exists() or not p.is_dir():
                    st.error(f"Thư mục không tồn tại: `{p}`\n\nKiểm tra lại đường dẫn.")
                else:
                    pattern = "**/*.pdf" if recursive else "*.pdf"
                    exts = {"*.pdf","*.PDF","*.png","*.jpg","*.jpeg","*.xlsx","*.xls"}
                    all_files = []
                    for ext in exts:
                        all_files += list(p.glob(f"**/{ext}" if recursive else ext))
                    all_files = sorted(set(all_files))
                    if not all_files:
                        st.warning("Không tìm thấy file nào (PDF/ảnh/Excel) trong thư mục.")
                    else:
                        loaded = []
                        for fp in all_files:
                            try: loaded.append((fp.name, fp.read_bytes()))
                            except: pass
                        st.session_state.batch_files = loaded
                        st.success(f"Tìm thấy {len(loaded)} file")

            if st.session_state.batch_files:
                files_data = st.session_state.batch_files
                with st.expander(f"Danh sách {len(files_data)} file"):
                    for name, data in files_data:
                        st.text(f"  • {name}  ({len(data)//1024} KB)")

        st.divider()

        # ── Cài đặt ký ───────────────────────────────────────────────────────
        st.subheader("⚙️ Cài đặt ký hàng loạt")

        kw_mode = st.radio("Từ khóa tìm vị trí",
                          ["🤖 Tự động (thử tất cả từ khóa)", "🎯 Chọn từ khóa cụ thể"],
                          key="b_kwmode")

        specific_kw, specific_place = None, None
        if kw_mode == "🎯 Chọn từ khóa cụ thể":
            chosen_label = st.selectbox("Từ khóa", _UNIQUE_LABELS, key="b_kwsel")
            entry = _LABEL_TO_ENTRY[chosen_label]
            specific_kw, specific_place = entry["kw"], entry["place"]
            place_hint = "bên dưới" if specific_place=="below" else "bên trên"
            st.caption(f"Chữ ký sẽ đặt **{place_hint}** dòng chữ này.")

        pages_mode = st.radio("Trang ký PDF",["Tất cả trang","Chỉ trang cuối"],
                             horizontal=True, key="b_pgmode")
        b_width = st.slider("Kích thước chữ ký (% chiều rộng)",5,60,22,key="b_w")
        b_voffset = st.slider("Khoảng cách từ từ khóa — PDF (điểm)",-30,80,4,key="b_vo")
        b_img_pos = st.selectbox("Vị trí ký — ảnh/Excel",
            ["Dưới phải","Dưới trái","Giữa dưới","Trên phải","Trên trái"],key="b_ipos")
        b_margin = st.slider("Lề — ảnh (px)",5,150,35,key="b_mg")

        st.divider()

        # ── Bắt đầu ký ───────────────────────────────────────────────────────
        ready = bool(files_data)
        if not ready:
            st.info("Chọn file hoặc quét thư mục trước.")

        if ready and st.button("▶️ Bắt đầu ký hàng loạt",type="primary",
                               use_container_width=True, key="b_go"):
            sig = st.session_state.sig_active
            results = []
            progress_bar = st.progress(0, text="Đang xử lý...")
            status_box = st.empty()

            for i, (name, data) in enumerate(files_data):
                status_box.text(f"Đang xử lý: {name}  ({i+1}/{len(files_data)})")

                # Tìm keyword
                if kw_mode == "🤖 Tự động (thử tất cả từ khóa)":
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
                    # Excel: hiện bảng dữ liệu + vị trí chữ ký
                    try:
                        import pandas as pd
                        from openpyxl import load_workbook as _lw
                        wb_p = _lw(io.BytesIO(sel_r["bytes"]), read_only=True, data_only=True)
                        ws_p = wb_p.active
                        rows_p = [[c.value for c in r] for r in ws_p.iter_rows(max_row=min(ws_p.max_row or 30, 50))]
                        wb_p.close()
                        df_p = pd.DataFrame(rows_p).fillna("")
                        st.dataframe(df_p, use_container_width=True, hide_index=True)
                        # Tìm vị trí chữ ký
                        row_s, col_s, txt_s, off_s = find_excel_sig_position(sel_r["bytes"])
                        if row_s:
                            st.success(f"Chữ ký đặt tại **Row {row_s+1}**, căn giữa bên dưới \"{txt_s}\" (offset {off_s//9525}px)")
                        else:
                            st.info("Không tìm thấy keyword — chữ ký đặt cuối trang.")
                    except Exception as ep:
                        st.info(f"Không xem trước được: {ep}")

                # ── Chỉnh vị trí cho file đang xem ──────────────────────────
                _orig_b = st.session_state.batch_orig_bytes.get(sel_r["name"])
                if _orig_b and ext_p in (".pdf", ".png", ".jpg", ".jpeg"):
                    with st.expander("✏️ Chỉnh vị trí chữ ký cho file này"):
                        _sig_e = st.session_state.sig_active
                        _ce1, _ce2 = st.columns(2)
                        with _ce1:
                            _ew = st.slider("Kích thước (% chiều rộng)", 5, 60, 22, key="b_ew")
                        with _ce2:
                            if ext_p == ".pdf":
                                _etotal = get_total_pages(_orig_b)
                                _epg = st.selectbox("Trang", list(range(1, _etotal+1)),
                                                    index=_etotal-1, key="b_epg")
                        _ex = st.slider("↔ Ngang (% từ trái)", 0, 95, 65, key="b_ex")
                        _ey = st.slider("↕ Dọc (% từ trên)",   0, 95, 70, key="b_ey")

                        # Preview cập nhật realtime khi kéo slider
                        try:
                            if ext_p == ".pdf":
                                _base_e = render_pdf_page(_orig_b, _epg - 1)
                            else:
                                _base_e = Image.open(io.BytesIO(_orig_b)).convert("RGB")
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
                                if ext_p == ".pdf":
                                    import fitz as _fz
                                    _sbuf = io.BytesIO(); _sig_e.save(_sbuf, "PNG")
                                    _spng = _sbuf.getvalue()
                                    _ar_e = _sig_e.width / _sig_e.height
                                    _doc_e = _fz.open(stream=_orig_b, filetype="pdf")
                                    for _pg_e in _doc_e:
                                        _pw_e, _ph_e = _pg_e.rect.width, _pg_e.rect.height
                                        _sw_e = _pw_e * _ew / 100
                                        _sh_e = _sw_e / _ar_e
                                        _x_e  = _pw_e * _ex / 100
                                        _y_e  = _ph_e * _ey / 100
                                        _pg_e.insert_image(
                                            _fz.Rect(_x_e, _y_e, _x_e+_sw_e, _y_e+_sh_e),
                                            stream=_spng)
                                    _out_e = io.BytesIO(); _doc_e.save(_out_e)
                                    _new_b = _out_e.getvalue()
                                else:
                                    _img_e = Image.open(io.BytesIO(_orig_b)).convert("RGB")
                                    _bw2, _bh2 = _img_e.size
                                    _sw2 = max(30, int(_bw2 * _ew / 100))
                                    _res_e = overlay_sig(_img_e, _sig_e,
                                                         int(_bw2 * _ex / 100),
                                                         int(_bh2 * _ey / 100), _sw2)
                                    _buf_e = io.BytesIO(); _res_e.save(_buf_e, "PNG")
                                    _new_b = _buf_e.getvalue()

                                for _r_e in st.session_state.batch_results:
                                    if _r_e["name"] == sel_r["name"]:
                                        _r_e["bytes"] = _new_b
                                        _r_e["detail"] += " [đã chỉnh vị trí]"
                                        break
                                st.success("Đã cập nhật! Tải file ZIP bên dưới để lấy bản mới.")
                                st.rerun()
                            except Exception as _ee:
                                st.error(f"Lỗi: {_ee}")

                # ── Tải về ───────────────────────────────────────────────────
                st.divider()
                zip_bytes = create_zip(ok)
                st.download_button(
                    f"⬇️ Tải tất cả {len(ok)} file đã ký (ZIP)",
                    data=zip_bytes,
                    file_name="da_ky_hang_loat.zip",
                    mime="application/zip",
                    use_container_width=True,
                )
                st.caption("File ZIP tải về nằm trong thư mục **Downloads** của trình duyệt. "
                           "Giải nén để lấy từng file.")

                with st.expander("Tải từng file riêng"):
                    for r in ok:
                        ext = _ext(r["name"])
                        mime = ("application/pdf" if ext == ".pdf" else
                                "image/png" if ext in (".png",".jpg",".jpeg") else
                                "application/vnd.openxmlformats-officedocument.wordprocessingml.document" if ext == ".docx" else
                                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
                        st.download_button(
                            f"⬇️ {r.get('out_name', r['name'])}",
                            data=r["bytes"],
                            file_name=r.get("out_name", f"da_ky_{r['name']}"),
                            mime=mime,
                            key=f"dl_{r['name']}",
                        )
