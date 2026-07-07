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
  niêm yết/khối ngoại 4, lợi nhuận 3...), Fed cao (fed/fomc 5). **Đã bỏ "vàng"**
  khỏi từ khóa nóng để không đẩy điểm tin giá vàng.
- **Lọc tin nhiễu** (`la_tin_nhieu`, `NHOM_TIN_NHIEU`, `LOC_NHOM_NHIEU`): loại tin
  quảng cáo vay, hình sự/pháp luật, lễ hội/đặc sản, hạ tầng giao thông hằng ngày,
  **mẹo chi tiêu/tài chính cá nhân** (nhóm `doi_song`), và **tin cập nhật giá vàng
  hằng ngày** (`CUM_GIA_VANG_HANG_NGAY`). Tin bị loại được in log `[loại-<nhóm>]`.
  Bật/tắt nhóm bằng `LOC_NHOM_NHIEU`.
- **"cáo buộc" xử lý theo ngữ cảnh** (`la_cao_buoc_hinh_su`, `NGU_CANH_HINH_SU`): từ
  "cáo buộc" hai nghĩa nên KHÔNG để trong nhóm `hinh_su`. Chỉ coi là nhiễu khi đi
  KÈM ngữ cảnh hình sự (bị bắt, khởi tố, truy tố, công an, tòa án, lừa đảo...); tin
  doanh nghiệp bị "cáo buộc gian lận/sai phạm" (có thể ảnh hưởng giá CP) được GIỮ.
  Lưu ý: KHÔNG thêm "bị cáo" vào `NGU_CANH_HINH_SU` (nó là substring của "bị cáo
  buộc" → vô hiệu hóa bộ lọc).
- **Gán chủ đề theo khu vực** (`gan_chu_de`): chủ đề "Kinh tế VN" CHỈ áp cho tin từ
  nguồn trong nước (`khu_vuc == "vn"`). Tin nguồn quốc tế dù khớp từ chung (xuất/nhập
  khẩu, tỷ giá...) sẽ về "Thế giới"/"Địa chính trị", tránh bị nhân ×2.0 sai và chen
  lên top.
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
