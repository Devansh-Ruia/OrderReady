"""Small, decorative introduction with a local GSAP core and static fallback."""

from pathlib import Path

import streamlit.components.v2 as components


_ASSETS = Path(__file__).with_name("assets")
_HTML = """
<div class="intro" aria-hidden="true">
  <svg width="280" height="128" viewBox="0 0 280 128" fill="none"
       xmlns="http://www.w3.org/2000/svg" focusable="false">
    <g class="inquiry">
      <rect x="2" y="22" width="78" height="86" rx="8" fill="#FFFFFF" stroke="#C8BFB3"/>
      <rect x="14" y="36" width="22" height="6" rx="3" fill="#B6491D"/>
      <path d="M14 54H67M14 65H61M14 76H65M14 87H43" stroke="#9C9286" stroke-width="3" stroke-linecap="round"/>
    </g>
    <g class="connector" stroke="#B6491D" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
      <path d="M88 65H103M98 60L103 65L98 70"/>
    </g>
    <g class="ticket">
      <path d="M119 14H167L182 29V112H113V20C113 16.7 115.7 14 119 14Z" fill="#FFFFFF" stroke="#C8BFB3"/>
      <path d="M167 14V29H182" fill="#E9E2D8" stroke="#C8BFB3" stroke-linejoin="round"/>
      <rect x="125" y="39" width="44" height="6" rx="3" fill="#B6491D"/>
      <path d="M125 58H168M125 69H163M125 80H151" stroke="#9C9286" stroke-width="3" stroke-linecap="round"/>
      <path d="M126 95L131 100L140 90" stroke="#B6491D" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"/>
    </g>
    <g class="shirt">
      <path d="M214 36L199 45L191 63L205 71L211 62V106H258V62L264 71L278 63L270 45L255 36C252 43 245 47 235 47C225 47 218 43 214 36Z"
            fill="#E9E2D8" stroke="#25231F" stroke-width="2" stroke-linejoin="round"/>
      <path d="M223 68H247V86H223Z" fill="#B6491D"/>
      <path d="M229 76L233 80L242 72" stroke="#FFFFFF" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>
    </g>
  </svg>
</div>
"""

_CSS = """
:host { display: block; }
.intro { width: 280px; height: 128px; overflow: hidden; }
svg { display: block; width: 280px; height: 128px; }
"""

_JS_TEMPLATE = """
export default function(component) {
  const root = component.parentElement;
  const nodes = Array.from(root.querySelectorAll('svg > g'));
  const playedKey = 'orderready.intro.played';
  let context = null;
  let gsap = null;
  let motion = null;
  const finalFrame = () => {
    if (context) { context.revert(); context = null; }
    nodes.forEach(node => {
      node.removeAttribute('style');
      node.removeAttribute('transform');
      node.removeAttribute('data-svg-origin');
    });
    if (gsap) gsap.ticker.sleep();
  };
  const motionChanged = event => { if (event.matches) finalFrame(); };
  const cleanup = () => {
    if (motion) motion.removeEventListener('change', motionChanged);
    finalFrame();
  };
  try {
    motion = globalThis.matchMedia('(prefers-reduced-motion: reduce)');
    if (motion.matches || globalThis.sessionStorage.getItem(playedKey) === '1') {
      return cleanup;
    }
    // The bundled UMD exports and its browser bookkeeping remain local.
    const loadGsap = () => {
      const exports = {};
      const module = { exports };
      const window = { document: globalThis.document, gsap: {}, gsapVersions: [] };
      __GSAP_CORE__
      return exports.gsap;
    };
    gsap = loadGsap();
    if (!gsap || gsap.version !== '3.13.0') return cleanup;
    globalThis.sessionStorage.setItem(playedKey, '1');
    motion.addEventListener('change', motionChanged);
    context = gsap.context(() => {});
    context.add(() => {
      const timeline = gsap.timeline({ onComplete: () => gsap.ticker.sleep() });
      timeline.fromTo(root.querySelector('.inquiry'),
        { x: -20, y: 12, opacity: 0 },
        { x: 0, y: 0, opacity: 1, duration: 0.75, ease: 'power2.out' }, 0);
      timeline.fromTo(root.querySelector('.ticket'),
        { x: 12, y: -6, opacity: 0 },
        { x: 0, y: 0, opacity: 1, duration: 0.75, ease: 'power2.out' }, 0);
      timeline.fromTo(root.querySelector('.shirt'),
        { x: 18, y: 10, opacity: 0 },
        { x: 0, y: 0, opacity: 1, duration: 0.75, ease: 'power2.out' }, 0);
      timeline.fromTo(root.querySelector('.connector'),
        { opacity: 0 }, { opacity: 1, duration: 0.35 }, 0.4);
    });
  } catch (_) {
    // The markup is the final illustration even when initialization fails.
    cleanup();
  }
  return cleanup;
}
"""

_JS = _JS_TEMPLATE.replace(
    "__GSAP_CORE__", (_ASSETS / "gsap-3.13.0.min.js").read_text(encoding="utf-8")
)


def render_intro() -> None:
    """Register with the current runtime, then mount the trusted illustration."""
    intro = components.component(
        "orderready_intro",
        html=_HTML,
        css=_CSS,
        js=_JS,
        isolate_styles=True,
    )
    intro(key="orderready_intro", width=280, height=128)
