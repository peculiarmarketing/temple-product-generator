/* Peculiar People homepage sections. Styles: pp-home.css.
   - Garment anatomy (sections/pp-garment-anatomy.liquid): arms the callouts hidden,
     then draws them out once the section scrolls into view. Not armed at all under
     reduced motion, or if this script never runs, so the labels are simply shown.
   - Temple marquee (sections/pp-temple-marquee.liquid): the pause button, pausing
     while off screen, and keyboard use. The loop itself is a CSS animation. */
(() => {
  if (window.PPHome) return;

  const reducedQuery = window.matchMedia('(prefers-reduced-motion: reduce)');
  const reduced = () => reducedQuery.matches;

  function initAnatomy(section) {
    if (reduced() || !('IntersectionObserver' in window)) return;
    section.classList.add('is-armed');
    const io = new IntersectionObserver((entries) => {
      if (!entries.some((e) => e.isIntersecting)) return;
      section.classList.add('is-in');
      io.disconnect();
    }, { threshold: 0.2 });
    io.observe(section.querySelector('.pp-anatomy__stage') || section);
  }

  function initMarquee(section) {
    const toggle = section.querySelector('[data-pp-marquee-toggle]');
    const toggleText = section.querySelector('[data-pp-marquee-toggle-text]');
    const viewport = section.querySelector('.pp-marquee__viewport');

    // WCAG 2.2.2: anything that moves on its own for more than five seconds needs a
    // way to stop it. Hover and focus already pause; the button makes it stick.
    const showToggle = () => { if (toggle) toggle.hidden = reduced(); };
    showToggle();
    reducedQuery.addEventListener?.('change', showToggle);
    if (toggle) {
      toggle.addEventListener('click', () => {
        const paused = section.classList.toggle('is-paused');
        toggleText.textContent = paused ? toggle.dataset.playLabel : toggle.dataset.pauseLabel;
      });
    }

    // No point animating what nobody can see.
    if ('IntersectionObserver' in window) {
      new IntersectionObserver((entries) => entries.forEach((e) => {
        section.classList.toggle('is-offscreen', !e.isIntersecting);
      })).observe(section);
    }

    // A tile reached by Tab may sit anywhere along the moving row, or off screen.
    // Stop the loop, let the row scroll, and bring the tile into view; the loop picks
    // up again from the start once focus leaves the marquee.
    section.addEventListener('focusin', (e) => {
      const tile = e.target.closest('.pp-marquee__tile');
      if (!tile) return;
      section.classList.add('is-manual');
      tile.scrollIntoView({ block: 'nearest', inline: 'center' });
    });
    section.addEventListener('focusout', (e) => {
      if (section.contains(e.relatedTarget)) return;
      section.classList.remove('is-manual');
      viewport.scrollLeft = 0;
    });
  }

  function init(root = document) {
    root.querySelectorAll('[data-pp-anatomy]:not([data-pp-init])').forEach((s) => {
      s.dataset.ppInit = '1';
      initAnatomy(s);
    });
    root.querySelectorAll('[data-pp-marquee]:not([data-pp-init])').forEach((s) => {
      s.dataset.ppInit = '1';
      initMarquee(s);
    });
  }

  window.PPHome = { init };
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', () => init());
  else init();
  document.addEventListener('shopify:section:load', (e) => init(e.target));
})();
