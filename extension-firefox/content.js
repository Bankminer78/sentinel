// Sentinel Firefox content script
(function () {
  if (window.self !== window.top) return;
  const api = (typeof browser !== "undefined") ? browser : chrome;

  function init() {
    try {
      api.runtime.sendMessage(
        { command: "sentinelCheck", url: window.location.href },
        function (response) {
          if (!response) return;
          if (response.verdict === "block" || response.verdict === "warn") {
            showCountdownOverlay(
              response.url || window.location.href,
              response.reason || "Blocked by Sentinel",
              response.category || "blocked"
            );
          }
        }
      );
    } catch (e) {}
  }

  api.runtime.onMessage.addListener(function (request, sender, sendResponse) {
    if (request && request.command === "sentinelOverlay") {
      showCountdownOverlay(request.url, request.reason, request.category);
    }
    sendResponse({ ok: true });
    return true;
  });

  function showCountdownOverlay(url, reason, category) {
    if (document.getElementById("sentinel-overlay")) return;
    if (!document.body) {
      document.addEventListener("DOMContentLoaded", function () {
        showCountdownOverlay(url, reason, category);
      });
      return;
    }

    let secondsLeft = 5;
    let domain = url;
    try { domain = new URL(url).hostname; } catch (e) {}

    const overlay = document.createElement("div");
    overlay.id = "sentinel-overlay";
    overlay.style.cssText =
      "position:fixed;top:0;left:0;right:0;bottom:0;background:rgba(0,0,0,0.9);" +
      "z-index:2147483647;display:flex;align-items:center;justify-content:center;" +
      "font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif;";

    const box = document.createElement("div");
    box.style.cssText =
      "background:#1a0a0a;border:2px solid #dc2626;border-radius:16px;padding:40px;" +
      "max-width:520px;text-align:center;color:#fff;box-shadow:0 25px 50px rgba(0,0,0,0.7);";

    const title = document.createElement("h2");
    title.style.cssText = "margin:0 0 8px 0;font-size:24px;color:#f87171;";
    title.textContent = "Sentinel: " + category;

    const reasonEl = document.createElement("p");
    reasonEl.style.cssText = "margin:0 0 12px 0;font-size:15px;color:#fca5a5;";
    reasonEl.textContent = reason;

    const domainEl = document.createElement("p");
    domainEl.style.cssText = "margin:0 0 24px 0;font-size:14px;color:#a1a1aa;word-break:break-all;";
    domainEl.textContent = domain;

    const countdown = document.createElement("div");
    countdown.style.cssText = "font-size:72px;font-weight:900;margin:0 0 24px 0;color:#dc2626;";
    countdown.textContent = secondsLeft.toString();

    const cancelBtn = document.createElement("button");
    cancelBtn.style.cssText =
      "background:#27272a;border:1px solid #52525b;color:#fff;padding:14px 36px;" +
      "border-radius:8px;font-size:15px;cursor:pointer;font-weight:600;";
    cancelBtn.textContent = "Cancel \u2014 false alarm";

    box.appendChild(title);
    box.appendChild(reasonEl);
    box.appendChild(domainEl);
    box.appendChild(countdown);
    box.appendChild(cancelBtn);
    overlay.appendChild(box);
    document.body.appendChild(overlay);

    const timer = setInterval(function () {
      secondsLeft--;
      if (secondsLeft <= 0) {
        clearInterval(timer);
        try {
          api.runtime.sendMessage({ command: "blockConfirmed", url: url });
        } catch (e) {}
        overlay.remove();
      } else {
        countdown.textContent = secondsLeft.toString();
      }
    }, 1000);

    cancelBtn.addEventListener("click", function () {
      clearInterval(timer);
      try {
        api.runtime.sendMessage({ command: "blockCancelled", url: url });
      } catch (e) {}
      overlay.remove();
    });
  }

  init();
})();
