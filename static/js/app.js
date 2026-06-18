function copyToClipboard(text, btn) {
  navigator.clipboard.writeText(text).then(() => {
    const original = btn.textContent;
    btn.textContent = 'Copied!';
    btn.classList.add('btn-gold');
    setTimeout(() => {
      btn.textContent = original;
      btn.classList.remove('btn-gold');
    }, 2000);
  });
}

document.addEventListener('DOMContentLoaded', () => {
  const path = window.location.pathname;
  document.querySelectorAll('.nav-links a').forEach(link => {
    const href = link.getAttribute('href');
    if (href === path || (href !== '/' && path.startsWith(href))) {
      link.classList.add('active');
    }
  });

  const heroForm = document.getElementById('hero-search');
  if (heroForm) {
    const tabs = heroForm.querySelectorAll('.search-tab');
    const input = heroForm.querySelector('input[name="q"]');
    let activeType = 'judgments';

    tabs.forEach(tab => {
      tab.addEventListener('click', () => {
        tabs.forEach(t => t.classList.remove('active'));
        tab.classList.add('active');
        activeType = tab.dataset.type;
        const placeholders = {
          judgments: 'Search judgments by case name, citation, or keywords...',
          citations: 'Enter citation e.g. (1973) 4 SCC 225...',
          proformas: 'Search legal proformas and templates...',
          guides: 'Search filing guides by state or case type...'
        };
        input.placeholder = placeholders[activeType];
      });
    });

    heroForm.addEventListener('submit', (e) => {
      e.preventDefault();
      const q = input.value.trim();
      const routes = {
        judgments: '/judgments',
        citations: '/citations',
        proformas: '/proformas',
        guides: '/filing-guides'
      };
      const url = new URL(routes[activeType], window.location.origin);
      if (q) url.searchParams.set('q', q);
      window.location.href = url.toString();
    });
  }
});