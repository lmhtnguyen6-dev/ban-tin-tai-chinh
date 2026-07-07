# 📰 Bản tin Tài chính - Địa chính trị

Thu thập tin tài chính & địa chính trị từ nhiều nguồn RSS, tự chấm **"điểm hot"**
bằng code thuần (không dùng AI), gộp tin trùng và hiển thị thành trang web tĩnh.
Chạy tự động **miễn phí** bằng GitHub Actions + GitHub Pages.

---

## 1. Các file trong dự án

| File | Dùng làm gì |
|------|-------------|
| `scraper.py` | "Bộ não" của dự án. Lấy tin từ RSS, lọc 24h gần nhất, gộp tin trùng, chấm điểm hot, xuất `data.json`. |
| `requirements.txt` | Danh sách thư viện Python cần cài (ở đây là `feedparser`). |
| `data.json` | Dữ liệu tin đã xử lý. File này được workflow tự động cập nhật. |
| `index.html` | Khung trang web hiển thị (cấu trúc HTML). |
| `style.css` | Trang trí cho trang web (màu sắc, bảng, nút lọc…). |
| `script.js` | Đọc `data.json`, render bảng tin, nút lọc chủ đề, ô "cập nhật lúc mấy giờ". |
| `.github/workflows/scrape.yml` | Lịch tự động: cứ 15 phút chạy `scraper.py` rồi commit `data.json` nếu có thay đổi. |
| `README.md` | File hướng dẫn này. |

---

## 2. Chạy thử trên máy (tuỳ chọn)

Cần cài Python trước. Sau đó:

```bash
pip install -r requirements.txt
python scraper.py
```

Mở `index.html` bằng trình duyệt để xem kết quả.
> Lưu ý: mở trực tiếp file có thể bị chặn `fetch`. Cách chắc ăn là chạy 1 web
> server nhỏ: `python -m http.server` rồi mở http://localhost:8000

---

## 3. Đưa lên GitHub

### Bước 1 — Tạo repo
1. Vào https://github.com → bấm **New repository**.
2. Đặt tên (ví dụ `ban-tin-tai-chinh`), chọn **Public**, bấm **Create repository**.

### Bước 2 — Push code lên
Trong thư mục dự án, chạy (thay `<USERNAME>` và `<REPO>` cho đúng):

```bash
git init
git add .
git commit -m "Khoi tao du an ban tin"
git branch -M main
git remote add origin https://github.com/<USERNAME>/<REPO>.git
git push -u origin main
```

---

## 4. Bật GitHub Pages (để có trang web)

1. Vào repo → tab **Settings** → mục **Pages** (menu bên trái).
2. Ở **Source**, chọn **Deploy from a branch**.
3. **Branch**: chọn `main`, thư mục `/ (root)` → bấm **Save**.
4. Chờ ~1 phút, GitHub sẽ hiện link dạng:
   `https://<USERNAME>.github.io/<REPO>/`

Đó là trang web bản tin của bạn.

---

## 5. Kiểm tra workflow chạy

1. Vào repo → tab **Actions**.
2. Lần đầu, GitHub có thể hỏi bật workflow → bấm **I understand my workflows, enable them**.
3. Chọn workflow **"Thu thap tin tuc"** → bấm **Run workflow** để chạy tay ngay
   (không cần chờ 15 phút).
4. Bấm vào lần chạy để xem log từng bước. Nếu thành công, `data.json` sẽ được
   cập nhật và trang web tự có tin mới.

> **Lưu ý về cron**: lịch `*/15 * * * *` chạy theo giờ **UTC** và GitHub thường
> chạy trễ vài phút hoặc bỏ nhịp khi hệ thống bận — đây là hành vi bình thường
> của GitHub Actions miễn phí.

---

## 6. Về các nguồn RSS (đọc kỹ phần này)

Các URL đã điền sẵn trong `scraper.py`. Một vài lưu ý:

- ✅ **VnExpress Kinh doanh, CNBC, Nikkei Asia**: RSS ổn định.
- ⚠️ **CafeF, Vietstock**: đôi khi đổi đường dẫn hoặc chặn. Nếu thấy nguồn nào
  luôn trống trong log, hãy mở `scraper.py` phần `RSS_SOURCES` và thay URL khác
  (gợi ý URL thay thế đã ghi ngay trong comment).
- ⚠️ **Reuters**: Reuters **đã bỏ RSS công khai từ 2020**. Mình đã thay bằng
  **Google News RSS lọc theo reuters.com** để vẫn có tin. Nếu muốn nguồn khác,
  sửa URL trong phần `RSS_SOURCES`.

Khi chạy `python scraper.py`, log sẽ in rõ nguồn nào trống để bạn biết mà thay.

---

## 7. Cách tính "điểm hot" (code thuần, không AI)

```
điểm = (số nguồn đăng trùng) × 3
     + (số lần lặp từ khóa nóng trong ngày)
     + (điểm mới: tin càng mới điểm càng cao, tối đa ~10)
```

- **Số nguồn trùng**: nhiều báo cùng đăng 1 sự kiện → sự kiện càng quan trọng.
- **Từ khóa nóng**: Fed, lãi suất, lạm phát, chiến tranh… (sửa trong
  `TU_KHOA_NONG` ở `scraper.py`).
- **Điểm mới**: tin 0h tuổi ≈ 10 điểm, tin đúng 24h ≈ 0 điểm.

Muốn đổi công thức, chủ đề hay từ khóa → chỉ cần sửa các danh sách ở đầu
`scraper.py`, có comment tiếng Việt đầy đủ.
