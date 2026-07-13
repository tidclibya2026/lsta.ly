const categories = [
  ["المواقع الأثرية", 2372],
  ["المواقع الطبيعية", 1534],
  ["المقاهي", 1282],
  ["المطاعم", 1062],
  ["مواقع الجذب", 920],
  ["المواقع التاريخية", 724],
];

const chart = document.getElementById("categoryChart");
const maxValue = Math.max(...categories.map(([, value]) => value));
categories.forEach(([label, value]) => {
  const row = document.createElement("div");
  row.className = "bar-row";
  row.innerHTML = `
    <label>${label}</label>
    <div class="bar-track"><div class="bar-fill" style="width:${(value / maxValue) * 100}%"></div></div>
    <b>${value.toLocaleString("ar-LY")}</b>`;
  chart.appendChild(row);
});

const map = L.map("nationalMap", { zoomControl: false }).setView([27.2, 17.1], 5);
L.control.zoom({ position: "bottomleft" }).addTo(map);
L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
  maxZoom: 18,
  attribution: "© OpenStreetMap",
}).addTo(map);

const locations = [
  { name: "طرابلس", coords: [32.8872, 13.1913], status: "verified", sites: 965 },
  { name: "بنغازي", coords: [32.1167, 20.0667], status: "verified", sites: 704 },
  { name: "غدامس", coords: [30.1337, 9.5007], status: "review", sites: 141 },
  { name: "سبها", coords: [27.0377, 14.4283], status: "review", sites: 328 },
  { name: "شحات", coords: [32.8287, 21.8621], status: "verified", sites: 210 },
  { name: "غات", coords: [24.9647, 10.1728], status: "verified", sites: 279 },
  { name: "أوباري", coords: [26.5903, 12.7805], status: "critical", sites: 88 },
];

const colorMap = { verified: "#17855b", review: "#b87912", critical: "#c43d4f" };
const markerLayer = L.layerGroup().addTo(map);
function drawMarkers(mode = "sites") {
  markerLayer.clearLayers();
  locations.forEach((location) => {
    const radius = mode === "sites" ? 7 + Math.sqrt(location.sites) / 4 : 9;
    const color = mode === "investment" ? "#d8a437" : colorMap[location.status];
    L.circleMarker(location.coords, {
      radius,
      color: "#ffffff",
      weight: 2,
      fillColor: color,
      fillOpacity: 0.86,
    })
      .bindPopup(`<strong>${location.name}</strong><br>المواقع المسجلة: ${location.sites.toLocaleString("ar-LY")}<br>الحالة: ${location.status}`)
      .addTo(markerLayer);
  });
}
drawMarkers();

document.querySelectorAll("[data-map-mode]").forEach((button) => {
  button.addEventListener("click", () => {
    document.querySelectorAll("[data-map-mode]").forEach((item) => item.classList.remove("active"));
    button.classList.add("active");
    drawMarkers(button.dataset.mapMode);
  });
});

document.getElementById("themeToggle").addEventListener("click", () => {
  document.body.classList.toggle("dark");
  setTimeout(() => map.invalidateSize(), 150);
});

document.getElementById("printDashboard").addEventListener("click", () => window.print());

document.getElementById("refreshDashboard").addEventListener("click", (event) => {
  const button = event.currentTarget;
  const original = button.textContent;
  button.disabled = true;
  button.textContent = "جارٍ التحديث...";
  setTimeout(() => {
    document.querySelectorAll("[data-kpi]").forEach((element) => {
      element.animate([{ opacity: 0.35 }, { opacity: 1 }], { duration: 450 });
    });
    button.textContent = "تم التحديث";
    setTimeout(() => {
      button.disabled = false;
      button.textContent = original;
    }, 900);
  }, 700);
});

document.getElementById("assistantForm").addEventListener("submit", (event) => {
  event.preventDefault();
  const input = document.getElementById("assistantInput");
  const response = document.getElementById("assistantResponse");
  const question = input.value.trim();
  response.hidden = false;
  response.innerHTML = `<strong>تحليل أولي للسؤال:</strong> ${question}<br>تُظهر البيانات النموذجية أن طرابلس وبنغازي تتصدران كثافة المواقع المسجلة. عند ربط الواجهة بواجهة API الوطنية سيعرض المساعد نتيجة موثقة، وخريطة مفلترة، ومصادر البيانات وتاريخ آخر تحقق.`;
});

document.getElementById("globalSearch").addEventListener("input", (event) => {
  const query = event.target.value.trim();
  if (!query) return;
  const matched = locations.find((location) => location.name.includes(query));
  if (matched) {
    map.flyTo(matched.coords, 8, { duration: 0.8 });
  }
});

window.addEventListener("resize", () => map.invalidateSize());
