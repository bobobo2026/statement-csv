(function () {
  const cfg = window.__PADDLE__ || {};
  let initialized = false;

  function init() {
    if (!cfg.token || typeof Paddle === "undefined") return false;
    try {
      if (cfg.env === "sandbox") {
        Paddle.Environment.set("sandbox");
      }
      Paddle.Initialize({ token: cfg.token });
      initialized = true;
      return true;
    } catch (e) {
      console.error("Paddle init failed", e);
      return false;
    }
  }

  function openCheckout(priceId) {
    if (!priceId) {
      alert("This pack has no Paddle price ID yet. Seller setup incomplete.");
      return;
    }
    if (!initialized && !init()) {
      alert("Paddle is not configured (missing client-side token).");
      return;
    }
    Paddle.Checkout.open({
      items: [{ priceId: priceId, quantity: 1 }],
    });
  }

  document.querySelectorAll(".paddle-buy").forEach(function (btn) {
    btn.addEventListener("click", function () {
      openCheckout(btn.getAttribute("data-price-id"));
    });
  });

  if (cfg.token) init();
})();
