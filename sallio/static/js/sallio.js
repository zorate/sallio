/**
 * sallio.js — Core UI utilities
 * Handles: toasts, button loading, form guard, offline detection, page transitions
 */

// ============================================================
// TOAST SYSTEM
// ============================================================

const Sallio = {

  _toastContainer: null,

  _getToastContainer() {
    if (!this._toastContainer) {
      this._toastContainer = document.createElement('div');
      this._toastContainer.id = 'sallio-toast-container';
      this._toastContainer.setAttribute('aria-live', 'polite');
      this._toastContainer.setAttribute('aria-atomic', 'false');
      document.body.appendChild(this._toastContainer);
    }
    return this._toastContainer;
  },

  toast(message, type = 'info', duration = 4000) {
    const container = this._getToastContainer();
    const toast = document.createElement('div');
    toast.className = `sallio-toast sallio-toast--${type}`;
    toast.setAttribute('role', 'status');

    const icons = {
      success: `<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><polyline points="20 6 9 17 4 12"/></svg>`,
      error: `<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="10"/><line x1="12" y1="8" x2="12" y2="12"/><line x1="12" y1="16" x2="12.01" y2="16"/></svg>`,
      warning: `<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><path d="M10.29 3.86L1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z"/><line x1="12" y1="9" x2="12" y2="13"/><line x1="12" y1="17" x2="12.01" y2="17"/></svg>`,
      info: `<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="10"/><line x1="12" y1="16" x2="12" y2="12"/><line x1="12" y1="8" x2="12.01" y2="8"/></svg>`,
    };

    toast.innerHTML = `
      <span class="sallio-toast__icon">${icons[type] || icons.info}</span>
      <span class="sallio-toast__msg">${message}</span>
      <button class="sallio-toast__close" aria-label="Dismiss">&times;</button>
    `;

    container.appendChild(toast);

    // Animate in
    requestAnimationFrame(() => {
      requestAnimationFrame(() => toast.classList.add('sallio-toast--visible'));
    });

    const dismiss = () => {
      toast.classList.remove('sallio-toast--visible');
      toast.classList.add('sallio-toast--hiding');
      setTimeout(() => toast.remove(), 350);
    };

    toast.querySelector('.sallio-toast__close').addEventListener('click', dismiss);

    if (duration > 0) {
      setTimeout(dismiss, duration);
    }

    return { dismiss };
  },

  success(msg, duration) { return this.toast(msg, 'success', duration); },
  error(msg, duration)   { return this.toast(msg, 'error', duration || 6000); },
  warning(msg, duration) { return this.toast(msg, 'warning', duration); },
  info(msg, duration)    { return this.toast(msg, 'info', duration); },


  // ============================================================
  // BUTTON LOADING STATE
  // ============================================================

  /**
   * Set a button into a loading state.
   * Returns a restore() function to reset it.
   */
  buttonLoading(btn, loadingText) {
    if (!btn || btn.disabled) return () => {};
    const originalHTML = btn.innerHTML;
    const originalDisabled = btn.disabled;

    btn.disabled = true;
    btn.setAttribute('aria-busy', 'true');
    btn.innerHTML = `
      <span class="sallio-spinner" aria-hidden="true"></span>
      <span>${loadingText || 'Loading...'}</span>
    `;

    return function restore() {
      btn.disabled = originalDisabled;
      btn.removeAttribute('aria-busy');
      btn.innerHTML = originalHTML;
    };
  },

  /**
   * Set a button into a success state briefly, then restore.
   */
  buttonSuccess(btn, successText, duration = 2000) {
    if (!btn) return;
    const originalHTML = btn.innerHTML;
    btn.disabled = true;
    btn.innerHTML = `<span aria-hidden="true">✓</span> <span>${successText || 'Done'}</span>`;
    btn.classList.add('btn--success');
    setTimeout(() => {
      btn.disabled = false;
      btn.innerHTML = originalHTML;
      btn.classList.remove('btn--success');
    }, duration);
  },


  // ============================================================
  // FORM GUARD — Prevent duplicate submissions
  // ============================================================

  /**
   * Attach single-submit guard to a form.
   * loadingText shown on the submit button while request is in-flight.
   */
  guardForm(form, loadingText) {
    if (!form) return;
    let submitted = false;
    form.addEventListener('submit', function(e) {
      if (submitted) {
        e.preventDefault();
        return false;
      }
      submitted = true;
      const submitBtn = form.querySelector('[type="submit"]');
      if (submitBtn) {
        Sallio.buttonLoading(submitBtn, loadingText || 'Please wait...');
      }
      // Reset flag after timeout as a safety net (network timeout)
      setTimeout(() => { submitted = false; }, 15000);
    });
  },


  // ============================================================
  // NETWORK / OFFLINE DETECTION
  // ============================================================

  _offlineBanner: null,

  initOfflineDetection() {
    const show = () => {
      if (this._offlineBanner) return;
      this._offlineBanner = document.createElement('div');
      this._offlineBanner.id = 'sallio-offline-banner';
      this._offlineBanner.setAttribute('role', 'alert');
      this._offlineBanner.innerHTML = `
        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><line x1="1" y1="1" x2="23" y2="23"/><path d="M16.72 11.06A10.94 10.94 0 0 1 19 12.55"/><path d="M5 12.55a10.94 10.94 0 0 1 5.17-2.39"/><path d="M10.71 5.05A16 16 0 0 1 22.56 9"/><path d="M1.42 9a15.91 15.91 0 0 1 4.7-2.88"/><path d="M8.53 16.11a6 6 0 0 1 6.95 0"/><line x1="12" y1="20" x2="12.01" y2="20"/></svg>
        You're offline. Check your connection.
      `;
      document.body.prepend(this._offlineBanner);
    };

    const hide = () => {
      if (this._offlineBanner) {
        this._offlineBanner.remove();
        this._offlineBanner = null;
      }
    };

    window.addEventListener('offline', show);
    window.addEventListener('online', () => {
      hide();
      Sallio.success('Connection restored.');
    });

    if (!navigator.onLine) show();
  },


  // ============================================================
  // PAGE TRANSITION BAR
  // ============================================================

  _progressBar: null,

  initPageTransitions() {
    this._progressBar = document.createElement('div');
    this._progressBar.id = 'sallio-progress';
    this._progressBar.setAttribute('role', 'progressbar');
    this._progressBar.setAttribute('aria-hidden', 'true');
    document.body.prepend(this._progressBar);

    document.addEventListener('click', (e) => {
      const anchor = e.target.closest('a[href]');
      if (!anchor) return;
      const href = anchor.getAttribute('href');
      // Only trigger for same-origin page navigations
      if (!href || href.startsWith('#') || href.startsWith('javascript') || href.startsWith('http') || anchor.target === '_blank') return;
      if (e.ctrlKey || e.metaKey || e.shiftKey) return;
      this._startProgress();
    });

    // Stop progress on page load
    window.addEventListener('pageshow', () => this._stopProgress());
  },

  _startProgress() {
    if (!this._progressBar) return;
    this._progressBar.classList.remove('sallio-progress--done');
    this._progressBar.classList.add('sallio-progress--loading');
  },

  _stopProgress() {
    if (!this._progressBar) return;
    this._progressBar.classList.remove('sallio-progress--loading');
    this._progressBar.classList.add('sallio-progress--done');
    setTimeout(() => this._progressBar.classList.remove('sallio-progress--done'), 300);
  },


  // ============================================================
  // FLASH → TOAST BRIDGE
  // ============================================================

  /**
   * Reads existing server-rendered flash messages from the DOM,
   * converts them to toasts, and removes the DOM elements.
   */
  initFlashToasts() {
    const container = document.getElementById('flash-data');
    if (!container) return;
    container.querySelectorAll('span[data-msg]').forEach(el => {
      const type = el.dataset.type === 'success' ? 'success'
                 : el.dataset.type === 'error'   ? 'error'
                 : el.dataset.type === 'warning' ? 'warning'
                 : 'info';
      const msg = el.dataset.msg;
      if (msg) this.toast(msg, type);
    });
    container.remove();
  },


  // ============================================================
  // ACTIVE NAV
  // ============================================================

  initActiveNav() {
    const currentPath = window.location.pathname;
    document.querySelectorAll('.nav-link').forEach(link => {
      const href = link.getAttribute('href');
      if (href && href !== '/' && currentPath.startsWith(href)) {
        link.classList.add('nav-link--active');
      }
    });
  },


  // ============================================================
  // INIT ALL
  // ============================================================

  init() {
    this.initOfflineDetection();
    this.initPageTransitions();
    this.initFlashToasts();
    this.initActiveNav();
  }

};

// Auto-initialize on DOM ready
document.addEventListener('DOMContentLoaded', () => Sallio.init());
