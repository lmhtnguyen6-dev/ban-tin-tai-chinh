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
from datetime import datetime, timezone, timedelta, date
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
# 2. BỘ TỪ KHÓA NÓNG CÓ TRỌNG SỐ (TIẾNG VIỆT)
# ---------------------------------------------------------------------------
# Mỗi từ khóa có một TRỌNG SỐ: từ khóa càng quan trọng với thị trường chứng khoán
# thì điểm cộng càng lớn. (Trước đây mọi từ khóa cộng như nhau nên tin giá vàng,
# tỷ giá... dễ áp đảo. Nay ƯU TIÊN tin CHỨNG KHOÁN - TÀI CHÍNH - DOANH NGHIỆP.)
# Muốn tăng/giảm mức ưu tiên của một chủ điểm, chỉ cần sửa con số ở đây.
TRONG_SO_TU_KHOA = {
    # --- Chứng khoán & thị trường (ưu tiên cao nhất) ---
    "vn-index": 6, "vnindex": 6, "vn30": 5, "chứng khoán": 5, "cổ phiếu": 5,
    "hose": 4, "hnx": 3, "upcom": 3, "niêm yết": 4,
    "trái phiếu": 3, "khối ngoại": 5, "thanh khoản": 3,
    # --- NHNN: nghiệp vụ điều hành tiền tệ (tầng 1.3 trong bộ khung tham khảo
    #     — đây là các CÔNG CỤ điều hành cụ thể, tin về chúng thường báo hiệu
    #     sớm hướng đi thanh khoản/lãi suất trước khi có quyết định chính thức) ---
    "room tín dụng": 4, "lãi suất điều hành": 4, "tín phiếu": 3, "omo": 3,
    "reverse repo": 3, "dự trữ ngoại hối": 3,
    # --- UBCK: cấu trúc & quy định giao dịch (tầng 1.4) ---
    "krx": 4, "t+0": 4, "bán khống": 3, "margin": 3, "ftse": 3, "msci": 3,
    # --- Hoạt động doanh nghiệp trên sàn (ƯU TIÊN TĂNG: cổ tức, phát hành, M&A,
    #     ĐHĐCĐ, giao dịch cổ đông... = tin CK thực chất, cần đẩy lên top) ---
    "cổ tức": 4, "trả cổ tức": 4, "chia cổ tức": 4,
    "phát hành cổ phiếu": 5, "chào bán cổ phiếu": 5, "phát hành riêng lẻ": 4,
    "cổ phiếu quỹ": 4, "mua lại cổ phiếu": 4,
    "đhđcđ": 4, "đại hội cổ đông": 4, "cổ đông lớn": 4, "thoái vốn": 4,
    # --- Doanh nghiệp niêm yết ---
    "lợi nhuận": 4, "doanh thu": 2, "báo cáo tài chính": 3, "kết quả kinh doanh": 4,
    "thâu tóm": 4, "sáp nhập": 4, "m&a": 4, "ipo": 4, "vốn hóa": 3,
    # --- Chính sách / chủ trương / quyết định của Chính phủ (ƯU TIÊN CAO NHẤT
    #     theo yêu cầu chủ dự án — đứng trên cả lãi suất/lạm phát/hàng hóa) ---
    "đề án": 4, "phê duyệt": 3, "cải cách": 4, "cải cách tổng thể": 6,
    "nghị quyết": 3, "nghị định": 3, "chiến lược phát triển": 3,
    # --- Giao dịch cổ đông nội bộ / lãnh đạo mua bán cổ phiếu (tín hiệu quan
    #     trọng với NĐT cá nhân, dễ bị bỏ sót nếu không có từ khóa riêng) ---
    "đăng ký mua": 5, "đăng ký bán": 3, "cổ đông nội bộ": 5, "người nội bộ": 4,
    # --- Tài chính - ngân hàng - chính sách tiền tệ ---
    "ngân hàng nhà nước": 4, "nhnn": 4, "lãi suất": 4, "lãi suất liên ngân hàng": 5,
    "tín dụng": 3, "tỷ giá": 2, "lạm phát": 4,
    # --- Fed & quốc tế tác động mạnh (thêm vài số liệu Mỹ cụ thể hay dẫn tới
    #     biến động thị trường ngay khi công bố) ---
    "fed": 5, "fomc": 5, "powell": 4, "lãi suất mỹ": 5, "thuế quan": 3,
    "non farm payroll": 3, "bảng lương phi nông nghiệp": 3, "cpi mỹ": 3,
    "dot plot": 3, "pboc": 2,
    # --- Vĩ mô Việt Nam ---
    "fdi": 3, "gdp": 3, "tăng trưởng": 2, "xuất khẩu": 2, "nhập khẩu": 2,
    "đầu tư công": 3, "giải ngân": 2,
    # --- Hàng hóa (dầu, vàng...): nâng nhẹ so với trước vì chủ dự án xếp nhóm
    #     này vào ưu tiên cao (sau chính sách/lãi suất/lạm phát) ---
    "dầu": 2, "opec": 2, "vàng": 2, "usd": 1, "bất động sản": 2,
    "trung quốc": 1, "trump": 2,
    # Hàng hóa mở rộng (tầng 4) — dùng cụm "giá X" thay vì từ trơn để tránh
    # nhầm với nghĩa đời thường (vd "cà phê" quán xá, "gạo" bữa ăn...).
    "giá thép": 2, "quặng sắt": 2, "giá cà phê": 1, "giá cao su": 1,
    "giá gạo": 1, "giá bạc": 1,
    # --- Dòng vốn / trái phiếu quốc tế (tầng 7-8) ---
    "etf": 3, "dragon capital": 2, "vinacapital": 2, "pyn elite": 2,
    "lợi suất trái phiếu": 2, "trái phiếu chính phủ": 2,
    "phát hành trái phiếu doanh nghiệp": 3,
    # --- Doanh nghiệp lớn / vốn hóa lớn (tầng 9) — tin riêng về các mã này vẫn
    #     là tin thị trường thực chất dù không dùng từ "cổ phiếu"/"chứng khoán" ---
    "vingroup": 2, "hòa phát": 2, "masan": 2, "pv gas": 2, "petrolimex": 2,
    "vietcombank": 2, "bidv": 2, "vietinbank": 2, "techcombank": 2,
    "vpbank": 2, "mbbank": 2, "acb": 2, "sacombank": 2, "hdbank": 2, "tpbank": 2,
    # --- Tin ngành (tầng 10): mỗi ngành vài từ khóa đặc trưng hay tạo sóng ---
    "nợ xấu": 3, "basel": 2,                          # ngân hàng
    "tự doanh": 2,                                    # công ty chứng khoán
    "luật đất đai": 3,                                # bất động sản
    "evn": 3, "giá điện": 3,                          # điện
    "giá urê": 2, "than cốc": 1,                      # phân bón / thép
    # GHI CHÚ: "vàng" ở đây CHỈ cộng điểm cho tin vàng mang tính vĩ mô/sự kiện
    # (vd "NHTW tăng mua vàng dự trữ") vì tin CẬP NHẬT GIÁ VÀNG HẰNG NGÀY đã bị
    # loại ở bước lọc nhiễu (xem CUM_GIA_VANG_HANG_NGAY) trước khi tới bước này.
    # GHI CHÚ 2: KHÔNG thêm các số liệu cần nguồn dữ liệu thị trường riêng
    # (US10Y/US2Y, DXY số cụ thể, CDS Việt Nam...) vì RSS báo chí không phải
    # nguồn số liệu gốc cho các chỉ số này — chỉ có bài DIỄN GIẢI về chúng, và
    # các bài đó đã được bắt qua "lợi suất trái phiếu"/"fed"/"trung quốc" ở trên.
}

# Token ASCII đánh dấu tin Việt Nam (dùng cho bộ lọc tiếng Việt bên dưới).
VN_MARKERS = ["vn-index", "vnindex", "hose", "hnx", "upcom", "vn30", "fdi", "nhnn", "vnd"]


# ---------------------------------------------------------------------------
# 2b. LỌC TIN "NHIỄU" (không ảnh hưởng thị trường -> loại khỏi bảng)
# ---------------------------------------------------------------------------
# Mỗi nhóm là danh sách cụm từ; tiêu đề chứa BẤT KỲ cụm nào -> tin bị loại (có log).
# Bật/tắt từng nhóm bằng cách thêm/bớt tên nhóm trong LOC_NHOM_NHIEU bên dưới.
NHOM_TIN_NHIEU = {
    # Quảng cáo / khuyến mãi sản phẩm ngân hàng (vd "VIB Up: đăng ký một lần...").
    "quang_cao": [
        "trọn đời", "đăng ký một lần", "hoàn tiền", "mở thẻ", "trả góp",
        "quà tặng", "tri ân", "cashback", "khuyến mãi", "ưu đãi lãi suất",
        "ra mắt gói", "hoàn phí", "tặng ngay", "voucher", "quay số trúng thưởng",
    ],
    # Vụ án / hình sự / pháp luật (vd "người phụ nữ bị truy tìm vì nghi chiếm đoạt").
    # LƯU Ý: "cáo buộc" và "gian lận" KHÔNG để ở đây vì chúng HAI NGHĨA — xử lý theo
    # ngữ cảnh trong la_tu_hai_nghia_hinh_su. Có tội phạm-gian lận ngành NH đã có nghĩa
    # rõ (rửa tiền, lỗ hổng tài khoản) — KHÁC tin CHÍNH SÁCH/quy định (room tín dụng,
    # chế tài...) vẫn được giữ ở chủ đề Chính sách.
    "hinh_su": [
        "truy tìm", "truy nã", "bị bắt", "khởi tố", "lừa đảo", "chiếm đoạt",
        "lãnh án", "tuyên án", "bắt giam", "hầu tòa", "cáo trạng", "vòng lao lý",
        "trốn nã", "trộm", "cướp", "đánh bạc", "rửa tiền", "lỗ hổng tài khoản",
    ],
    # Mẹo chi tiêu / tài chính cá nhân / đời sống (không tác động thị trường).
    "doi_song": [
        "nghiện mua", "nên chi tiêu", "chi tiêu thế nào", "chi tiêu ra sao",
        "quản lý chi tiêu", "quản lý tài chính cá nhân", "chi tiền vào đâu",
    ],
    # Lễ hội / đặc sản / sự kiện (vd "Saigon Co.op ... tại Lễ hội Việt").
    "le_hoi": [
        "lễ hội", "đặc sản", "hoa hậu", "giải chạy", "cuộc thi", "khai mạc lễ",
        "ẩm thực", "du lịch hè", "check-in", "sống ảo",
    ],
    # Hạ tầng giao thông hằng ngày (vd "Tạm dừng khai thác cao tốc ... ban đêm").
    "giao_thong": [
        "tạm dừng khai thác", "phân luồng", "cấm xe", "cấm đường", "kẹt xe",
        "ùn tắc", "tai nạn giao thông", "khai thác cao tốc", "phạt nguội",
    ],
    # PR doanh nghiệp: vinh danh/giải thưởng/xếp hạng, ký kết hợp tác/MOU, ra mắt sản
    # phẩm-hệ thống, tài trợ. Có tên NH niêm yết nhưng KHÔNG phải hoạt động thị trường.
    # (Dùng cụm cụ thể như "ký kết"/"hợp tác chiến lược" thay vì "hợp tác" trơn, và
    #  "bảng xếp hạng" thay vì "xếp hạng" trơn — tránh dính "xếp hạng tín nhiệm".)
    "pr_doanh_nghiep": [
        "vinh danh", "giải thưởng", "awards", "bảng xếp hạng", "fortune",
        "được trao giải", "đạt giải", "top 500",
        "ký kết", "ký hợp tác", "hợp tác chiến lược", "biên bản ghi nhớ", "mou",
        "đồng hành", "tài trợ", "ra mắt", "core banking", "open banking",
        # Quảng cáo sản phẩm ngân hàng số / bài PR "câu chuyện thương hiệu"
        "1 chạm", "một chạm", "chuyển đổi toàn diện", "giai đoạn tăng trưởng mới",
        "hành trình chuyển đổi", "thấu hiểu", "hiểu đúng nhịp sống",
    ],
    # Dự báo/nhận định vĩ mô CHUNG CHUNG (tổ chức quốc tế nâng/hạ dự báo GDP,
    # kịch bản tăng trưởng địa phương, bình luận trấn an kiểu "không ảnh hưởng
    # lớn"...). KHÁC với tin CHÍNH SÁCH đã ban hành (nghị quyết, đề án, phê
    # duyệt...) — những tin đó vẫn được GIỮ và tính điểm cao ở nhóm Chính sách.
    "du_bao_vi_mo": [
        "dự báo tăng trưởng gdp", "nâng dự báo tăng trưởng", "hạ dự báo tăng trưởng",
        "tổ chức quốc tế dự báo", "kịch bản tăng trưởng",
        "không ảnh hưởng lớn", "không ảnh hưởng đáng kể", "tác động không đáng kể",
    ],
    # Số liệu vụn vặt của một ngân hàng/doanh nghiệp riêng lẻ, ít tác động toàn
    # thị trường (so sánh thu nhập nhân viên, tỷ lệ cho vay một mảng của 1 NH,
    # kiều hối định kỳ...). KHÔNG lọc "cổ đông lớn"/"đăng ký mua" vì đó là tín
    # hiệu giao dịch cổ phiếu quan trọng, khác hẳn nhóm này.
    "so_lieu_le_te": [
        "kiều hối", "trả thu nhập", "thu nhập khủng", "độ chịu chi",
        "tỷ lệ cho vay bất động sản",
    ],
    # Nhân sự lãnh đạo thường lệ (bổ nhiệm/tái bổ nhiệm/miễn nhiệm). KHÔNG dùng "bầu"
    # để không loại nhầm tin ĐHĐCĐ (vd "họp ĐHĐCĐ bất thường, bầu bổ sung nhân sự").
    "nhan_su": [
        "bổ nhiệm", "miễn nhiệm", "từ nhiệm",
    ],
    # Bình luận vĩ mô địa phương chung chung (tăng trưởng 2 con số của tỉnh/thành...).
    # Heuristic theo cụm đặc trưng — có thể cần tinh chỉnh nếu sót/nhầm.
    "vi_mo_dia_phuong": [
        "tăng trưởng kinh tế 2 con số", "tăng trưởng 2 con số",
        "thuế thời gian", "ốc đảo ưu đãi",
    ],
}

# Các nhóm ĐANG BẬT (theo lựa chọn của chủ dự án). Bỏ bớt tên trong list này để tắt.
LOC_NHOM_NHIEU = ["quang_cao", "hinh_su", "le_hoi", "giao_thong", "doi_song",
                  "pr_doanh_nghiep", "nhan_su", "vi_mo_dia_phuong",
                  "du_bao_vi_mo", "so_lieu_le_te"]

# Tin CẬP NHẬT GIÁ VÀNG hằng ngày (giá vàng sáng/chiều, vàng miếng/nhẫn/SJC) -> loại.
# Vẫn GIỮ tin vàng vĩ mô (vd "ngân hàng trung ương tăng tích trữ vàng") vì tiêu đề
# dạng đó KHÔNG khớp các cụm dưới đây.
CUM_GIA_VANG_HANG_NGAY = ["giá vàng", "vàng miếng", "vàng nhẫn", "vàng sjc"]

# Tin CẬP NHẬT TỶ GIÁ USD/EUR... hằng ngày (vd "Tỷ giá USD hôm nay 27/7: ...",
# "Tỷ giá euro ngày 28/7: ...", "Đồng USD có tuần bứt phá..."). Đây là bài đăng
# ĐỊNH KỲ, không phải sự kiện chính sách/thị trường thực sự -> loại. Dùng regex
# vì cách viết đa dạng hơn giá vàng (nhiều đồng tiền, "hôm nay"/"ngày x/y"/"tuần").
# VẪN GIỮ các mốc tỷ giá mang tính SỰ KIỆN (vd "Tỷ giá trung tâm lập kỷ lục") vì
# không khớp các mẫu dưới đây.
MAU_TY_GIA_HANG_NGAY = [
    re.compile(r"tỷ giá (usd|đô la|đôla|euro|yên|nhân dân tệ|bảng anh)"
               r".{0,20}(hôm nay|ngày\s*\d{1,2}[/-]\d{1,2})"),
    re.compile(r"(giá|đồng) (usd|euro)\b.{0,25}(hôm nay|ngày\s*\d{1,2}[/-]\d{1,2}"
               r"|có tuần|tuần này|tuần qua)"),
    # Tiêu đề ngắn kiểu "Giá USD tăng vọt" / "Đồng euro lao dốc" không kèm bối
    # cảnh chính sách/sự kiện gì khác -> vẫn là bản tin giá spot hằng ngày.
    re.compile(r"^(giá|đồng)\s+(usd|euro)\b.{0,25}"
               r"(tăng|giảm|vọt|lao dốc|bứt phá|trượt giá|đi lên|đi xuống)"),
]


def la_tin_ty_gia_hang_ngay(t: str) -> bool:
    """True nếu tiêu đề khớp mẫu bản tin tỷ giá USD/EUR... cập nhật định kỳ."""
    return any(mau.search(t) for mau in MAU_TY_GIA_HANG_NGAY)

# Các từ HAI NGHĨA: vừa có thể là tin hình sự ("bị cáo buộc lừa đảo, đã khởi tố"),
# vừa có thể là tin doanh nghiệp/thị trường ("công ty X bị cáo buộc gian lận sổ sách",
# "nghi thao túng") — loại tin sau CÓ THỂ ảnh hưởng giá cổ phiếu nên PHẢI GIỮ. Vì vậy
# chỉ coi các từ này là nhiễu khi chúng ĐI KÈM ngữ cảnh hình sự rõ ràng dưới đây.
TU_HAI_NGHIA = ["cáo buộc", "gian lận"]

# (Dùng "tòa án"/"hầu tòa" thay vì "tòa" trơn để khỏi dính "tòa nhà", "tòa soạn".)
# LƯU Ý: KHÔNG đưa "bị cáo" vào đây — nó là substring của chính "bị CÁO buộc" nên sẽ
# khớp mọi tiêu đề "bị cáo buộc", vô hiệu hóa bộ lọc ngữ cảnh. Dùng "bị can" là đủ.
NGU_CANH_HINH_SU = [
    "bị bắt", "khởi tố", "truy tố", "công an", "tòa án", "hầu tòa", "lừa đảo",
    "chiếm đoạt", "bắt giam", "truy nã", "truy tìm", "cáo trạng", "bị can", "rửa tiền",
]


def la_tu_hai_nghia_hinh_su(t: str) -> bool:
    """True nếu tiêu đề chứa từ HAI NGHĨA ('cáo buộc'/'gian lận') ĐI KÈM ngữ cảnh hình
    sự -> coi là nhiễu. Nếu đứng một mình hoặc gắn ngữ cảnh doanh nghiệp/thị trường
    (cáo buộc/nghi gian lận sổ sách, thao túng...) -> GIỮ lại vì có thể ảnh hưởng CP."""
    return (any(tu in t for tu in TU_HAI_NGHIA)
            and any(cum in t for cum in NGU_CANH_HINH_SU))


def la_tin_nhieu(tieu_de: str):
    """
    Trả về (True, tên_nhóm) nếu tiêu đề là tin 'nhiễu' cần loại, ngược lại (False, "").
      - Là tin cập nhật giá vàng hằng ngày, HOẶC
      - Từ hai nghĩa ("cáo buộc"/"gian lận") đi kèm ngữ cảnh hình sự
        (xem la_tu_hai_nghia_hinh_su), HOẶC
      - Khớp cụm từ trong các nhóm ĐANG BẬT (LOC_NHOM_NHIEU).
    """
    t = tieu_de.lower()
    if any(cum in t for cum in CUM_GIA_VANG_HANG_NGAY):
        return True, "gia_vang_hang_ngay"
    if la_tin_ty_gia_hang_ngay(t):
        return True, "ty_gia_hang_ngay"
    if "hinh_su" in LOC_NHOM_NHIEU and la_tu_hai_nghia_hinh_su(t):
        return True, "hinh_su"
    for ten_nhom in LOC_NHOM_NHIEU:
        for cum in NHOM_TIN_NHIEU.get(ten_nhom, []):
            if cum in t:
                return True, ten_nhom
    return False, ""


# ---------------------------------------------------------------------------
# 2c. TIN KHẨN CẤP (Breaking News) — sự kiện đủ lớn để vượt lên TRÊN mọi luật
#     xếp hạng thông thường, bất kể chủ đề/số nguồn/độ mới.
# ---------------------------------------------------------------------------
# Đây là các cụm từ ĐẶC HIỆU cho sự kiện QUY MÔ LỚN thực sự (vỡ nợ, khủng hoảng
# ngân hàng, chiến tranh bùng nổ, sự cố hệ thống giao dịch...), KHÁC với tin
# thời sự thông thường dù cùng chủ đề (vd "lãi suất tăng" là tin thường, nhưng
# "khủng hoảng ngân hàng" là tin khẩn cấp). Dùng cụm nhiều từ để tránh khớp nhầm.
TU_KHOA_TIN_KHAN_CAP = [
    # Vỡ nợ / khủng hoảng tài chính - ngân hàng
    "vỡ nợ", "khủng hoảng ngân hàng", "khủng hoảng tài chính", "sụp đổ ngân hàng",
    "khủng hoảng thanh khoản", "vỡ bong bóng",
    # Chiến tranh / xung đột quân sự leo thang (có kênh truyền dẫn rõ tới giá dầu/
    # tâm lý rủi ro toàn cầu). ĐÃ BỎ "đảo chính"/"chính biến" vì quá chung chung —
    # chính biến ở một nước không liên quan kinh tế VN vẫn khớp, gây tin "linh tinh".
    "tuyên chiến", "chiến tranh bùng nổ", "tấn công quân sự", "không kích",
    # Dịch bệnh nghiêm trọng (có tiền lệ tác động mạnh tới KT-XH và TTCK VN, khác
    # với thiên tai đơn lẻ ở nước ngoài — xem ghi chú bên dưới).
    "đại dịch", "phong tỏa toàn quốc",
    # Xếp hạng tín nhiệm quốc gia
    "hạ xếp hạng tín nhiệm", "hạ bậc tín nhiệm",
    # Sự cố hệ thống giao dịch chứng khoán
    "sập sàn", "lỗi hệ thống giao dịch", "tạm dừng giao dịch toàn thị trường",
    "ngừng giao dịch toàn thị trường",
    # Trừng phạt / cấm vận diện rộng
    "cấm vận toàn diện", "trừng phạt kinh tế",
    # GHI CHÚ: ĐÃ BỎ "sóng thần"/"động đất mạnh" — thiên tai ở nước ngoài (vd Nhật)
    # KHÔNG có kênh truyền dẫn rõ ràng tới TTCK Việt Nam/kinh tế trong nước, nên dù
    # là tin lớn vẫn không nên chiếm vị trí "khẩn cấp" trên trang.
]


def la_tin_khan_cap(tieu_de: str) -> bool:
    """True nếu tiêu đề khớp một cụm từ 'khẩn cấp' (sự kiện đủ lớn)."""
    t = tieu_de.lower()
    return any(cum in t for cum in TU_KHOA_TIN_KHAN_CAP)


# Điểm THƯỞNG THÊM (cộng thẳng vào điểm cuối, sau hệ số ưu tiên chủ đề) cho tin
# khẩn cấp, để đảm bảo LUÔN đứng đầu bảng bất kể chủ đề gì / bao nhiêu nguồn đăng.
DIEM_THUONG_KHAN_CAP = 50


# ---------------------------------------------------------------------------
# 3. GÁN CHỦ ĐỀ & HỆ SỐ ƯU TIÊN
# ---------------------------------------------------------------------------
# Quy tắc gán chủ đề: duyệt theo thứ tự, khớp từ khóa nào trước thì gán chủ đề đó.
# (Chủ đề đặc thù đặt trước.)
CHU_DE_RULES = [
    ("Fed", ["fed", "fomc", "powell", "cục dự trữ liên bang", "lãi suất mỹ",
             "ngân hàng trung ương mỹ", "chủ tịch fed", "biên bản fomc",
             "non farm payroll", "bảng lương phi nông nghiệp", "cpi mỹ", "dot plot"]),
    ("Chính sách", ["chính phủ", "thủ tướng", "quốc hội", "nghị định", "nghị quyết",
                    "bộ tài chính", "ngân hàng nhà nước", "nhnn", "chính sách",
                    "thông tư", "đầu tư công", "giải ngân", "quy hoạch", "luật",
                    "đề án", "phê duyệt", "cải cách"]),
    ("Kinh tế VN", ["vn-index", "vnindex", "vn30", "hose", "hnx", "upcom",
                    "chứng khoán", "cổ phiếu", "niêm yết", "cổ tức", "trái phiếu",
                    "khối ngoại", "thanh khoản", "lợi nhuận", "doanh thu",
                    "kết quả kinh doanh", "ipo", "vốn hóa", "tỷ giá", "vnd",
                    "fdi", "tín dụng", "lãi suất", "xuất khẩu", "nhập khẩu",
                    "bất động sản",
                    # NHNN nghiệp vụ điều hành + UBCK cấu trúc thị trường + dòng
                    # vốn/trái phiếu quốc tế — đều là tin thị trường VN cụ thể.
                    "room tín dụng", "omo", "tín phiếu", "dự trữ ngoại hối",
                    "krx", "t+0", "bán khống", "margin", "ftse", "msci",
                    "etf", "lợi suất trái phiếu"]),
    ("Địa chính trị", ["chiến tranh", "xung đột", "trump", "opec", "cấm vận",
                       "biển đông", "đài loan", "iran", "israel", "ukraine",
                       "nga", "hạt nhân", "quân sự", "căng thẳng"]),
    ("Thế giới", ["mỹ", "trung quốc", "nhật", "hàn quốc", "eu", "châu âu",
                  "phố wall", "dow jones", "nasdaq", "s&p", "toàn cầu", "thế giới",
                  "pboc"]),
]

# Hệ số ưu tiên: nhân vào ĐIỂM GỐC để đẩy tin Việt Nam & Fed lên đầu.
HE_SO_UU_TIEN = {
    "Kinh tế VN": 2.0,
    "Chính sách": 2.0,  # nâng 1.7 -> 2.0: chủ dự án xếp chính sách/chủ trương/
                        # quyết định của Chính phủ là ưu tiên CAO NHẤT
    "Fed": 1.7,        # nâng 1.3 -> 1.7: tập trung hơn vào động thái/chính sách Fed
    "Thế giới": 1.1,   # hạ nhẹ 1.2 -> 1.1: tin thế giới lặt vặt không chen top
    "Địa chính trị": 1.0,
}

# Chủ đề nào được coi là "tin Việt Nam" (dùng cho lưới an toàn mềm).
CHU_DE_VN = {"Kinh tế VN", "Chính sách"}

# Lưới an toàn MỀM: cố gắng có ít nhất bấy nhiêu tin VN trong 30 tin NẾU có sẵn.
# Ưu tiên VN chủ yếu đã nằm trong ĐIỂM (HE_SO_UU_TIEN); đây chỉ là mức tối thiểu rất
# nhẹ để bản tin không bao giờ vắng bóng tin VN. Đặt = 0 để tắt hẳn (chọn thuần điểm).
SAN_TIN_VN_MEM = 3


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
        # "Kinh tế VN" và "Chính sách" CHỈ áp cho tin từ nguồn trong nước
        # (khu_vuc == "vn"). Hai chủ đề này dùng từ CHUNG ("xuất/nhập khẩu", "tỷ giá",
        # "chính sách", "chính phủ"...) nên dễ khớp nhầm tin quốc tế rồi được nhân hệ
        # số cao (×2.0 / ×1.7) và chen lên top -> chặn theo khu vực.
        # LƯU Ý: KHÔNG chặn "Fed" theo khu vực — từ khóa Fed (fed, fomc, powell...) rất
        # đặc thù, và tin Fed thật chủ yếu đến từ nguồn quốc tế nên cần giữ ×1.7.
        if chu_de in ("Kinh tế VN", "Chính sách") and khu_vuc != "vn":
            continue
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
    bo_vi_nhieu = {}   # đếm số tin bị loại theo từng nhóm nhiễu (để log)

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

            # Loại tin "nhiễu" (quảng cáo, hình sự, lễ hội, giao thông, giá vàng ngày)
            nhieu, nhom_nhieu = la_tin_nhieu(tieu_de)
            if nhieu:
                bo_vi_nhieu[nhom_nhieu] = bo_vi_nhieu.get(nhom_nhieu, 0) + 1
                print(f"   [loại-{nhom_nhieu}] {tieu_de}")
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

    tong_nhieu = sum(bo_vi_nhieu.values())
    print(f"=> Tổng tin thô trong 24h (tiếng Việt): {len(tin_tho)} "
          f"(đã loại {bo_vi_tieng_anh} tin không phải tiếng Việt, "
          f"{tong_nhieu} tin nhiễu)")
    if bo_vi_nhieu:
        chi_tiet = ", ".join(f"{k}={v}" for k, v in sorted(bo_vi_nhieu.items()))
        print(f"   Chi tiết tin nhiễu bị loại: {chi_tiet}")
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
             + (tổng TRỌNG SỐ các từ khóa nóng xuất hiện trong tiêu đề)
             + (điểm mới)
    điểm     = điểm_gốc * HỆ SỐ ƯU TIÊN theo chủ đề (CHỈ áp dụng nếu tiêu đề khớp
               ít nhất 1 từ khóa tài chính-kinh tế cụ thể trong TRONG_SO_TU_KHOA —
               xem GHI CHÚ bên dưới)
             + DIEM_THUONG_KHAN_CAP (nếu là tin khẩn cấp - xem la_tin_khan_cap)

    GHI CHÚ QUAN TRỌNG (sửa lỗi "tin rác điểm cao"): trước đây HỆ SỐ ƯU TIÊN nhân
    vào điểm gốc ngay cả khi tiêu đề KHÔNG khớp từ khóa tài chính cụ thể nào — chỉ
    cần được gán chủ đề "Kinh tế VN"/"Chính sách" (thường do fallback theo khu_vực
    nguồn, hoặc chỉ khớp từ chung như "thủ tướng") là đã được nhân hệ số x2.0/x2.0.
    Hệ quả: các tin kiểu thông cáo hành chính/dự án hạ tầng địa phương chung chung
    (vd "TP HCM thành lập khu thương mại tự do...", "Đồng Nai định hướng thành
    trung tâm hàng không...") vẫn đạt ~26 điểm dù KHÔNG có nội dung tài chính cụ
    thể nào, chỉ nhờ hệ số nhân — chiếm mất chỗ của tin lãi suất/lạm phát/doanh
    nghiệp thực chất hơn. Nay CHỈ nhân hệ số khi diem_tu_khoa > 0 (tức tiêu đề có
    ít nhất 1 từ khóa tài chính-kinh tế cụ thể) — nếu không, hệ số = 1.0.
    """
    bay_gio = datetime.now(timezone.utc)

    ket_qua = []
    for nhom in nhom_list:
        so_nguon = len(nhom["nguon_set"])
        t = nhom["tieu_de"].lower()

        diem_tu_khoa = sum(ts for tu, ts in TRONG_SO_TU_KHOA.items() if tu in t)
        diem_mo = diem_moi(nhom["gio_dang"], bay_gio)

        diem_goc = so_nguon * 3 + diem_tu_khoa + diem_mo

        chu_de = gan_chu_de(nhom["tieu_de"], nhom["khu_vuc"])
        he_so = HE_SO_UU_TIEN.get(chu_de, 1.0) if diem_tu_khoa > 0 else 1.0
        tong_diem = round(diem_goc * he_so, 1)

        # Tin khẩn cấp: cộng thẳng điểm thưởng SAU hệ số, để luôn đứng đầu bảng
        # bất kể chủ đề/số nguồn/độ mới ra sao.
        khan_cap = la_tin_khan_cap(nhom["tieu_de"])
        if khan_cap:
            tong_diem = round(tong_diem + DIEM_THUONG_KHAN_CAP, 1)

        gio_vn = nhom["gio_dang"].astimezone(GIO_VN)
        ket_qua.append({
            "tieu_de": nhom["tieu_de"],
            "chu_de": chu_de,
            "nguon": ", ".join(sorted(nhom["nguon_set"])),
            "so_nguon": so_nguon,
            "thoi_gian": gio_vn.strftime("%Y-%m-%d %H:%M"),
            "link": nhom["link"],
            "diem": tong_diem,
            "khan_cap": khan_cap,            # cờ hiển thị badge "khẩn cấp" ở frontend
            "_la_vn": chu_de in CHU_DE_VN,   # cờ nội bộ cho hạn ngạch
        })

    return ket_qua


# ---------------------------------------------------------------------------
# 8. CHỌN 30 TIN THEO ĐIỂM (ưu tiên VN MỀM, không ép sàn/trần cứng)
# ---------------------------------------------------------------------------
# Giới hạn số tin TỐI ĐA cho một số cụm từ/chủ đề hẹp, để tránh nhiều bài cùng
# nói về một chủ điểm hẹp (thường là các bài kiểu "cập nhật phiên" lặp lại gần
# giống nhau) chiếm nhiều chỗ, không còn đất cho tin đa dạng khác. Thêm cụm mới
# vào đây nếu sau này thấy chủ điểm nào khác cũng bị lặp nhiều.
GIOI_HAN_THEO_TU_KHOA = {
    "lãi suất liên ngân hàng": 1,
}


def chon_tin_uu_tien(danh_sach, tong=30):
    """
    Chọn tối đa `tong` tin THEO ĐIỂM GIẢM DẦN, có 2 lớp điều chỉnh:

    1. GIỚI HẠN THEO CỤM TỪ (GIOI_HAN_THEO_TU_KHOA): duyệt danh sách đã xếp hạng
       theo điểm, bỏ qua các tin VƯỢT QUÁ số lượng cho phép của một cụm từ hẹp
       (vd tối đa 1 tin "lãi suất liên ngân hàng") — nhường chỗ cho tin điểm thấp
       hơn nhưng thuộc chủ điểm khác được chọn thay, thay vì lấy y nguyên top N.
    2. Lưới an toàn MỀM cho tin VN (SAN_TIN_VN_MEM) — giữ nguyên logic cũ.
    """
    xep = sorted(danh_sach, key=lambda x: x["diem"], reverse=True)

    final = []
    dem_theo_nhom = {tu: 0 for tu in GIOI_HAN_THEO_TU_KHOA}
    for tin in xep:
        if len(final) >= tong:
            break
        t = tin["tieu_de"].lower()
        vuot_gioi_han = any(
            tu in t and dem_theo_nhom[tu] >= gioi_han
            for tu, gioi_han in GIOI_HAN_THEO_TU_KHOA.items()
        )
        if vuot_gioi_han:
            continue
        final.append(tin)
        for tu in GIOI_HAN_THEO_TU_KHOA:
            if tu in t:
                dem_theo_nhom[tu] += 1

    da_chon_id = {id(t) for t in final}

    # ----- Lưới an toàn mềm cho tin VN -----
    if SAN_TIN_VN_MEM > 0:
        so_vn = sum(1 for t in final if t["_la_vn"])
        # Các tin VN CHƯA được chọn (điểm cao trước) để bù vào nếu thiếu sàn.
        vn_du_bi = [t for t in xep if id(t) not in da_chon_id and t["_la_vn"]]
        i_bu = 0
        while so_vn < SAN_TIN_VN_MEM and i_bu < len(vn_du_bi):
            tin_vn = vn_du_bi[i_bu]; i_bu += 1
            # Thay tin KHÔNG-VN điểm thấp nhất trong final bằng tin VN dự bị.
            for j in range(len(final) - 1, -1, -1):
                if not final[j]["_la_vn"]:
                    final[j] = tin_vn
                    so_vn += 1
                    break
            else:
                break  # final đã toàn tin VN, không còn gì để thay

    # Sắp lại toàn bộ theo điểm giảm dần cho gọn.
    final.sort(key=lambda x: x["diem"], reverse=True)
    return final


# ---------------------------------------------------------------------------
# 8b. LỊCH SỰ KIỆN (Event Calendar) — tầng 11 trong khung tham khảo chủ dự án
#     gửi. KHÁC HẲN phần scrape tin ở trên: đây là các mốc THỜI GIAN ĐÃ BIẾT
#     TRƯỚC, không lấy được qua RSS. Xuất ra file RIÊNG (lich_su_kien.json),
#     không trộn vào data.json của bảng tin.
# ---------------------------------------------------------------------------
# Lịch họp FOMC 2026 đã được Fed CÔNG BỐ CHÍNH THỨC trước cả năm (ngày ghi ở đây
# là ngày công bố quyết định lãi suất = ngày thứ 2 của kỳ họp 2 ngày). Khi sang
# năm mới, cập nhật lại danh sách này theo lịch chính thức tại
# https://www.federalreserve.gov/monetarypolicy/fomccalendars.htm
LICH_FOMC_2026 = [
    "2026-01-28", "2026-03-18", "2026-04-29", "2026-06-17",
    "2026-07-29", "2026-09-16", "2026-10-28", "2026-12-09",
]


def tinh_ngay_dao_han_phai_sinh(nam: int, thang: int) -> date:
    """
    Ngày đáo hạn hợp đồng phái sinh VN30F1M = THỨ NĂM của TUẦN THỨ 3 trong tháng
    (quy luật cố định của HNX/VNDIRECT, không đổi qua các năm).
    """
    ngay1 = date(nam, thang, 1)
    # weekday(): Monday=0 ... Thursday=3 ... Sunday=6
    offset = (3 - ngay1.weekday()) % 7
    thu5_dau_tien = ngay1 + timedelta(days=offset)
    return thu5_dau_tien + timedelta(days=14)  # nhảy thêm 2 tuần = tuần thứ 3


def tao_lich_su_kien(so_ngay_toi: int = 30):
    """
    Trả về danh sách sự kiện trong `so_ngay_toi` ngày tới (mặc định 30), gồm:
      1. Họp FOMC — tự động, lấy từ LICH_FOMC_2026.
      2. Đáo hạn phái sinh VN30F1M — tự động TÍNH theo quy luật cố định.
      3. Sự kiện THỦ CÔNG (chốt quyền cổ tức, công bố KQKD, IPO, MSCI/FTSE
         review...) — đọc từ su_kien_thu_cong.json NẾU file này tồn tại.
         File này KHÔNG tự sinh được vì cần dữ liệu riêng của từng công ty mà
         RSS tin tức không cung cấp — người dùng tự thêm dòng mới vào đó.
    Sắp xếp theo ngày tăng dần.
    """
    hom_nay = datetime.now(GIO_VN).date()
    han_cuoi = hom_nay + timedelta(days=so_ngay_toi)
    su_kien = []

    # ----- 1. FOMC -----
    for ngay_str in LICH_FOMC_2026:
        ngay = datetime.strptime(ngay_str, "%Y-%m-%d").date()
        if hom_nay <= ngay <= han_cuoi:
            su_kien.append({
                "ngay": ngay.isoformat(),
                "ten": "Họp FOMC - công bố lãi suất điều hành Fed",
                "loai": "Fed",
            })

    # ----- 2. Đáo hạn phái sinh VN30F1M (kiểm tra tháng này + tháng sau) -----
    for i in (0, 1):
        thang = hom_nay.month + i
        nam = hom_nay.year
        if thang > 12:
            thang -= 12
            nam += 1
        ngay_dao_han = tinh_ngay_dao_han_phai_sinh(nam, thang)
        if hom_nay <= ngay_dao_han <= han_cuoi:
            su_kien.append({
                "ngay": ngay_dao_han.isoformat(),
                "ten": "Đáo hạn hợp đồng phái sinh VN30F1M",
                "loai": "Chứng khoán VN",
            })

    # ----- 3. Sự kiện thủ công (nếu có file) -----
    try:
        with open("su_kien_thu_cong.json", "r", encoding="utf-8") as f:
            danh_sach_thu_cong = json.load(f)
        for sk in danh_sach_thu_cong:
            ngay = datetime.strptime(sk["ngay"], "%Y-%m-%d").date()
            if hom_nay <= ngay <= han_cuoi:
                su_kien.append(sk)
    except FileNotFoundError:
        pass  # Chưa tạo file — bỏ qua, không phải lỗi.
    except (json.JSONDecodeError, KeyError, ValueError) as e:
        print(f"   !! Lỗi đọc su_kien_thu_cong.json, bỏ qua sự kiện thủ công: {e}")

    su_kien.sort(key=lambda s: s["ngay"])
    return su_kien


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

    # ----- Lịch sự kiện (tầng 11) - file RIÊNG, không trộn vào data.json -----
    lich = tao_lich_su_kien(so_ngay_toi=30)
    lich_output = {
        "cap_nhat_luc": datetime.now(GIO_VN).strftime("%Y-%m-%d %H:%M:%S"),
        "su_kien": lich,
    }
    with open("lich_su_kien.json", "w", encoding="utf-8") as f:
        json.dump(lich_output, f, ensure_ascii=False, indent=2)
    print(f"=> Đã ghi lich_su_kien.json với {len(lich)} sự kiện trong 30 ngày tới.")


if __name__ == "__main__":
    main()
