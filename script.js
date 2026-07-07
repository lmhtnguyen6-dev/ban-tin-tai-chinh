/* ------------------------------------------------------------------
   script.js - đọc data.json và render giao diện
------------------------------------------------------------------ */

let TAT_CA_TIN = [];      // toàn bộ tin đọc từ data.json
let CHU_DE_DANG_CHON = "Tất cả";

// Bắt đầu khi trang tải xong
document.addEventListener("DOMContentLoaded", taiDuLieu);

async function taiDuLieu() {
  try {
    // Thêm ?t=... để tránh trình duyệt cache file cũ
    const res = await fetch("data.json?t=" + Date.now());
    if (!res.ok) throw new Error("HTTP " + res.status);
    const data = await res.json();

    TAT_CA_TIN = data.tin || [];

    // Hiển thị thời gian cập nhật
    document.getElementById("cap-nhat").textContent =
      "Cập nhật lúc: " + (data.cap_nhat_luc || "không rõ") +
      " · " + TAT_CA_TIN.length + " tin";

    hienDiemNong();
    taoBoLoc();
    renderBang();
  } catch (err) {
    document.getElementById("cap-nhat").textContent =
      "Không tải được data.json (" + err.message + "). Chờ workflow chạy lần đầu.";
  }
}

/* ----- Điểm nóng hôm nay: tin điểm cao nhất ----- */
function hienDiemNong() {
  if (TAT_CA_TIN.length === 0) return;
  const top = TAT_CA_TIN[0]; // data.json đã sắp theo điểm giảm dần

  const box = document.getElementById("diem-nong");
  const link = document.getElementById("diem-nong-link");
  const meta = document.getElementById("diem-nong-meta");

  link.textContent = top.tieu_de;
  link.href = top.link;
  meta.textContent =
    `${top.chu_de} · ${top.nguon} · ${top.thoi_gian} · Điểm ${top.diem}`;
  box.hidden = false;
}

/* ----- Tạo các nút lọc theo chủ đề ----- */
function taoBoLoc() {
  const nav = document.getElementById("bo-loc");
  nav.innerHTML = "";

  // Lấy danh sách chủ đề duy nhất + thêm "Tất cả" ở đầu
  const dsChuDe = ["Tất cả", ...new Set(TAT_CA_TIN.map((t) => t.chu_de))];

  dsChuDe.forEach((cd) => {
    const btn = document.createElement("button");
    btn.textContent = cd;
    if (cd === CHU_DE_DANG_CHON) btn.classList.add("active");
    btn.addEventListener("click", () => {
      CHU_DE_DANG_CHON = cd;
      taoBoLoc();   // cập nhật nút active
      renderBang();
    });
    nav.appendChild(btn);
  });
}

/* ----- Render bảng tin theo chủ đề đang chọn ----- */
function renderBang() {
  const tbody = document.getElementById("tbody-tin");
  const trong = document.getElementById("trong");
  tbody.innerHTML = "";

  const ds =
    CHU_DE_DANG_CHON === "Tất cả"
      ? TAT_CA_TIN
      : TAT_CA_TIN.filter((t) => t.chu_de === CHU_DE_DANG_CHON);

  trong.hidden = ds.length !== 0;

  ds.forEach((tin, i) => {
    const tr = document.createElement("tr");
    tr.innerHTML = `
      <td>${i + 1}</td>
      <td><a href="${tin.link}" target="_blank" rel="noopener">${escapeHtml(tin.tieu_de)}</a></td>
      <td><span class="the-chu-de">${escapeHtml(tin.chu_de)}</span></td>
      <td>${escapeHtml(tin.nguon)}</td>
      <td>${escapeHtml(tin.thoi_gian)}</td>
      <td class="diem">${tin.diem}</td>
    `;
    tbody.appendChild(tr);
  });
}

/* ----- Chống lỗi hiển thị khi tiêu đề có ký tự đặc biệt ----- */
function escapeHtml(s) {
  return String(s)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;");
}
