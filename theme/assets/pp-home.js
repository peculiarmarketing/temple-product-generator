/* Peculiar People homepage sections. Styles: pp-home.css.
   - Garment anatomy (sections/pp-garment-anatomy.liquid): arms the callouts hidden,
     then draws them out once the section scrolls into view. Not armed at all under
     reduced motion, or if this script never runs, so the labels are simply shown.
   - Temple marquee (sections/pp-temple-marquee.liquid): pausing while off screen,
     and keyboard use. The loop itself is a CSS animation, paused on hover.
   - Collection tabs (sections/pp-collection-tabs.liquid): turns the stacked panels
     into tabs. Without this script every panel simply shows, labelled. */
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
    const viewport = section.querySelector('.pp-marquee__viewport');

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

  function initTabs(section) {
    const list = section.querySelector('.pp-tabs__list');
    const tabs = [...section.querySelectorAll('.pp-tabs__tab')];
    const panels = [...section.querySelectorAll('.pp-tabs__panel')];
    if (!list || !tabs.length) return;

    const select = (i, focus) => {
      tabs.forEach((tab, j) => {
        const on = i === j;
        tab.setAttribute('aria-selected', on ? 'true' : 'false');
        tab.tabIndex = on ? 0 : -1;
        if (panels[j]) panels[j].hidden = !on;
      });
      if (focus) tabs[i].focus();
    };

    list.hidden = false;
    section.classList.add('is-tabbed');
    select(Math.max(0, tabs.findIndex((t) => t.getAttribute('aria-selected') === 'true')), false);

    tabs.forEach((tab, i) => tab.addEventListener('click', () => select(i, false)));
    list.addEventListener('keydown', (e) => {
      const i = tabs.indexOf(document.activeElement);
      if (i < 0) return;
      const last = tabs.length - 1;
      const next = { ArrowRight: i === last ? 0 : i + 1, ArrowLeft: i === 0 ? last : i - 1,
                     Home: 0, End: last }[e.key];
      if (next === undefined) return;
      e.preventDefault();
      select(next, true);
    });

    // Theme editor: selecting a tab block shows its panel.
    section.addEventListener('shopify:block:select', (e) => {
      const i = tabs.indexOf(e.target.closest('.pp-tabs__tab'));
      if (i >= 0) select(i, false);
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
    root.querySelectorAll('[data-pp-tabs]:not([data-pp-init])').forEach((s) => {
      s.dataset.ppInit = '1';
      initTabs(s);
    });
  }

  window.PPHome = { init };
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', () => init());
  else init();
  document.addEventListener('shopify:section:load', (e) => init(e.target));
})();
