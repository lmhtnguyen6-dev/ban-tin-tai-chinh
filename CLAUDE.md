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
- **Công thức điểm**: `điểm_gốc = số_nguồn*3 + tần_suất_từ_khóa_nóng + điểm_mới`,
  rồi nhân **hệ số ưu tiên theo chủ đề**: Kinh tế VN ×2.0, Chính sách ×1.7,
  Fed ×1.3, Thế giới ×1.2, Địa chính trị ×1.0 (trong `HE_SO_UU_TIEN`).
- **Hạn ngạch** (`chon_tin_uu_tien`): ≤10 tin không-VN trong 15 vị trí cuối,
  đảm bảo ≥6 tin chủ đề VN.
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
