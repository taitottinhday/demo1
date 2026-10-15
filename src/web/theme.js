// Light/dark theme shared by every page (applicant, account, staff, admin).
// Loaded synchronously in <head> so the saved theme applies before first paint.
// Default is light; the choice is stored in localStorage so all pages and open
// tabs stay in sync.
(() => {
  const KEY = 'x-theme';
  const root = document.documentElement;
  const reduceMotion = window.matchMedia('(prefers-reduced-motion: reduce)');
  const read = () => {
    try { return localStorage.getItem(KEY) === 'dark' ? 'dark' : 'light'; } catch { return 'light'; }
  };
  let toggle = null;

  function apply(theme) {
    root.dataset.theme = theme;
    if (toggle) {
      const dark = theme === 'dark';
      toggle.setAttribute('aria-checked', String(dark));
      toggle.title = dark ? 'Chuyển sang giao diện sáng' : 'Chuyển sang giao diện tối';
    }
  }

  function choose(theme) {
    try { localStorage.setItem(KEY, theme); } catch { /* storage blocked: still switch for this page */ }
    if (theme === root.dataset.theme) return;
    if (reduceMotion.matches) { apply(theme); return; }
    if (document.startViewTransition && toggle) {
      // Circular reveal from the switch.
      const rect = toggle.getBoundingClientRect();
      const x = rect.left + rect.width / 2;
      const y = rect.top + rect.height / 2;
      const radius = Math.hypot(Math.max(x, innerWidth - x), Math.max(y, innerHeight - y));
      const transition = document.startViewTransition(() => apply(theme));
      transition.ready.then(() => {
        root.animate(
          { clipPath: [`circle(0px at ${x}px ${y}px)`, `circle(${radius}px at ${x}px ${y}px)`] },
          { duration: 600, easing: 'cubic-bezier(.22,1,.36,1)', pseudoElement: '::view-transition-new(root)' }
        );
      }).catch(() => {});
      return;
    }
    root.classList.add('theme-animating');
    apply(theme);
    setTimeout(() => root.classList.remove('theme-animating'), 450);
  }

  apply(read());
  window.addEventListener('storage', event => { if (event.key === KEY) apply(read()); });

  function mount() {
    const nav = document.querySelector('.topbar nav');
    if (!nav || nav.querySelector('.theme-switch')) return;
    toggle = document.createElement('button');
    toggle.type = 'button';
    toggle.className = 'theme-switch';
    toggle.setAttribute('role', 'switch');
    toggle.setAttribute('aria-label', 'Giao diện tối');
    toggle.innerHTML = `<span class="theme-track" aria-hidden="true">
        <svg class="theme-sun" viewBox="0 0 24 24"><circle cx="12" cy="12" r="4"/><path d="M12 2.5v2M12 19.5v2M4.6 4.6l1.4 1.4M18 18l1.4 1.4M2.5 12h2M19.5 12h2M4.6 19.4 6 18M18 6l1.4-1.4"/></svg>
        <svg class="theme-moon" viewBox="0 0 24 24"><path d="M20 14.5A8.5 8.5 0 0 1 9.5 4a8.5 8.5 0 1 0 10.5 10.5Z"/></svg>
        <span class="theme-knob"></span>
      </span>`;
    toggle.addEventListener('click', () => choose(root.dataset.theme === 'dark' ? 'light' : 'dark'));
    const slot = nav.querySelector('[data-theme-slot]');
    if (slot) slot.replaceWith(toggle); else nav.prepend(toggle);
    apply(read());
  }

  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', mount);
  else mount();
})();
