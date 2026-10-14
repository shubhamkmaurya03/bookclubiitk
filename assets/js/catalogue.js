/* Card catalogue: loads data/catalogue.json and searches it in the browser. */
(function () {
  var PAGE = 30;
  var COVER_COLOURS = ["#7d1f2c", "#2f4b3c", "#23395b", "#6b4a1f", "#4a2c4f", "#5c3a2e", "#1f4a4a", "#3b3b3b", "#8a5a2b", "#46523a"];

  var $ = function (s) { return document.querySelector(s); };
  var form = $("#cat-form"), qEl = $("#q"), byEl = $("#by"), sortEl = $("#sort");
  var grid = $("#books"), countEl = $("#count"), moreBtn = $("#more"), chipsEl = $("#chips");

  var books = [], results = [], shown = 0, genre = "";

  function esc(s) {
    return String(s).replace(/[&<>"']/g, function (c) {
      return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c];
    });
  }
  function norm(s) {
    return (s || "").toLowerCase().normalize("NFD").replace(/[̀-ͯ]/g, "");
  }
  function hash(s) {
    var h = 0;
    for (var i = 0; i < s.length; i++) h = (h * 31 + s.charCodeAt(i)) | 0;
    return Math.abs(h);
  }

  /* ---- URL state ---- */
  function readURL() {
    var p = new URLSearchParams(location.search);
    qEl.value = p.get("q") || "";
    byEl.value = ["title", "author", "genre"].indexOf(p.get("by")) !== -1 ? p.get("by") : "all";
    sortEl.value = ["rating", "title"].indexOf(p.get("sort")) !== -1 ? p.get("sort") : "best";
    genre = p.get("genre") || "";
  }
  function writeURL() {
    var p = new URLSearchParams();
    if (qEl.value.trim()) p.set("q", qEl.value.trim());
    if (byEl.value !== "all") p.set("by", byEl.value);
    if (genre) p.set("genre", genre);
    if (sortEl.value !== "best") p.set("sort", sortEl.value);
    var qs = p.toString();
    history.replaceState(null, "", location.pathname + (qs ? "?" + qs : ""));
  }

  /* ---- genre chips ---- */
  function buildChips() {
    var counts = {};
    books.forEach(function (b) { if (b.g) counts[b.g] = (counts[b.g] || 0) + 1; });
    var list = Object.keys(counts).sort(function (a, b) { return counts[b] - counts[a]; });
    var html = '<button type="button" class="chip" data-g="">All genres</button>';
    list.forEach(function (g, i) {
      html += '<button type="button" class="chip' + (i >= 12 ? ' extra' : '') + '" data-g="' + esc(g) + '">' +
        esc(g) + '<small>' + counts[g] + '</small></button>';
    });
    html += '<button type="button" class="chips-toggle" aria-expanded="false">more genres</button>';
    chipsEl.innerHTML = html;

    var toggle = chipsEl.querySelector(".chips-toggle");
    function setExtras(show) {
      chipsEl.querySelectorAll(".extra").forEach(function (c) {
        c.hidden = !show && c.getAttribute("data-g") !== genre;
      });
      toggle.textContent = show ? "fewer genres" : "more genres";
      toggle.setAttribute("aria-expanded", show ? "true" : "false");
    }
    setExtras(false);
    toggle.addEventListener("click", function () { setExtras(toggle.getAttribute("aria-expanded") !== "true"); });

    chipsEl.addEventListener("click", function (e) {
      var c = e.target.closest(".chip");
      if (!c) return;
      genre = c.getAttribute("data-g");
      run();
    });
  }
  function markChips() {
    chipsEl.querySelectorAll(".chip").forEach(function (c) {
      c.setAttribute("aria-pressed", c.getAttribute("data-g") === genre ? "true" : "false");
    });
  }

  /* ---- search ---- */
  function run() {
    var terms = norm(qEl.value).split(/\s+/).filter(Boolean);
    var by = byEl.value;
    results = books.filter(function (b) {
      if (genre && b.g !== genre) return false;
      if (!terms.length) return true;
      var hay = by === "title" ? b._t : by === "author" ? b._a : by === "genre" ? b._g : b._t + " " + b._a + " " + b._g;
      for (var i = 0; i < terms.length; i++) if (hay.indexOf(terms[i]) === -1) return false;
      return true;
    });
    if (sortEl.value === "rating") {
      results = results.slice().sort(function (a, b) { return (b.r || 0) - (a.r || 0); });
    } else if (sortEl.value === "best") {
      var first = terms[0] || "";
      results = results.map(function (b, i) {
        var s = 0;
        if (first) {
          if (b._t.indexOf(norm(qEl.value.trim())) === 0) s += 40;
          else if (b._t.indexOf(first) !== -1) s += 20;
          if (b._a.indexOf(first) !== -1) s += 12;
        }
        if (b.i) s += 6;
        if (b.d) s += 4;
        s += (b.r || 0);
        return { b: b, s: s, i: i };
      }).sort(function (x, y) { return y.s - x.s || x.i - y.i; }).map(function (x) { return x.b; });
    }
    markChips();
    writeURL();
    grid.innerHTML = "";
    shown = 0;
    renderMore();

    var n = results.length.toLocaleString("en-IN");
    var what = terms.length ? ' for “<b>' + esc(qEl.value.trim()) + '</b>”' : "";
    var where = genre ? ' in <b>' + esc(genre) + '</b>' : "";
    countEl.innerHTML = results.length
      ? '<b>' + n + '</b> ' + (results.length === 1 ? "book" : "books") + what + where
      : "";
    if (!results.length) {
      grid.innerHTML = '<div class="empty"><b>Not on our shelves… yet.</b>' +
        'Try a different spelling, or <a href="request.html">request the book</a> and we will do our best to procure it.</div>';
    }
  }

  function cover(b) {
    var colour = COVER_COLOURS[hash(b.t + b.a) % COVER_COLOURS.length];
    var made = '<div class="made-cover" style="background:' + colour + '">' + esc(b.t.length > 60 ? b.t.slice(0, 57) + "…" : b.t) + '</div>';
    if (!b.i) return made;
    return '<img src="' + esc(b.i) + '" alt="" loading="lazy" referrerpolicy="no-referrer" data-fallback="' + esc(made) + '">';
  }

  function card(b) {
    var h = '<article class="book"><div class="cover">' + cover(b) + '</div><div class="book-body">';
    h += '<h3>' + esc(b.t) + '</h3>';
    if (b.a) h += '<div class="author">' + esc(b.a) + '</div>';
    if (b.d) h += '<details><summary>About this book</summary><p>' + esc(b.d) + '</p>' +
      (b.ds ? '<p class="via">Description via ' + esc(b.ds) + '</p>' : '') + '</details>';
    h += '<div class="book-tags">';
    if (b.r) h += '<span class="rating"><span class="stars" style="--pct:' + Math.min(100, b.r * 20) + '%" aria-hidden="true"></span>' + b.r.toFixed(1) + '<span class="sr"> out of 5</span></span>';
    if (b.g) h += '<span class="tag">' + esc(b.g) + '</span>';
    h += b.o ? '<span class="avail out">Issued</span>' : '<span class="avail">On the shelf</span>';
    h += '</div></div></article>';
    return h;
  }

  function renderMore() {
    var next = results.slice(shown, shown + PAGE);
    grid.insertAdjacentHTML("beforeend", next.map(card).join(""));
    shown += next.length;
    moreBtn.hidden = shown >= results.length;
    moreBtn.textContent = "Show more books (" + (results.length - shown).toLocaleString("en-IN") + " left)";
  }

  /* broken cover links fall back to a typeset cover */
  grid.addEventListener("error", function (e) {
    var img = e.target;
    if (img.tagName === "IMG" && img.dataset.fallback) img.outerHTML = img.dataset.fallback;
  }, true);

  /* ---- wire up ---- */
  readURL();
  var timer;
  qEl.addEventListener("input", function () { clearTimeout(timer); timer = setTimeout(run, 180); });
  byEl.addEventListener("change", run);
  sortEl.addEventListener("change", run);
  form.addEventListener("submit", function (e) { e.preventDefault(); clearTimeout(timer); run(); });
  moreBtn.addEventListener("click", renderMore);

  fetch("data/catalogue.json")
    .then(function (r) { if (!r.ok) throw new Error(r.status); return r.json(); })
    .then(function (data) {
      books = data;
      books.forEach(function (b) {
        b.t = b.t || ""; b.a = b.a || "";
        b._t = norm(b.t); b._a = norm(b.a); b._g = norm(b.g);
      });
      buildChips();
      run();
    })
    .catch(function () {
      grid.innerHTML = '<div class="empty"><b>The card drawer is stuck.</b>We could not load the catalogue just now. Please refresh the page in a moment.</div>';
    });
})();
