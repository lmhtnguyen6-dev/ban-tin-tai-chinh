# CLAUDE.md — Bối cảnh dự án cho Claude Code

File này giúp phiên Claude Code mới (trên bất kỳ máy nào) nắm ngay bối cảnh.

## Dự án là gì
Trang tin **tài chính - địa chính trị tiếng Việt**, thu thập từ RSS, tự chấm
"điểm hot" bằng **code thuần (không gọi AI)**, gộp tin trùng, xuất `data.json`,
hiển thị bằng web tĩnh. Chạy tự động **miễn phí** trên GitHub Actions + Pages.

- Repo: https://github.com/lmhtnguyen6-dev/ban-tin-tai-chinh
- Trang web: https://lmhtnguyen6-dev.github.io/ban-tin-tai-chinh/
- Chủ dự án là **người mới** với Git/deploy → giải thích ngắn gọn, dễ hiểu,
  ưu tiên tiếng Việt.

## Các file
- `scraper.py` — bộ não: lấy RSS → lọc 24h + lọc tiếng Việt → gộp trùng →
  gộp loạt bài định kỳ → chấm điểm → chọn 30 tin theo hạn ngạch → ghi `data.json`.
- `index.html` / `style.css` / `script.js` — web tĩnh đọc `data.json`.
- `.github/workflows/scrape.yml` — cron `*/15 * * * *`, chạy scraper rồi commit
  `data.json` nếu đổi. Có `workflow_dispatch` để chạy tay.
- `data.json` — dữ liệu (bot Actions tự cập nhật, KHÔNG sửa tay).
- `requirements.txt` — chỉ `feedparser`.

## Quyết định thiết kế đã chốt
- **Chỉ nguồn tiếng Việt** (đã bỏ Reuters/CNBC/Nikkei tiếng Anh). Nguồn hiện dùng:
  CafeF (Tài chính, Vĩ mô, TC quốc tế), VnExpress (Kinh doanh, Thế giới),
  Vietstock (Kinh tế, Thế giới), VietnamBiz (Tài chính, Vĩ mô).
- **Báo Đầu tư**: chưa tìm được RSS còn sống → để dòng comment sẵn trong
  `RSS_SOURCES`, thay khi họ mở lại.
- **Công thức điểm**: `điểm_gốc = số_nguồn*3 + tổng_TRỌNG_SỐ_từ_khóa + điểm_mới`,
  rồi nhân **hệ số ưu tiên theo chủ đề**: Kinh tế VN ×2.0, Chính sách ×1.7,
  Fed ×1.7, Thế giới ×1.1, Địa chính trị ×1.0 (trong `HE_SO_UU_TIEN`).
- **Từ khóa nóng CÓ TRỌNG SỐ** (`TRONG_SO_TU_KHOA`, dict): thay cho list cũ.
  Ưu tiên chứng khoán–tài chính–doanh nghiệp (vn-index 6, chứng khoán/cổ phiếu 5,
  niêm yết 4, khối ngoại 5...), Fed cao (fed/fomc 5). **Đã bỏ "vàng"**. Đã **tăng
  trọng số HOẠT ĐỘNG DOANH NGHIỆP trên sàn** để đẩy tin CK thực chất lên top: trả/chia
  cổ tức 4, phát hành/chào bán cổ phiếu 5, cổ phiếu quỹ/mua lại CP 4, đhđcđ/đại hội cổ
  đông/cổ đông lớn/thoái vốn 4, lợi nhuận/KQKD 4, thâu tóm/sáp nhập/m&a 4.
- **Lọc tin nhiễu** (`la_tin_nhieu`, `NHOM_TIN_NHIEU`, `LOC_NHOM_NHIEU`): loại tin
  quảng cáo vay, hình sự/pháp luật (gồm tội phạm ngành NH nghĩa rõ: rửa tiền, lỗ hổng
  tài khoản), lễ hội/đặc sản, hạ tầng giao thông (gồm "phạt nguội"),
  **mẹo chi tiêu/tài chính cá nhân** (`doi_song`), **PR doanh nghiệp** (`pr_doanh_nghiep`:
  vinh danh/giải thưởng/xếp hạng, ký kết-MOU, ra mắt sản phẩm-hệ thống, tài trợ),
  **nhân sự lãnh đạo thường lệ** (`nhan_su`: bổ nhiệm/miễn nhiệm/từ nhiệm — KHÔNG dùng
  "bầu" để giữ tin ĐHĐCĐ), **bình luận vĩ mô địa phương** (`vi_mo_dia_phuong`: tăng
  trưởng 2 con số của tỉnh/thành...), và **tin giá vàng hằng ngày** (`CUM_GIA_VANG_HANG_NGAY`).
  Tin bị loại in log `[loại-<nhóm>]`. Bật/tắt nhóm bằng `LOC_NHOM_NHIEU`.
- **Từ HAI NGHĨA xử lý theo ngữ cảnh** (`TU_HAI_NGHIA`, `la_tu_hai_nghia_hinh_su`,
  `NGU_CANH_HINH_SU`): "cáo buộc" và "gian lận" đều hai nghĩa nên KHÔNG để trong nhóm
  `hinh_su`. Chỉ coi là nhiễu khi đi KÈM ngữ cảnh hình sự (bị bắt, khởi tố, truy tố,
  công an, tòa án, lừa đảo, chiếm đoạt, rửa tiền...); tin doanh nghiệp bị "cáo buộc/nghi
  gian lận sổ sách, thao túng" (có thể ảnh hưởng giá CP) được GIỮ. Thêm từ hai nghĩa
  mới vào `TU_HAI_NGHIA`. Lưu ý: KHÔNG thêm "bị cáo" vào `NGU_CANH_HINH_SU` (nó là
  substring của "bị cáo buộc" → vô hiệu hóa bộ lọc).
- **Gán chủ đề theo khu vực** (`gan_chu_de`): "Kinh tế VN" và "Chính sách" CHỈ áp cho
  tin từ nguồn trong nước (`khu_vuc == "vn"`) — hai chủ đề này dùng từ CHUNG (xuất/nhập
  khẩu, tỷ giá, "chính sách", "chính phủ"...) nên dễ khớp nhầm tin quốc tế rồi bị nhân
  hệ số cao (×2.0 / ×1.7). Tin nguồn quốc tế sẽ về "Thế giới"/"Địa chính trị".
  **KHÔNG chặn "Fed" theo khu vực** — từ khóa Fed đặc thù, tin Fed thật chủ yếu từ
  nguồn quốc tế nên cần giữ ×1.7. Lưu ý: tin nội dung nước ngoài do nguồn VN đăng (vd
  VnExpress Kinh doanh) vẫn có `khu_vuc="vn"` nên bộ chặn theo NGUỒN không bắt được —
  hạn chế cố hữu, chấp nhận vì các tin đó thường điểm thấp.
- **Chọn 30 tin — ưu tiên VN MỀM** (`chon_tin_uu_tien`, `SAN_TIN_VN_MEM`): chọn
  THUẦN theo điểm giảm dần. Ưu tiên VN nằm sẵn trong điểm (`HE_SO_UU_TIEN`) nên tin
  Fed/thế giới điểm cao lên top TỰ NHIÊN. ĐÃ BỎ sàn cứng ≥6 tin VN và trần cứng tin
  quốc tế. Chỉ còn **lưới an toàn mềm** `SAN_TIN_VN_MEM = 3`: nếu 30 tin có <3 tin VN
  mà còn tin VN chưa dùng thì bù cho đủ 3; đặt = 0 để tắt hẳn (chọn hoàn toàn theo
  điểm). Ưu điểm: bản tin không bao giờ vắng bóng tin VN; nhược: hôm VN quá nhạt vẫn
  có thể chiếm 3 chỗ. Số 3 nhỏ nên ảnh hưởng không đáng kể.
- **Gộp loạt bài định kỳ** (`gop_bai_dinh_ky`): bỏ token ngày/tháng
  (`bo_token_ngay`) rồi so phần chữ; giống ≥85% thì giữ bản mới nhất + log.
- Từ khóa nóng, chủ đề, hệ số... đều ở đầu `scraper.py`, sửa dễ.

## Gotcha khi làm việc với repo này
- **Luôn `git pull --rebase` TRƯỚC khi push**: bot Actions commit `data.json`
  mỗi 15 phút nên remote thường đi trước local; không pull sẽ bị từ chối push.
- **KHÔNG sửa tay `data.json`** (bot sẽ ghi đè). Muốn đổi kết quả thì sửa logic
  trong `scraper.py`.
- Cron GitHub có thể trễ/bỏ nhịp — cần tin ngay thì vào Actions bấm "Run workflow".
- Test nhanh trên máy: `pip install -r requirements.txt` rồi `python scraper.py`.

## Ý tưởng còn để ngỏ (chưa làm)
- Thêm nguồn Báo Đầu tư khi có RSS.
- Tinh chỉnh ngưỡng gộp loạt định kỳ (hiện 0.85) nếu thấy sót.
