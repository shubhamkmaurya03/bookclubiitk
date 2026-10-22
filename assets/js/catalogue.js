/* Card catalogue: loads data/catalogue.json and searches it in the browser. */
(function () {
  var PAGE = 30;
  var COVER_COLOURS = ["#7d1f2c", "#2f4b3c", "#23395b", "#6b4a1f", "#4a2c4f", "#5c3a2e", "#1f4a4a", "#3b3b3b", "#8a5a2b", "#46523a"];
  var SORTS = ["best", "new", "popular", "rating", "title"];

  var $ = function (s) { return document.querySelector(s); };
  var form = $("#cat-form"), qEl = $("#q"), byEl = $("#by"), sortEl = $("#sort");
  var grid = $("#books"), countEl = $("#count"), moreBtn = $("#more"), chipsEl = $("#chips");
  var availWrap = $("#avail-wrap"), availEl = $("#avail"), surpriseBtn = $("#surprise");

  var books = [], results = [], shown = 0, genre = "", wantSort = "best", wantSurprise = false;
  var shelfUrl = grid.getAttribute("data-shelf"), shelf = null;

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
    wantSort = SORTS.indexOf(p.get("sort")) !== -1 ? p.get("sort") : "best";
    sortEl.value = wantSort;
    availEl.checked = p.get("avail") === "1";
    wantSurprise = p.get("surprise") === "1";
    genre = p.get("genre") || "";
  }
  function writeURL() {
    var p = new URLSearchParams();
    if (qEl.value.trim()) p.set("q", qEl.value.trim());
    if (byEl.value !== "all") p.set("by", byEl.value);
    if (genre) p.set("genre", genre);
    if (sortEl.value !== "best") p.set("sort", sortEl.value);
    if (availOnly()) p.set("avail", "1");
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
        esc(g) + '</button>';
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
  function availOnly() { return !!shelf && availEl.checked; }
  function borrowed(b) {
    var n = 0;
    if (shelf && shelf.popular && Array.isArray(b.k)) b.k.forEach(function (k) { n += shelf.popular[k] || 0; });
    return n;
  }
  function filtered(terms) {
    var by = byEl.value, onlyAvail = availOnly();
    return books.filter(function (b) {
      if (genre && b.g !== genre) return false;
      if (onlyAvail && !onShelf(b)) return false;
      if (!terms.length) return true;
      var hay = by === "title" ? b._t : by === "author" ? b._a : by === "genre" ? b._g : b._t + " " + b._a + " " + b._g;
      for (var i = 0; i < terms.length; i++) if (hay.indexOf(terms[i]) === -1) return false;
      return true;
    });
  }
  function run() {
    var terms = norm(qEl.value).split(/\s+/).filter(Boolean);
    results = filtered(terms);
    var sort = sortEl.value;
    if (sort === "rating") {
      results = results.slice().sort(function (a, b) { return (b.r || 0) - (a.r || 0); });
    } else if (sort === "new") {
      results = results.slice().sort(function (a, b) {
        return (b.ad || "").localeCompare(a.ad || "") || Math.max.apply(null, b.k || [0]) - Math.max.apply(null, a.k || [0]);
      });
    } else if (sort === "popular") {
      results = results.map(function (b, i) { return { b: b, n: borrowed(b), i: i }; })
        .sort(function (x, y) { return y.n - x.n || x.i - y.i; }).map(function (x) { return x.b; });
    } else if (sort === "best") {
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

    // Counts are shown only for word searches, not for the whole collection or a genre.
    var notes = [];
    if (availOnly()) notes.push("on the shelf now");
    if (sort === "new") notes.push("newest arrivals first");
    if (sort === "popular") notes.push("most borrowed this semester first");
    var where = genre ? ' in <b>' + esc(genre) + '</b>' : "";
    var head = terms.length
      ? '<b>' + results.length.toLocaleString("en-IN") + '</b> ' + (results.length === 1 ? "book" : "books") +
        ' for “<b>' + esc(qEl.value.trim()) + '</b>”' + where
      : genre ? 'Books in <b>' + esc(genre) + '</b>' : notes.length ? "All books" : "";
    countEl.innerHTML = results.length && head ? head + (notes.length ? ", " + notes.join(", ") : "") : "";
    if (!results.length) {
      grid.innerHTML = availOnly()
        ? '<div class="empty"><b>Every copy is out right now.</b>Untick <i>On the shelf now</i> to see all of them, ' +
          'or check again in a few days.</div>'
        : '<div class="empty"><b>Not on our shelves… yet.</b>' +
          'Try a different spelling, or <a href="request.html">request the book</a> and we will do our best to procure it.</div>';
    }
  }

  /* ---- surprise me: one random book from the current genre / search, preferring ones on the shelf ---- */
  function surprise() {
    var terms = norm(qEl.value).split(/\s+/).filter(Boolean);
    var pool = filtered(terms);
    if (shelf) {
      var free = pool.filter(onShelf);
      if (free.length) pool = free;
    }
    if (!pool.length) { run(); return; }
    var pick = pool[Math.floor(Math.random() * pool.length)];
    markChips();
    writeURL();
    grid.innerHTML = card(pick);
    moreBtn.hidden = true;
    countEl.innerHTML = 'A surprise pick' + (genre ? ' from <b>' + esc(genre) + '</b>' : "") +
      ' · <button type="button" class="linkish" id="again">pick another</button>' +
      ' · <button type="button" class="linkish" id="showall">show all</button>';
  }
  countEl.addEventListener("click", function (e) {
    if (e.target.id === "again") surprise();
    if (e.target.id === "showall") run();
  });

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
    if (b.r) h += '<span class="rating" title="Goodreads rating"><span class="stars" style="--pct:' + Math.min(100, b.r * 20) + '%" aria-hidden="true"></span>' + b.r.toFixed(1) + '<span class="sr"> out of 5</span> <span class="src">Goodreads</span></span>';
    if (b.g) h += '<span class="tag">' + esc(b.g) + '</span>';
    h += avail(b);
    h += '</div></div></article>';
    return h;
  }

  /* ---- live shelf status ----
     The club computer publishes, for each Koha record with a copy out, [copies, issued, earliest due date],
     and the titles borrowed most this semester. Catalogue entries list their Koha record numbers in b.k. */
  function validShelf(d) {
    if (!d || d.v !== 1 || !d.out || typeof d.out !== "object") return null;
    var out = {}, count = function (n) { return typeof n === "number" && n >= 0 && n < 1e4 && n % 1 === 0; };
    Object.keys(d.out).forEach(function (k) {
      var v = d.out[k];
      if (/^\d{1,9}$/.test(k) && Array.isArray(v) && v.length === 3 && count(v[0]) && count(v[1]) && v[1] <= v[0] &&
          typeof v[2] === "string" && /^(\d{4}-\d\d-\d\d)?$/.test(v[2])) out[k] = v;
    });
    var popular = null, top = d.popular && Array.isArray(d.popular.top) ? d.popular.top : [];
    top.forEach(function (v) {
      if (Array.isArray(v) && v.length === 2 && count(v[0]) && count(v[1]) && v[1] > 0) {
        popular = popular || {};
        popular[v[0]] = v[1];
      }
    });
    var t = typeof d.updated === "string" ? new Date(d.updated) : null;
    return { out: out, popular: popular, updated: t && !isNaN(t) ? t : null };
  }
  function loadShelf() {
    if (!shelfUrl) return Promise.resolve(null);
    var req = fetch(shelfUrl + (shelfUrl.indexOf("?") === -1 ? "?" : "&") + "t=" + Date.now(),
                    { cache: "no-store", credentials: "omit", referrerPolicy: "no-referrer" })
      .then(function (r) { return r.ok ? r.json() : null; })
      .then(validShelf)
      .catch(function () { return null; });
    return Promise.race([req, new Promise(function (done) { setTimeout(done, 5000, null); })]);
  }
  function istDate(d) {   // YYYY-MM-DD in Indian time
    return new Date(d.getTime() + 5.5 * 3600e3).toISOString().slice(0, 10);
  }
  function shortDate(ymd) {
    return new Date(ymd + "T12:00:00+05:30").toLocaleDateString("en-IN", { day: "numeric", month: "short", timeZone: "Asia/Kolkata" });
  }
  /* {copies, issued, due, allKnown} from the live status, or null when unknown */
  function shelfState(b) {
    if (!shelf || !Array.isArray(b.k) || !b.k.length) return null;
    var copies = 0, issued = 0, due = "", allKnown = true;
    b.k.forEach(function (k) {
      var v = shelf.out[k];
      if (!v) { allKnown = false; return; }                                      // no copy of it out
      copies += v[0]; issued += v[1];
      if (v[2] && (!due || v[2] < due)) due = v[2];
    });
    if (typeof b.n === "number" && b.n >= copies) { copies = b.n; allKnown = true; }   // total copies from the catalogue
    return { copies: copies, issued: issued, due: due, allKnown: allKnown };
  }
  function onShelf(b) {
    var s = shelfState(b);
    return !!s && (!s.issued || !(s.allKnown && s.issued >= s.copies));
  }
  function avail(b) {
    var on = '<span class="avail">On the shelf</span>';
    if (!shelfUrl) return b.o ? '<span class="avail out">Issued</span>' : on;   // live status not set up
    var s = shelfState(b);
    if (!s) return "";                                                          // unknown: say nothing
    if (!s.issued) return on;
    if (s.allKnown && s.issued >= s.copies) {
      var when = s.due && s.due >= istDate(new Date()) ? " · due " + shortDate(s.due) : "";
      return '<span class="avail out">Issued' + esc(when) + '</span>';
    }
    return s.allKnown && s.copies > 1
      ? '<span class="avail">' + (s.copies - s.issued) + ' of ' + s.copies + ' on the shelf</span>'
      : on;
  }
  function showShelfNote() {
    var note = $("#shelf-note");
    if (!shelfUrl || !note) return;
    if (shelf) {
      note.textContent = "Live shelf status" + (shelf.updated ? ", last change " + shelf.updated.toLocaleString("en-IN",
        { day: "numeric", month: "short", hour: "numeric", minute: "2-digit", timeZone: "Asia/Kolkata" }) : "");
      note.className = "shelf-note";
    } else {
      note.textContent = "Shelf status could not be loaded just now.";
      note.className = "shelf-note off";
    }
    note.hidden = false;
  }
  /* Options that need live data appear only when it has loaded. */
  function setupShelfControls() {
    availWrap.hidden = !shelf;
    if (!shelf) availEl.checked = false;
    var popOpt = sortEl.querySelector('option[value="popular"]');
    if (!(shelf && shelf.popular)) {
      popOpt.remove();
      if (wantSort === "popular") wantSort = "best";
    }
    sortEl.value = wantSort;
  }

  function renderMore() {
    var next = results.slice(shown, shown + PAGE);
    grid.insertAdjacentHTML("beforeend", next.map(card).join(""));
    shown += next.length;
    moreBtn.hidden = shown >= results.length;
    moreBtn.textContent = "Show more books";
  }

  /* broken cover links fall back to a typeset cover */
  grid.addEventListener("error", function (e) {
    var img = e.target;
    if (img.tagName === "IMG" && img.dataset.fallback) img.outerHTML = img.dataset.fallback;
  }, true);

  /* ---- wire up ---- */
  readURL();
  var timer, ready = false;
  qEl.addEventListener("input", function () { clearTimeout(timer); timer = setTimeout(run, 180); });
  byEl.addEventListener("change", run);
  sortEl.addEventListener("change", run);
  availEl.addEventListener("change", run);
  surpriseBtn.addEventListener("click", function () { if (ready) surprise(); });
  form.addEventListener("submit", function (e) { e.preventDefault(); clearTimeout(timer); run(); });
  moreBtn.addEventListener("click", renderMore);

  var shelfReady = loadShelf();
  fetch("data/catalogue.json")
    .then(function (r) { if (!r.ok) throw new Error(r.status); return r.json(); })
    .then(function (data) { return shelfReady.then(function (s) { shelf = s; return data; }); })
    .then(function (data) {
      books = data;
      showShelfNote();
      setupShelfControls();
      books.forEach(function (b) {
        b.t = b.t || ""; b.a = b.a || "";
        b._t = norm(b.t); b._a = norm(b.a); b._g = norm(b.g);
      });
      buildChips();
      ready = true;
      if (wantSurprise) surprise(); else run();
    })
    .catch(function () {
      grid.innerHTML = '<div class="empty"><b>The card drawer is stuck.</b>We could not load the catalogue just now. Please refresh the page in a moment.</div>';
    });
})();
