/* 安芯全局交互层：即时按下反馈、鼠标高光、Toast、键盘状态与加载态。 */
(() => {
  const reducedMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
  const surfaceSelector = '.card, .alert-item, .panel, .e-card, .e-checkin, .e-sos, .sos-cancel, .btn, .nav-links a, .tabs a, .map-dot';
  const rippleSelector = 'button:not(:disabled), .btn, .nav-links a, .tabs a, .map-dot';

  const markSurface = (element) => {
    const isControl = element.matches('button, a, .btn, .e-card, .e-checkin, .e-sos, .sos-cancel, .map-dot');
    const containsControl = !!element.querySelector('button, a, .btn');
    if (isControl || containsControl) {
      element.classList.add('interactive-surface');
      if (element.matches('.card, .alert-item')) element.classList.add('is-interactive');
    }
  };

  document.querySelectorAll(surfaceSelector).forEach((element) => {
    markSurface(element);
    element.addEventListener('pointerenter', () => element.classList.add('is-pointer-over'));
    element.addEventListener('pointerleave', () => element.classList.remove('is-pointer-over'));
    element.addEventListener('pointermove', (event) => {
      const rect = element.getBoundingClientRect();
      element.style.setProperty('--pointer-x', `${event.clientX - rect.left}px`);
      element.style.setProperty('--pointer-y', `${event.clientY - rect.top}px`);
    });
  });

  document.addEventListener('pointerdown', (event) => {
    const target = event.target.closest(rippleSelector);
    if (!target || target.disabled || target.getAttribute('aria-busy') === 'true' || reducedMotion) return;
    const rect = target.getBoundingClientRect();
    const ripple = document.createElement('span');
    ripple.className = 'ui-ripple';
    ripple.style.left = `${event.clientX - rect.left}px`;
    ripple.style.top = `${event.clientY - rect.top}px`;
    target.appendChild(ripple);
    ripple.addEventListener('animationend', () => ripple.remove(), { once: true });
    window.setTimeout(() => ripple.remove(), 700);
  });

  document.addEventListener('keydown', (event) => {
    if (!['Enter', ' '].includes(event.key)) return;
    const target = event.target.closest('button, a, .map-dot');
    if (target) target.classList.add('is-key-pressed');
  });
  document.addEventListener('keyup', (event) => {
    const target = event.target.closest('button, a, .map-dot');
    if (target) target.classList.remove('is-key-pressed');
  });

  // 表单提交后立即锁定按钮，避免重复提交，并给用户明确的忙碌反馈。
  document.querySelectorAll('form').forEach((form) => {
    form.addEventListener('submit', () => {
      const submit = form.querySelector('button[type="submit"], input[type="submit"]');
      if (!submit) return;
      submit.classList.add('is-loading');
      submit.setAttribute('aria-busy', 'true');
      submit.disabled = true;
    });
  });

  // 当前导航项：让用户始终知道自己所在的位置。
  const currentPath = window.location.pathname.replace(/\/$/, '') || '/';
  document.querySelectorAll('.nav-links a[href]').forEach((link) => {
    const linkPath = new URL(link.href, window.location.origin).pathname.replace(/\/$/, '') || '/';
    if (linkPath === currentPath) {
      link.classList.add('active');
      link.setAttribute('aria-current', 'page');
    }
  });

  const topnavLinks = document.querySelector('.topnav .nav-links');
  const rubber = document.querySelector('.topnav .nav-rubber');
  const gooLayer = document.querySelector('.topnav .nav-goo-layer');
  let animateGooeyNav = () => 0;
  if (topnavLinks && rubber) {
    let hoveredLink = null;
    let activeLink = topnavLinks.querySelector('a.active');
    let stretchTimer = null;
    let rubberRect = null;
    const moveRubberTo = (link, stretch = false) => {
      const nav = topnavLinks.closest('.topnav');
      const navRect = nav.getBoundingClientRect();
      const rect = link.getBoundingClientRect();
      const nextLeft = rect.left - navRect.left;
      const nextTop = rect.top - navRect.top;
      const nextWidth = rect.width;
      const nextHeight = rect.height;
      const sameRow = rubberRect && Math.abs(rubberRect.top - nextTop) < 4;
      if (stretch && rubberRect && sameRow) {
        const currentRight = rubberRect.left + rubberRect.width;
        const nextRight = nextLeft + nextWidth;
        const edge = Math.min(rubberRect.left, nextLeft);
        rubber.style.left = `${edge}px`;
        rubber.style.width = `${Math.max(currentRight, nextRight) - edge}px`;
        rubber.classList.add('is-stretching');
        window.clearTimeout(stretchTimer);
        stretchTimer = window.setTimeout(() => {
          rubber.classList.remove('is-stretching');
          rubber.style.top = `${nextTop}px`;
          rubber.style.left = `${nextLeft}px`;
          rubber.style.width = `${nextWidth}px`;
          rubber.style.height = `${nextHeight}px`;
          rubberRect = { left: nextLeft, top: nextTop, width: nextWidth, height: nextHeight };
        }, 100);
      } else {
        rubber.style.top = `${nextTop}px`;
        rubber.style.left = `${nextLeft}px`;
        rubber.style.width = `${nextWidth}px`;
        rubber.style.height = `${nextHeight}px`;
        rubberRect = { left: nextLeft, top: nextTop, width: nextWidth, height: nextHeight };
      }
      rubber.classList.add('is-visible');
    };

    const settleOnActive = () => {
      activeLink = topnavLinks.querySelector('a.active') || activeLink;
      if (activeLink) moveRubberTo(activeLink);
      else rubber.classList.remove('is-visible', 'is-stretching');
    };

    animateGooeyNav = (link) => {
      if (reducedMotion || !gooLayer || !link || link === activeLink) return 0;
      const nav = topnavLinks.closest('.topnav');
      const navRect = nav.getBoundingClientRect();
      const sourceRect = (activeLink || link).getBoundingClientRect();
      const targetRect = link.getBoundingClientRect();
      const sourceX = sourceRect.left - navRect.left + sourceRect.width / 2;
      const sourceY = sourceRect.top - navRect.top + sourceRect.height / 2;
      const targetX = targetRect.left - navRect.left + targetRect.width / 2;
      const targetY = targetRect.top - navRect.top + targetRect.height / 2;
      const dx = targetX - sourceX;
      const dy = targetY - sourceY;
      const distance = Math.hypot(dx, dy) || 1;
      const normalX = -dy / distance;
      const normalY = dx / distance;

      gooLayer.replaceChildren();
      for (let index = 0; index < 14; index += 1) {
        const particle = document.createElement('span');
        const spread = (Math.random() - .5) * Math.min(52, 18 + distance * .18);
        const progress = .42 + Math.random() * .18;
        const offsetX = (Math.random() - .5) * sourceRect.width * .34;
        const offsetY = (Math.random() - .5) * sourceRect.height * .22;
        const duration = 330 + Math.random() * 130;
        particle.className = 'nav-goo-particle';
        particle.style.setProperty('--goo-x', `${sourceX}px`);
        particle.style.setProperty('--goo-y', `${sourceY}px`);
        particle.style.setProperty('--goo-size', `${7 + Math.random() * 10}px`);
        particle.style.setProperty('--goo-ox', `${offsetX}px`);
        particle.style.setProperty('--goo-oy', `${offsetY}px`);
        particle.style.setProperty('--goo-mx', `${dx * progress + normalX * spread}px`);
        particle.style.setProperty('--goo-my', `${dy * progress + normalY * spread}px`);
        particle.style.setProperty('--goo-dx', `${dx + (Math.random() - .5) * targetRect.width * .22}px`);
        particle.style.setProperty('--goo-dy', `${dy + (Math.random() - .5) * targetRect.height * .16}px`);
        particle.style.setProperty('--goo-duration', `${duration}ms`);
        particle.style.setProperty('--goo-delay', `${Math.random() * 42}ms`);
        gooLayer.appendChild(particle);
      }

      activeLink?.classList.remove('active');
      activeLink?.removeAttribute('aria-current');
      link.classList.add('active');
      link.setAttribute('aria-current', 'page');
      activeLink = link;
      moveRubberTo(link, true);
      rubber.classList.remove('is-gooey');
      rubber.getBoundingClientRect();
      rubber.classList.add('is-gooey');
      window.setTimeout(() => {
        rubber.classList.remove('is-gooey');
        gooLayer.replaceChildren();
      }, 520);
      return 360;
    };

    window.requestAnimationFrame(settleOnActive);
    document.fonts?.ready.then(settleOnActive);

    topnavLinks.addEventListener('pointerover', event => {
      if (event.pointerType === 'touch') return;
      const link = event.target.closest('a[href]');
      if (!link || !topnavLinks.contains(link)) return;
      const changed = hoveredLink && hoveredLink !== link;
      hoveredLink = link;
      moveRubberTo(link, changed);
    });
    topnavLinks.addEventListener('pointermove', event => {
      if (event.pointerType === 'touch') return;
      const link = event.target.closest('a[href]');
      if (link && link !== hoveredLink) {
        const changed = !!hoveredLink;
        hoveredLink = link;
        moveRubberTo(link, changed);
      }
    });
    topnavLinks.addEventListener('pointerleave', event => {
      if (event.pointerType === 'touch') return;
      hoveredLink = null;
      window.clearTimeout(stretchTimer);
      rubber.classList.remove('is-stretching');
      settleOnActive();
    });
    window.addEventListener('resize', () => {
      if (hoveredLink) moveRubberTo(hoveredLink);
      else settleOnActive();
    }, { passive: true });
  }

  const topnav = document.querySelector('.topnav');
  if (topnav) {
    const islandSizeKey = 'anxin-island-size';
    let navigationPending = false;
    if (!reducedMotion) {
      let previousSize = null;
      try {
        previousSize = JSON.parse(window.sessionStorage.getItem(islandSizeKey) || 'null');
        window.sessionStorage.removeItem(islandSizeKey);
      } catch (_) {
        previousSize = null;
      }

      const targetRect = topnav.getBoundingClientRect();
      const targetWidth = Math.round(targetRect.width);
      const targetHeight = Math.round(targetRect.height);
      const previousIsRecent = previousSize && Date.now() - previousSize.time < 10000;
      const maxIslandWidth = Math.max(0, window.innerWidth - 16);
      const previousWidth = previousIsRecent
        ? Math.min(Math.round(previousSize.width), maxIslandWidth)
        : targetWidth;
      const sameWidth = previousIsRecent && Math.abs(previousWidth - targetWidth) <= 1;
      const elasticPulse = Math.min(24, Math.max(8, Math.round(targetWidth * 0.04)));
      const startWidth = sameWidth
        ? Math.min(targetWidth + elasticPulse, maxIslandWidth)
        : previousWidth;

      if (previousIsRecent && startWidth > 0 && Math.abs(startWidth - targetWidth) > 1) {
        topnav.classList.add('is-resizing');
        topnav.style.transition = 'none';
        topnav.style.width = `${startWidth}px`;
        topnav.style.height = `${targetHeight}px`;
        topnav.getBoundingClientRect();

        let resizeTimer;
        const finishResize = (event) => {
          if (event && (event.target !== topnav || event.propertyName !== 'width')) return;
          window.clearTimeout(resizeTimer);
          topnav.removeEventListener('transitionend', finishResize);
          topnav.style.removeProperty('transition');
          topnav.style.removeProperty('width');
          topnav.style.removeProperty('height');
          topnav.classList.remove('is-resizing');
        };
        topnav.addEventListener('transitionend', finishResize);
        resizeTimer = window.setTimeout(() => finishResize(), 1100);
        window.requestAnimationFrame(() => {
          topnav.style.removeProperty('transition');
          topnav.style.width = `${targetWidth}px`;
        });
      }
    }

    if (!reducedMotion) topnav.addEventListener('click', (event) => {
      const link = event.target.closest('.nav-links a[href], .nav-user a[href]');
      if (!link || event.defaultPrevented || event.button !== 0 || event.metaKey || event.ctrlKey || event.shiftKey || event.altKey) return;
      if ((link.target && link.target !== '_self') || link.hasAttribute('download')) return;

      const destination = new URL(link.href, window.location.href);
      const destinationPath = destination.pathname.replace(/\/$/, '') || '/';
      if (destination.origin !== window.location.origin) return;
      if (destinationPath === currentPath && destination.search === window.location.search && destination.hash === window.location.hash) return;

      const rect = topnav.getBoundingClientRect();
      try {
        window.sessionStorage.setItem(islandSizeKey, JSON.stringify({
          width: Math.round(rect.width),
          time: Date.now(),
        }));
      } catch (_) {
        // Storage may be unavailable in private browsing; navigation remains unaffected.
      }

      const delay = topnavLinks?.contains(link) ? animateGooeyNav(link) : 0;
      if (delay > 0) {
        event.preventDefault();
        if (navigationPending) return;
        navigationPending = true;
        window.setTimeout(() => window.location.assign(destination.href), delay);
      }
    });
  }

  const toast = document.getElementById('app-toast');
  let toastTimer = null;
  window.showToast = (message, tone = 'success', duration = 2800) => {
    if (!toast) return;
    window.clearTimeout(toastTimer);
    toast.textContent = message;
    toast.dataset.tone = tone;
    toast.classList.add('is-visible');
    toastTimer = window.setTimeout(() => toast.classList.remove('is-visible'), duration);
  };

  // 对屏幕阅读器和键盘用户补齐最常见的图标按钮名称。
  const voiceButton = document.querySelector('.e-voice');
  if (voiceButton && !voiceButton.hasAttribute('aria-label')) voiceButton.setAttribute('aria-label', '播放语音提示');
})();
