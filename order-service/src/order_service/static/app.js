"use strict";
const ORDER_API = "";                               // cùng origin với trang này
const PRODUCT_API = window.PRODUCT_API || "http://localhost:8091";
const STATUS = { PENDING: "Chờ xác nhận", CONFIRMED: "Đã xác nhận", SHIPPING: "Đang giao", DELIVERED: "Đã giao", CANCELLED: "Đã hủy" };
const NEXT = { PENDING: ["CONFIRMED", "CANCELLED"], CONFIRMED: ["SHIPPING", "CANCELLED"], SHIPPING: ["DELIVERED"], DELIVERED: [], CANCELLED: [] };
const ACTION = { CONFIRMED: "Xác nhận", SHIPPING: "Giao hàng", DELIVERED: "Đã giao", CANCELLED: "Hủy đơn" };
const $ = (s) => document.querySelector(s);
const money = (v) => new Intl.NumberFormat("vi-VN").format(Number(v)) + " ₫";
const esc = (s) => String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
const state = { orders: { page: 1, size: 10 }, products: { page: 1, size: 10 }, pick: [] };

let toastTimer;
function toast(msg, bad = false) {
  const el = $("#toast");
  el.textContent = msg; el.className = bad ? "bad" : ""; el.hidden = false;
  clearTimeout(toastTimer); toastTimer = setTimeout(() => (el.hidden = true), bad ? 6000 : 2500);
}

async function api(base, path, options = {}) {
  let res;
  try {
    res = await fetch(base + path, { headers: { "Content-Type": "application/json" }, ...options });
  } catch {
    throw new Error("Không kết nối được tới dịch vụ (" + (base || "order-service") + ")");
  }
  if (res.status === 204) return null;
  const data = await res.json().catch(() => ({}));
  if (!res.ok) throw new Error(data.message || "Lỗi " + res.status);
  return data;
}
const orderApi = (p, o) => api(ORDER_API, p, o);
const productApi = (p, o) => api(PRODUCT_API, p, o);
const run = (fn) => async (...a) => { try { await fn(...a); } catch (e) { toast(e.message, true); } };

// ---- Tabs
document.querySelectorAll("nav button").forEach((b) => b.addEventListener("click", () => showTab(b.dataset.tab)));
function showTab(name) {
  document.querySelectorAll("nav button").forEach((b) => b.classList.toggle("active", b.dataset.tab === name));
  for (const t of ["orders", "new", "products"]) $("#tab-" + t).hidden = t !== name;
  if (name === "orders") run(loadOrders)();
  if (name === "new") run(loadPick)();
  if (name === "products") run(loadProducts)();
}
$("#docs-product").href = PRODUCT_API + "/docs";

// ---- Đơn hàng
async function loadOrders() {
  const { page, size } = state.orders;
  const status = $("#filter-status").value;
  const data = await orderApi(`/orders?page=${page}&size=${size}` + (status ? `&status=${status}` : ""));
  $("#orders-body").innerHTML = data.items.map((o) => `
    <tr>
      <td>${o.id}</td>
      <td>${esc(o.customer_name)}<br><span class="muted">${esc(o.customer_phone)}${o.address ? " · " + esc(o.address) : ""}</span></td>
      <td><ul class="items">${o.items.map((i) => `<li>${esc(i.product_name)} × ${i.quantity}</li>`).join("")}</ul></td>
      <td class="num">${money(o.total_amount)}</td>
      <td><span class="badge ${o.status}">${STATUS[o.status]}</span></td>
      <td class="muted">${new Date(o.created_at).toLocaleString("vi-VN")}</td>
      <td>
        ${NEXT[o.status].map((s) => `<button class="small ${s === "CANCELLED" ? "danger" : ""}" data-act="status" data-id="${o.id}" data-to="${s}">${ACTION[s]}</button>`).join("")}
        ${o.status === "PENDING" ? `<button class="small ghost" data-act="edit" data-id="${o.id}">Sửa</button>` : ""}
        ${["PENDING", "CANCELLED"].includes(o.status) ? `<button class="small ghost" data-act="delete" data-id="${o.id}">Xóa</button>` : ""}
      </td>
    </tr>`).join("") || `<tr><td colspan="7" class="muted">Chưa có đơn hàng nào</td></tr>`;
  const pages = Math.max(1, Math.ceil(data.total / size));
  $("#orders-page").textContent = `Trang ${page}/${pages} · ${data.total} đơn`;
  $("#orders-prev").disabled = page <= 1; $("#orders-next").disabled = page >= pages;
  state.orders.items = Object.fromEntries(data.items.map((o) => [o.id, o]));
}
$("#filter-status").addEventListener("change", () => { state.orders.page = 1; run(loadOrders)(); });
$("#reload-orders").addEventListener("click", run(loadOrders));
$("#orders-prev").addEventListener("click", () => { state.orders.page--; run(loadOrders)(); });
$("#orders-next").addEventListener("click", () => { state.orders.page++; run(loadOrders)(); });
$("#orders-body").addEventListener("click", run(async (e) => {
  const b = e.target.closest("button[data-act]"); if (!b) return;
  const id = b.dataset.id;
  if (b.dataset.act === "status") {
    if (b.dataset.to === "CANCELLED" && !confirm(`Hủy đơn #${id}? Hàng sẽ được hoàn lại kho.`)) return;
    await orderApi(`/orders/${id}/status`, { method: "PATCH", body: JSON.stringify({ status: b.dataset.to }) });
    toast(`Đơn #${id}: ${STATUS[b.dataset.to]}`);
  } else if (b.dataset.act === "delete") {
    if (!confirm(`Xóa đơn #${id}?`)) return;
    await orderApi(`/orders/${id}`, { method: "DELETE" });
    toast(`Đã xóa đơn #${id}`);
  } else if (b.dataset.act === "edit") {
    const o = state.orders.items[id], f = $("#order-edit-form");
    for (const k of ["id", "customer_name", "customer_phone", "address", "note"]) f.elements[k].value = o[k] ?? "";
    $("#order-edit-title").textContent = `Sửa thông tin đơn #${id}`;
    $("#order-dialog").showModal(); return;
  }
  await loadOrders();
}));
$("#order-cancel").addEventListener("click", () => $("#order-dialog").close());
$("#order-edit-form").addEventListener("submit", run(async (e) => {
  e.preventDefault();
  const f = e.target.elements;
  const body = { customer_name: f.customer_name.value, customer_phone: f.customer_phone.value, address: f.address.value || null, note: f.note.value || null };
  await orderApi(`/orders/${f.id.value}`, { method: "PUT", body: JSON.stringify(body) });
  $("#order-dialog").close(); toast("Đã cập nhật đơn"); await loadOrders();
}));

// ---- Tạo đơn
async function loadPick() {
  const data = await productApi("/products?size=200");
  const old = Object.fromEntries(state.pick.map((p) => [p.id, p.qty]));
  state.pick = data.items.map((p) => ({ ...p, qty: Math.min(old[p.id] || 0, p.quantity) }));
  $("#pick-body").innerHTML = state.pick.map((p) => `
    <tr><td>${esc(p.name)} <span class="muted">${esc(p.sku)}</span></td>
    <td class="num">${money(p.price)}</td>
    <td class="num ${p.quantity === 0 ? "low" : ""}">${p.quantity}</td>
    <td class="num"><input type="number" min="0" step="1" value="${p.qty}" data-id="${p.id}" style="width:90px"></td>
    <td class="num" id="line-${p.id}">${money(p.qty * p.price)}</td></tr>`).join("") || `<tr><td colspan="5" class="muted">Chưa có sản phẩm. Hãy thêm ở tab Sản phẩm.</td></tr>`;
  updateTotal();
}
function updateTotal() {
  let total = 0;
  for (const p of state.pick) { total += p.qty * p.price; const el = $("#line-" + p.id); if (el) el.textContent = money(p.qty * p.price); }
  $("#pick-total").textContent = money(total);
}
$("#pick-body").addEventListener("input", (e) => {
  const id = Number(e.target.dataset.id); if (!id) return;
  state.pick.find((p) => p.id === id).qty = Math.max(0, parseInt(e.target.value, 10) || 0);
  $("#stock-preview").hidden = true; updateTotal();
});
const pickedItems = () => state.pick.filter((p) => p.qty > 0).map((p) => ({ product_id: p.id, quantity: p.qty }));
$("#btn-check").addEventListener("click", run(async () => {
  const items = pickedItems();
  if (!items.length) return toast("Hãy chọn ít nhất một sản phẩm", true);
  const r = await orderApi("/orders/check-stock", { method: "POST", body: JSON.stringify({ items }) });
  const box = $("#stock-preview"); box.hidden = false; box.className = "notice" + (r.all_enough ? "" : " bad");
  box.innerHTML = (r.all_enough ? "Đủ hàng cho tất cả sản phẩm." : "Thiếu hàng:") + "<ul>" + r.items.filter((l) => !l.enough || !r.all_enough)
    .map((l) => `<li>${esc(l.product_name || "Sản phẩm #" + l.product_id)}: cần ${l.requested}, còn ${l.available}</li>`).join("") + "</ul>";
}));
$("#order-form").addEventListener("submit", run(async (e) => {
  e.preventDefault();
  const items = pickedItems();
  if (!items.length) return toast("Hãy chọn ít nhất một sản phẩm", true);
  const f = e.target.elements;
  const body = { customer_name: f.customer_name.value, customer_phone: f.customer_phone.value, address: f.address.value || null, note: f.note.value || null, items };
  const order = await orderApi("/orders", { method: "POST", body: JSON.stringify(body) });
  toast(`Đã tạo đơn #${order.id} - ${money(order.total_amount)}`);
  e.target.reset(); state.pick = []; $("#stock-preview").hidden = true;
  showTab("orders");
}));

// ---- Sản phẩm
async function loadProducts() {
  const { page, size } = state.products;
  const q = $("#product-q").value.trim();
  const data = await productApi(`/products?page=${page}&size=${size}` + (q ? `&q=${encodeURIComponent(q)}` : ""));
  $("#products-body").innerHTML = data.items.map((p) => `
    <tr><td>${p.id}</td><td>${esc(p.sku)}</td><td>${esc(p.name)}<br><span class="muted">${esc(p.description || "")}</span></td>
    <td class="num">${money(p.price)}</td><td class="num ${p.quantity === 0 ? "low" : ""}">${p.quantity}</td>
    <td><button class="small ghost" data-act="edit" data-id="${p.id}">Sửa</button><button class="small danger" data-act="delete" data-id="${p.id}">Xóa</button></td></tr>`).join("")
    || `<tr><td colspan="6" class="muted">Không có sản phẩm</td></tr>`;
  const pages = Math.max(1, Math.ceil(data.total / size));
  $("#products-page").textContent = `Trang ${page}/${pages} · ${data.total} sản phẩm`;
  $("#products-prev").disabled = page <= 1; $("#products-next").disabled = page >= pages;
  state.products.items = Object.fromEntries(data.items.map((p) => [p.id, p]));
}
let qTimer;
$("#product-q").addEventListener("input", () => { clearTimeout(qTimer); qTimer = setTimeout(() => { state.products.page = 1; run(loadProducts)(); }, 300); });
$("#products-prev").addEventListener("click", () => { state.products.page--; run(loadProducts)(); });
$("#products-next").addEventListener("click", () => { state.products.page++; run(loadProducts)(); });
function openProduct(p) {
  const f = $("#product-form").elements;
  f.id.value = p?.id ?? ""; f.sku.value = p?.sku ?? ""; f.name.value = p?.name ?? "";
  f.description.value = p?.description ?? ""; f.price.value = p ? Number(p.price) : ""; f.quantity.value = p?.quantity ?? 0;
  $("#product-title").textContent = p ? `Sửa sản phẩm #${p.id}` : "Thêm sản phẩm";
  $("#product-dialog").showModal();
}
$("#btn-new-product").addEventListener("click", () => openProduct(null));
$("#product-cancel").addEventListener("click", () => $("#product-dialog").close());
$("#products-body").addEventListener("click", run(async (e) => {
  const b = e.target.closest("button[data-act]"); if (!b) return;
  const p = state.products.items[b.dataset.id];
  if (b.dataset.act === "edit") return openProduct(p);
  if (!confirm(`Xóa sản phẩm "${p.name}"?`)) return;
  await productApi(`/products/${p.id}`, { method: "DELETE" });
  toast("Đã xóa sản phẩm"); await loadProducts();
}));
$("#product-form").addEventListener("submit", run(async (e) => {
  e.preventDefault();
  const f = e.target.elements, id = f.id.value;
  const body = { sku: f.sku.value, name: f.name.value, description: f.description.value || null, price: f.price.value, quantity: parseInt(f.quantity.value, 10) };
  await productApi(id ? `/products/${id}` : "/products", { method: id ? "PUT" : "POST", body: JSON.stringify(body) });
  $("#product-dialog").close(); toast(id ? "Đã cập nhật sản phẩm" : "Đã thêm sản phẩm"); await loadProducts();
}));

run(loadOrders)();
