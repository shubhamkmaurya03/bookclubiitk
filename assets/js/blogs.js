/* Blogs & Events: All / Reviews / Events filter, and the newest Instagram posts loaded live.
   On the home page (data-events="3") it keeps just that many of the newest posts. */
(function () {
  var grid = document.querySelector(".posts[data-feed]");
  if (!grid) return;
  var lead = document.querySelector(".lead-post");
  var empty = document.querySelector(".feed-empty");
  var buttons = document.querySelectorAll(".feed-filter .chip");
  var live = grid.getAttribute("data-live");
  var limit = parseInt(grid.getAttribute("data-events"), 10) || 0;
  var shows = ["all", "review", "event"];
  var show = shows.indexOf(new URLSearchParams(location.search).get("show")) !== -1
    ? new URLSearchParams(location.search).get("show") : "all";

  function esc(s) {
    return String(s).replace(/[&<>"']/g, function (c) {
      return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c];
    });
  }

  function apply() {
    var visible = 0;
    [].forEach.call(grid.querySelectorAll("[data-kind]"), function (c) {
      c.hidden = show !== "all" && c.getAttribute("data-kind") !== show;
      if (!c.hidden) visible++;
    });
    if (lead) lead.hidden = show === "event";
    if (empty) empty.hidden = visible > 0 || (lead && !lead.hidden);
    [].forEach.call(buttons, function (b) {
      b.setAttribute("aria-pressed", b.getAttribute("data-show") === show ? "true" : "false");
    });
  }
  [].forEach.call(buttons, function (b) {
    b.addEventListener("click", function () {
      show = b.getAttribute("data-show");
      history.replaceState(null, "", location.pathname + (show === "all" ? "" : "?show=" + show));
      apply();
    });
  });
  apply();

  /* ---- live Instagram posts (same markup as tools/build_site.py card_event) ---- */
  if (!live || !window.fetch) return;
  var ARROW = '<svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M5 12h14M13 6l6 6-6 6"/></svg>';
  var arrowEl = document.querySelector(".event-card .on-insta svg");
  if (arrowEl) ARROW = arrowEl.outerHTML;

  function valid(p) {
    return p && /^\d{5,30}$/.test(p.id) && typeof p.url === "string" && p.url.indexOf("https://www.instagram.com/") === 0 &&
      typeof p.time === "string" && /^\d{4}-\d\d-\d\dT\d\d:\d\d/.test(p.time) && !isNaN(new Date(p.time)) &&
      typeof p.caption === "string" && typeof p.image === "string" && /^assets\/instagram\/\d+\.jpg$/.test(p.image);
  }
  function split(text) {
    var lines = text.split("\n").map(function (l) { return l.trim(); }).filter(Boolean);
    var title = lines[0] || "On Instagram", rest = lines.slice(1).join(" ");
    if (title.length > 110) title = title.slice(0, 107).replace(/\s+\S*$/, "") + "…";
    if (rest.length > 170) rest = rest.slice(0, 167).replace(/\s+\S*$/, "") + "…";
    return [title, rest];
  }
  function card(p) {
    var t = split(p.caption), when = new Date(p.time);
    var date = when.toLocaleDateString("en-IN", { day: "numeric", month: "long", year: "numeric", timeZone: "Asia/Kolkata" });
    var badge = p.type === "video" ? '<span class="event-badge">▶ Video</span>' : p.type === "album" ? '<span class="event-badge">Album</span>' : "";
    return '<a class="post-card event-card" href="' + esc(p.url) + '" target="_blank" rel="noopener" data-kind="event" data-id="' +
      esc(p.id) + '" data-date="' + esc(p.time.slice(0, 16)) + '"><div class="event-pic"><img src="' + esc(new URL(p.image, new URL("..", live)).href) +
      '" alt="" loading="lazy" width="600" height="600">' + badge + '</div><span class="post-meta">Event · ' + esc(date) +
      '</span><h3>' + esc(t[0]) + '</h3>' + (t[1] ? '<span class="by">' + esc(t[1]) + '</span>' : "") +
      '<span class="on-insta">View on Instagram ' + ARROW + '</span></a>';
  }

  fetch(live + (live.indexOf("?") === -1 ? "?" : "&") + "t=" + Date.now(),
        { cache: "no-store", credentials: "omit", referrerPolicy: "no-referrer" })
    .then(function (r) { return r.ok ? r.json() : null; })
    .then(function (d) {
      var posts = d && Array.isArray(d.posts) ? d.posts.filter(valid) : [];
      if (!posts.length) return;                       // keep what the page already shows
      if (limit) {                                      // home: the newest few, before the review
        posts.sort(function (a, b) { return b.time.localeCompare(a.time); });
        [].forEach.call(grid.querySelectorAll('[data-kind="event"]'), function (c) { grid.removeChild(c); });
        grid.insertAdjacentHTML("afterbegin", posts.slice(0, limit).map(card).join(""));
        return;
      }
      var have = {}, keep = {};
      [].forEach.call(grid.querySelectorAll('[data-kind="event"]'), function (c) { have[c.getAttribute("data-id")] = c; });
      posts.forEach(function (p) {
        keep[p.id] = true;
        if (!have[p.id]) grid.insertAdjacentHTML("beforeend", card(p));
      });
      Object.keys(have).forEach(function (id) { if (!keep[id]) grid.removeChild(have[id]); });   // hidden since
      [].slice.call(grid.children)
        .sort(function (a, b) { return (b.getAttribute("data-date") || "").localeCompare(a.getAttribute("data-date") || ""); })
        .forEach(function (c) { grid.appendChild(c); });
      apply();
    })
    .catch(function () {});
})();
