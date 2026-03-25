// viewport-fix.js — DPR correction for Playwright MCP (DPR=0.5)
// Applied via <script src="viewport-fix.js"> in all canal-*.html
(function() {
  if (window.devicePixelRatio <= 0.6) {
    // MCP Playwright environment: DPR=0.5, viewport CSS=2160×3840
    // zoom:2 makes the 1080×1920 layout fill the full viewport
    document.documentElement.style.zoom = '2';
  }
})();
