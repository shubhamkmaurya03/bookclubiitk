/* Book Club IIT Kanpur — shared behaviour (no dependencies) */
(function () {
  var root = document.documentElement;
  root.classList.add("js");

  /* ---- theme toggle (initial theme is set inline in <head>) ---- */
  var toggle = document.querySelector(".theme-toggle");
  if (toggle) {
    toggle.addEventListener("click", function () {
      var current = root.getAttribute("data-theme") || "light";
      var next = current === "dark" ? "light" : "dark";
      root.setAttribute("data-theme", next);
      try { localStorage.setItem("bc-theme", next); } catch (e) {}
    });
  }

  /* ---- mobile menu ---- */
  var nav = document.querySelector(".nav");
  var menuBtn = document.querySelector(".menu-toggle");
  if (nav && menuBtn) {
    menuBtn.addEventListener("click", function () {
      var open = nav.classList.toggle("open");
      menuBtn.setAttribute("aria-expanded", open ? "true" : "false");
    });
    document.addEventListener("keydown", function (e) {
      if (e.key === "Escape" && nav.classList.contains("open")) {
        nav.classList.remove("open");
        menuBtn.setAttribute("aria-expanded", "false");
        menuBtn.focus();
      }
    });
  }

  /* ---- tabs (team page) ---- */
  document.querySelectorAll("[role='tablist']").forEach(function (list) {
    var tabs = Array.prototype.slice.call(list.querySelectorAll("[role='tab']"));
    function select(tab) {
      tabs.forEach(function (t) {
        var on = t === tab;
        t.setAttribute("aria-selected", on ? "true" : "false");
        t.tabIndex = on ? 0 : -1;
        document.getElementById(t.getAttribute("aria-controls")).hidden = !on;
      });
    }
    tabs.forEach(function (tab, i) {
      tab.addEventListener("click", function () { select(tab); });
      tab.addEventListener("keydown", function (e) {
        var j = e.key === "ArrowRight" ? i + 1 : e.key === "ArrowLeft" ? i - 1 : null;
        if (j === null) return;
        var t = tabs[(j + tabs.length) % tabs.length];
        select(t); t.focus();
      });
    });
    var initial = tabs.filter(function (t) { return location.hash === "#" + t.getAttribute("aria-controls"); })[0];
    select(initial || tabs[0]);
  });

  /* ---- gentle reveal on scroll ---- */
  var items = document.querySelectorAll(".reveal");
  if ("IntersectionObserver" in window) {
    var io = new IntersectionObserver(function (entries) {
      entries.forEach(function (en) {
        if (en.isIntersecting) { en.target.classList.add("in"); io.unobserve(en.target); }
      });
    }, { rootMargin: "0px 0px -8% 0px" });
    items.forEach(function (el) { io.observe(el); });
  } else {
    items.forEach(function (el) { el.classList.add("in"); });
  }

  /* ---- forms: send in the background and confirm on the page (without JS they post normally) ---- */
  document.querySelectorAll("form[data-ajax-form]").forEach(function (form) {
    var status = form.querySelector(".form-status");
    var button = form.querySelector("button[type='submit']");
    function say(text, ok) {
      status.textContent = text;
      status.className = "form-status " + (ok ? "ok" : "err");
      status.hidden = false;
    }
    form.addEventListener("submit", function (e) {
      if (!window.fetch || !window.FormData) return;
      e.preventDefault();
      button.disabled = true;
      say("Sending…", true);
      fetch(form.action, { method: "POST", body: new FormData(form), headers: { Accept: "application/json" } })
        .then(function (r) { return r.json().catch(function () { return {}; }); })
        .then(function (res) {
          if (!res.success) throw new Error(res.message || "failed");
          form.reset();
          say("Thank you! Your message has reached the Book Club. We will get back to you soon.", true);
        })
        .catch(function () {
          say("Sorry, that didn’t go through. Please try again in a moment, or write to us at bookclub@iitk.ac.in.", false);
        })
        .then(function () { button.disabled = false; });
    });
  });

  /* ---- footer year ---- */
  var y = document.querySelector("[data-year]");
  if (y) y.textContent = new Date().getFullYear();
})();
