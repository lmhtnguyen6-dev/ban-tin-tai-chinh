# -*- coding: utf-8 -*-
"""
scraper.py
----------
Thu thập tin tài chính - địa chính trị TIẾNG VIỆT từ nhiều nguồn RSS,
ƯU TIÊN TIN VIỆT NAM, chấm "điểm hot" bằng code thuần (KHÔNG gọi AI),
gộp tin trùng và xuất ra data.json.

Cách chạy thủ công (test trên máy):
    pip install feedparser
    python scraper.py
"""

import json
import re
import html
from datetime import datetime, timezone, timedelta
from difflib import SequenceMatcher

import feedparser


# ---------------------------------------------------------------------------
# 1. DANH SÁCH NGUỒN RSS (CHỈ TIẾNG VIỆT)
# ---------------------------------------------------------------------------
# Mỗi nguồn gồm:
#   ten     : tên hiển thị
#   url     : URL feed
#   khu_vuc : "vn" (tin trong nước) hoặc "quoc_te" (tin quốc tế viết bằng TV)
#             -> dùng để đoán chủ đề mặc định khi tiêu đề không khớp từ khóa.
#
# GHI CHÚ:
#   - Đã BỎ toàn bộ feed tiếng Anh (Reuters, CNBC, Nikkei).
#   - Các URL dưới đây đã được kiểm tra thực tế và trả về tin.
#   - Nếu feed nào bị trống trong log -> nguồn đổi đường dẫn, hãy thay URL.
RSS_SOURCES = [
    # ----- CafeF -----
    {"ten": "CafeF Tài chính", "url": "https://cafef.vn/tai-chinh-ngan-hang.rss", "khu_vuc": "vn"},
    {"ten": "CafeF Vĩ mô", "url": "https://cafef.vn/vi-mo-dau-tu.rss", "khu_vuc": "vn"},
    {"ten": "CafeF Tài chính quốc tế", "url": "https://cafef.vn/tai-chinh-quoc-te.rss", "khu_vuc": "quoc_te"},

    # ----- VnExpress -----
    {"ten": "VnExpress Kinh doanh", "url": "https://vnexpress.net/rss/kinh-doanh.rss", "khu_vuc": "vn"},
    {"ten": "VnExpress Thế giới", "url": "https://vnexpress.net/rss/the-gioi.rss", "khu_vuc": "quoc_te"},

    # ----- Vietstock -----
    {"ten": "Vietstock Kinh tế", "url": "https://vietstock.vn/761/kinh-te.rss", "khu_vuc": "vn"},
    {"ten": "Vietstock Thế giới", "url": "https://vietstock.vn/772/the-gioi.rss", "khu_vuc": "quoc_te"},

    # ----- VietnamBiz -----
    {"ten": "VietnamBiz Tài chính", "url": "https://vietnambiz.vn/rss/tai-chinh.rss", "khu_vuc": "vn"},
    {"ten": "VietnamBiz Vĩ mô", "url": "https://vietnambiz.vn/rss/vi-mo.rss", "khu_vuc": "vn"},

    # ----- Báo Đầu tư (baodautu.vn) -----
    # GHI CHÚ: Ở thời điểm viết, KHÔNG tìm được RSS còn hoạt động của Báo Đầu tư
    # (mọi đường dẫn thử đều trống). Khi họ mở lại RSS, bỏ dấu # và thay URL đúng:
    # {"ten": "Báo Đầu tư", "url": "https://baodautu.vn/rss/tai-chinh-chung-khoan.rss", "khu_vuc": "vn"},
]


# ---------------------------------------------------------------------------
# 2. BỘ TỪ KHÓA NÓNG (TIẾNG VIỆT)
# ---------------------------------------------------------------------------
# Mỗi lần từ khóa xuất hiện sẽ được cộng điểm (xem phần chấm điểm).
TU_KHOA_NONG = [
    "vn-index", "vnindex", "ngân hàng nhà nước", "nhnn", "tỷ giá", "lãi suất",
    "fdi", "lạm phát", "chứng khoán", "cổ phiếu", "trái phiếu", "tín dụng",
    "fed", "trump", "trung quốc", "xuất khẩu", "nhập khẩu", "gdp", "vàng",
    "usd", "dầu", "bất động sản", "thuế quan", "opec", "chính phủ", "xuất siêu",
]

# Token ASCII đánh dấu tin Việt Nam (dùng cho bộ lọc tiếng Việt bên dưới).
VN_MARKERS = ["vn-index", "vnindex", "hose", "hnx", "upcom", "vn30", "fdi", "nhnn", "vnd"]


# ---------------------------------------------------------------------------
# 3. GÁN CHỦ ĐỀ & HỆ SỐ ƯU TIÊN
# ---------------------------------------------------------------------------
# Quy tắc gán chủ đề: duyệt theo thứ tự, khớp từ khóa nào trước thì gán chủ đề đó.
# (Chủ đề đặc thù đặt trước.)
CHU_DE_RULES = [
    ("Fed", ["fed", "fomc", "powell", "cục dự trữ liên bang", "lãi suất mỹ",
             "ngân hàng trung ương mỹ"]),
    ("Chính sách", ["chính phủ", "thủ tướng", "quốc hội", "nghị định", "nghị quyết",
                    "bộ tài chính", "ngân hàng nhà nước", "nhnn", "chính sách",
                    "thông tư", "đầu tư công", "giải ngân", "quy hoạch", "luật"]),
    ("Kinh tế VN", ["vn-index", "vnindex", "hose", "hnx", "upcom", "tỷ giá", "vnd",
                    "fdi", "xuất khẩu", "nhập khẩu", "chứng khoán", "cổ phiếu",
                    "tín dụng", "lãi suất", "việt nam", "bất động sản"]),
    ("Địa chính trị", ["chiến tranh", "xung đột", "trump", "opec", "cấm vận",
                       "biển đông", "đài loan", "iran", "israel", "ukraine",
                       "nga", "hạt nhân", "quân sự", "căng thẳng"]),
    ("Thế giới", ["mỹ", "trung quốc", "nhật", "hàn quốc", "eu", "châu âu",
                  "phố wall", "dow jones", "nasdaq", "s&p", "toàn cầu", "thế giới"]),
]

# Hệ số ưu tiên: nhân vào ĐIỂM GỐC để đẩy tin Việt Nam lên đầu.
HE_SO_UU_TIEN = {
    "Kinh tế VN": 2.0,
    "Chính sách": 1.7,
    "Fed": 1.3,
    "Thế giới": 1.2,
    "Địa chính trị": 1.0,
}

# Chủ đề nào được coi là "tin Việt Nam" (dùng cho hạn ngạch).
CHU_DE_VN = {"Kinh tế VN", "Chính sách"}


# ---------------------------------------------------------------------------
# 4. HÀM TIỆN ÍCH
# ---------------------------------------------------------------------------
GIO_VN = timezone(timedelta(hours=7))  # múi giờ Việt Nam (UTC+7)

# Tập ký tự tiếng Việt CÓ DẤU (dùng để nhận diện tiêu đề tiếng Việt).
KY_TU_TV = set(
    "àáảãạăắằẳẵặâấầẩẫậèéẻẽẹêếềểễệìíỉĩịòóỏõọôốồổỗộơớờởỡợ"
    "ùúủũụưứừửữựỳýỷỹỵđ"
)


def lam_sach_text(s: str) -> str:
    """Bỏ thẻ HTML, giải mã ký tự đặc biệt, gọn khoảng trắng."""
    if not s:
        return ""
    s = re.sub(r"<[^>]+>", " ", s)      # bỏ thẻ HTML
    s = html.unescape(s)                # &amp; -> &, &#201; -> É ...
    s = re.sub(r"\s+", " ", s).strip()  # gộp khoảng trắng
    return s


def chuan_hoa_de_so_sanh(tieu_de: str) -> str:
    """Chuẩn hóa tiêu đề để so trùng: chữ thường, bỏ ký tự lạ."""
    s = tieu_de.lower()
    s = re.sub(r"[^\w\s" + "".join(KY_TU_TV) + r"]", " ", s)
    s = re.sub(r"\s+", " ", s).strip()
    return s


def bo_token_ngay(tieu_de: str) -> str:
    """
    Bỏ các token chỉ NGÀY/THÁNG/THỜI ĐIỂM ra khỏi tiêu đề để so "phần chữ".
    Ví dụ: "Tỷ giá euro ngày 6/7: ..." -> "tỷ giá euro : ..."
    Xử lý: "ngày 6/7", "hôm nay 6/7", "sáng/chiều 6/7", "06/07/2026", "6-7"...
    """
    s = tieu_de.lower()
    # Bỏ ngày dạng số: 6/7, 06/07, 6/7/2026, 6-7 ...
    s = re.sub(r"\b\d{1,2}\s*[/-]\s*\d{1,2}(?:\s*[/-]\s*\d{2,4})?\b", " ", s)
    # Bỏ các từ chỉ mốc thời gian thường đi kèm ngày
    s = re.sub(r"\b(ngày|hôm nay|sáng nay|sáng|chiều nay|chiều|trưa|tối nay|tối|tuần này)\b", " ", s)
    # Chỉ giữ chữ + số + ký tự tiếng Việt, gộp khoảng trắng
    s = re.sub(r"[^\w\s" + "".join(KY_TU_TV) + r"]", " ", s)
    s = re.sub(r"\s+", " ", s).strip()
    return s


def la_tieng_viet(tieu_de: str) -> bool:
    """
    Trả về True nếu tiêu đề được coi là tiếng Việt:
      - chứa ít nhất 1 ký tự tiếng Việt có dấu, HOẶC
      - khớp một token đánh dấu tin VN (vn-index, hose, nhnn...).
    Dùng để loại tin lọt tiếng Anh khi feed lẫn ngôn ngữ.
    """
    t = tieu_de.lower()
    if any(ch in KY_TU_TV for ch in t):
        return True
    if any(marker in t for marker in VN_MARKERS):
        return True
    return False


def lay_thoi_gian(entry) -> datetime:
    """Lấy thời gian đăng của một entry RSS, trả về datetime có timezone (UTC)."""
    for field in ("published_parsed", "updated_parsed"):
        t = entry.get(field)
        if t:
            return datetime(*t[:6], tzinfo=timezone.utc)
    return datetime.now(timezone.utc)


def diem_moi(gio_dang: datetime, bay_gio: datetime) -> float:
    """Điểm 'mới': 0h tuổi -> ~10 điểm; 24h tuổi -> 0 điểm (giảm tuyến tính)."""
    tuoi_gio = (bay_gio - gio_dang).total_seconds() / 3600.0
    diem = 10.0 * (1 - tuoi_gio / 24.0)
    return round(max(0.0, diem), 1)


def gan_chu_de(tieu_de: str, khu_vuc: str) -> str:
    """
    Gán chủ đề dựa trên từ khóa trong tiêu đề.
    Nếu không khớp từ khóa nào -> dựa vào khu vực của nguồn:
      nguồn trong nước -> 'Kinh tế VN'; nguồn quốc tế -> 'Thế giới'.
    """
    t = tieu_de.lower()
    for chu_de, tu_khoas in CHU_DE_RULES:
        if any(tk in t for tk in tu_khoas):
            return chu_de
    return "Kinh tế VN" if khu_vuc == "vn" else "Thế giới"


# ---------------------------------------------------------------------------
# 5. LẤY TIN TỪ CÁC FEED
# ---------------------------------------------------------------------------
def lay_tat_ca_tin():
    """Duyệt mọi nguồn RSS, trả về danh sách tin thô (đã lọc 24h + tiếng Việt)."""
    bay_gio = datetime.now(timezone.utc)
    gioi_han = bay_gio - timedelta(hours=24)
    tin_tho = []
    bo_vi_tieng_anh = 0

    for nguon in RSS_SOURCES:
        print(f"-> Đang lấy: {nguon['ten']} ({nguon['url']})")
        try:
            feed = feedparser.parse(nguon["url"])
        except Exception as e:
            print(f"   !! Lỗi khi đọc feed: {e}")
            continue

        if not feed.entries:
            print("   (feed trống hoặc không đọc được - cân nhắc thay URL)")
            continue

        for entry in feed.entries:
            tieu_de = lam_sach_text(entry.get("title", ""))
            link = entry.get("link", "").strip()
            if not tieu_de or not link:
                continue

            # Loại tin không phải tiếng Việt
            if not la_tieng_viet(tieu_de):
                bo_vi_tieng_anh += 1
                continue

            gio_dang = lay_thoi_gian(entry)
            if gio_dang < gioi_han:   # chỉ giữ tin trong 24h
                continue

            tin_tho.append({
                "tieu_de": tieu_de,
                "nguon": nguon["ten"],
                "khu_vuc": nguon["khu_vuc"],
                "link": link,
                "gio_dang": gio_dang,
            })

    print(f"=> Tổng tin thô trong 24h (tiếng Việt): {len(tin_tho)} "
          f"(đã loại {bo_vi_tieng_anh} tin không phải tiếng Việt)")
    return tin_tho


# ---------------------------------------------------------------------------
# 6. GỘP TIN TRÙNG
# ---------------------------------------------------------------------------
def gop_tin_trung(tin_tho, nguong=0.72):
    """
    Gộp các tin nói về cùng sự kiện thành 1 mục (dựa trên độ giống tiêu đề).
    Nhóm giữ tin mới nhất làm đại diện và ghi lại tập hợp nguồn đã đăng.
    """
    nhom_list = []

    for tin in tin_tho:
        chuan = chuan_hoa_de_so_sanh(tin["tieu_de"])
        da_gop = False

        for nhom in nhom_list:
            do_giong = SequenceMatcher(None, chuan, nhom["_chuan"]).ratio()
            if do_giong >= nguong:
                nhom["nguon_set"].add(tin["nguon"])
                if tin["gio_dang"] > nhom["gio_dang"]:
                    nhom["tieu_de"] = tin["tieu_de"]
                    nhom["gio_dang"] = tin["gio_dang"]
                    nhom["link"] = tin["link"]
                    nhom["khu_vuc"] = tin["khu_vuc"]
                    nhom["_chuan"] = chuan
                da_gop = True
                break

        if not da_gop:
            nhom_list.append({
                "tieu_de": tin["tieu_de"],
                "link": tin["link"],
                "gio_dang": tin["gio_dang"],
                "khu_vuc": tin["khu_vuc"],
                "nguon_set": {tin["nguon"]},
                "_chuan": chuan,
            })

    print(f"=> Sau khi gộp còn: {len(nhom_list)} nhóm tin")
    return nhom_list


# ---------------------------------------------------------------------------
# 6b. GỘP LOẠT BÀI ĐỊNH KỲ (bỏ token ngày rồi so phần chữ còn lại)
# ---------------------------------------------------------------------------
def gop_bai_dinh_ky(nhom_list, nguong=0.85):
    """
    Gộp các bài ĐĂNG ĐỊNH KỲ chỉ khác nhau ở ngày/tháng
    (vd "Tỷ giá euro ngày 2/7", "ngày 3/7"...).
    Cách làm: bỏ token ngày -> so phần chữ còn lại; nếu giống >= `nguong`
    (mặc định 85%) thì coi là cùng một loạt và CHỈ GIỮ BẢN MỚI NHẤT.
    Ngưỡng cao (85%) để KHÔNG gộp nhầm tin khác nội dung.
    In log các bài bị gộp để kiểm tra.
    """
    ket_qua = []
    bi_gop = []  # danh sách (tiêu_đề_bị_bỏ, tiêu_đề_được_giữ) để log

    for nhom in nhom_list:
        khoa = bo_token_ngay(nhom["tieu_de"])
        trung = None

        for g in ket_qua:
            if SequenceMatcher(None, khoa, g["_khoa_ngay"]).ratio() >= nguong:
                trung = g
                break

        if trung is not None:
            # Cùng một loạt -> gộp nguồn, giữ bản MỚI NHẤT
            trung["nguon_set"] |= nhom["nguon_set"]
            if nhom["gio_dang"] > trung["gio_dang"]:
                # nhom mới hơn -> thay bản đại diện, bản cũ bị bỏ
                bi_gop.append((trung["tieu_de"], nhom["tieu_de"]))
                trung["tieu_de"] = nhom["tieu_de"]
                trung["gio_dang"] = nhom["gio_dang"]
                trung["link"] = nhom["link"]
                trung["khu_vuc"] = nhom["khu_vuc"]
                trung["_khoa_ngay"] = khoa
            else:
                # bản đang xét cũ hơn -> bỏ nó, giữ bản đã có
                bi_gop.append((nhom["tieu_de"], trung["tieu_de"]))
        else:
            n = dict(nhom)
            n["_khoa_ngay"] = khoa
            ket_qua.append(n)

    # ----- Log các bài bị gộp -----
    if bi_gop:
        print(f"=> Gộp loạt bài định kỳ: bỏ {len(bi_gop)} bản cũ, giữ bản mới nhất:")
        for bo, giu in bi_gop:
            print(f"   - BỎ : {bo}")
            print(f"     GIỮ: {giu}")
    else:
        print("=> Gộp loạt bài định kỳ: không có bài nào bị gộp.")

    print(f"=> Sau khi gộp loạt định kỳ còn: {len(ket_qua)} nhóm tin")
    return ket_qua


# ---------------------------------------------------------------------------
# 7. CHẤM ĐIỂM HOT (CODE THUẦN) + HỆ SỐ ƯU TIÊN
# ---------------------------------------------------------------------------
def cham_diem(nhom_list):
    """
    điểm_gốc = (số nguồn đăng trùng) * 3
             + (số lần lặp từ khóa nóng trong ngày)
             + (điểm mới)
    điểm     = điểm_gốc * HỆ SỐ ƯU TIÊN theo chủ đề
    """
    bay_gio = datetime.now(timezone.utc)

    # Đếm tần suất mỗi từ khóa nóng trên TOÀN BỘ tin trong ngày.
    tan_suat_tu_khoa = {tu: 0 for tu in TU_KHOA_NONG}
    for nhom in nhom_list:
        t = nhom["tieu_de"].lower()
        for tu in TU_KHOA_NONG:
            tan_suat_tu_khoa[tu] += t.count(tu)

    ket_qua = []
    for nhom in nhom_list:
        so_nguon = len(nhom["nguon_set"])
        t = nhom["tieu_de"].lower()

        diem_tu_khoa = sum(tan_suat_tu_khoa[tu] for tu in TU_KHOA_NONG if tu in t)
        diem_mo = diem_moi(nhom["gio_dang"], bay_gio)

        diem_goc = so_nguon * 3 + diem_tu_khoa + diem_mo

        chu_de = gan_chu_de(nhom["tieu_de"], nhom["khu_vuc"])
        he_so = HE_SO_UU_TIEN.get(chu_de, 1.0)
        tong_diem = round(diem_goc * he_so, 1)

        gio_vn = nhom["gio_dang"].astimezone(GIO_VN)
        ket_qua.append({
            "tieu_de": nhom["tieu_de"],
            "chu_de": chu_de,
            "nguon": ", ".join(sorted(nhom["nguon_set"])),
            "so_nguon": so_nguon,
            "thoi_gian": gio_vn.strftime("%Y-%m-%d %H:%M"),
            "link": nhom["link"],
            "diem": tong_diem,
            "_la_vn": chu_de in CHU_DE_VN,   # cờ nội bộ cho hạn ngạch
        })

    return ket_qua


# ---------------------------------------------------------------------------
# 8. CHỌN 30 TIN THEO HẠN NGẠCH (tin quốc tế không tràn top)
# ---------------------------------------------------------------------------
def chon_tin_uu_tien(danh_sach, tong=30):
    """
    Chọn tối đa `tong` tin, sắp theo điểm giảm dần, nhưng áp hạn ngạch:
      - Tối đa 10 tin KHÔNG-phải-VN nằm trong 15 vị trí CUỐI (16..30).
      - Ưu tiên đủ ít nhất 6 tin chủ đề Việt Nam (Kinh tế VN / Chính sách)
        nếu nguồn có đủ.
    """
    # Tách 2 nhóm, mỗi nhóm sắp theo điểm giảm dần.
    vn = sorted([t for t in danh_sach if t["_la_vn"]], key=lambda x: x["diem"], reverse=True)
    intl = sorted([t for t in danh_sach if not t["_la_vn"]], key=lambda x: x["diem"], reverse=True)

    final = []
    i_vn = i_intl = 0
    intl_o_duoi = 0   # số tin quốc tế đã nằm trong vùng 15 vị trí cuối

    while len(final) < tong and (i_vn < len(vn) or i_intl < len(intl)):
        trong_vung_cuoi = len(final) >= (tong - 15)  # vị trí 16..30

        con_vn = i_vn < len(vn)
        con_intl = i_intl < len(intl)

        # Mặc định: lấy tin có điểm cao hơn giữa 2 nhóm.
        if con_vn and con_intl:
            lay_vn = vn[i_vn]["diem"] >= intl[i_intl]["diem"]
        else:
            lay_vn = con_vn  # hết nhóm nào thì lấy nhóm còn lại

        # Áp hạn ngạch: ở vùng cuối, nếu đã đủ 10 tin quốc tế thì buộc lấy VN.
        if trong_vung_cuoi and not lay_vn and intl_o_duoi >= 10 and con_vn:
            lay_vn = True

        if lay_vn:
            final.append(vn[i_vn]); i_vn += 1
        else:
            final.append(intl[i_intl]); i_intl += 1
            if trong_vung_cuoi:
                intl_o_duoi += 1

    # Đảm bảo tối thiểu 6 tin Việt Nam (nếu còn tin VN chưa dùng).
    so_vn = sum(1 for t in final if t["_la_vn"])
    while so_vn < 6 and i_vn < len(vn):
        # Thay tin quốc tế điểm thấp nhất trong final bằng tin VN kế tiếp.
        for j in range(len(final) - 1, -1, -1):
            if not final[j]["_la_vn"]:
                final[j] = vn[i_vn]
                i_vn += 1
                so_vn += 1
                break
        else:
            break  # không còn tin quốc tế để thay

    # Sắp lại toàn bộ theo điểm giảm dần cho gọn.
    final.sort(key=lambda x: x["diem"], reverse=True)
    return final


# ---------------------------------------------------------------------------
# 9. HÀM CHÍNH
# ---------------------------------------------------------------------------
def main():
    tin_tho = lay_tat_ca_tin()
    nhom_list = gop_tin_trung(tin_tho)
    nhom_list = gop_bai_dinh_ky(nhom_list)   # gộp loạt bài chỉ khác ngày/tháng
    danh_sach = cham_diem(nhom_list)
    danh_sach = chon_tin_uu_tien(danh_sach, tong=30)

    # Bỏ cờ nội bộ trước khi xuất file.
    for t in danh_sach:
        t.pop("_la_vn", None)

    output = {
        "cap_nhat_luc": datetime.now(GIO_VN).strftime("%Y-%m-%d %H:%M:%S"),
        "so_tin": len(danh_sach),
        "tin": danh_sach,
    }

    with open("data.json", "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)

    so_vn = sum(1 for t in danh_sach if t["chu_de"] in CHU_DE_VN)
    print(f"=> Đã ghi data.json với {len(danh_sach)} tin "
          f"(trong đó {so_vn} tin chủ đề Việt Nam).")


if __name__ == "__main__":
    main()
