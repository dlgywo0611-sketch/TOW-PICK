(() => {
  'use strict';
  const logic = globalThis.TwoPickOnboardingLogic;
  const root = document.querySelector('#onboarding');
  if (!logic || !root) return;
  const ui = {
    close: root.querySelector('#onboarding-close'), later: root.querySelector('#onboarding-later'),
    action: root.querySelector('#onboarding-action'), hint: root.querySelector('#onboarding-hint'),
    steps: Array.from(root.querySelectorAll('[data-onboarding-step]')),
  };

  function completionKey() {
    return state.user ? `tow_pick_onboarding_complete_${state.user.id}` : '';
  }

  function isPendingForUser() {
    const pending = localStorage.getItem('tow_pick_onboarding_pending');
    return Boolean(state.user && pending === String(state.user.email).trim().toLowerCase() && localStorage.getItem(completionKey()) !== 'true');
  }

  function currentState() {
    return logic.getOnboardingState({
      authenticated: Boolean(state.user),
      hasCouple: Boolean(state.couple),
      connected: Boolean(state.couple?.members?.length === 2),
    });
  }

  function render() {
    if (!isPendingForUser()) return root.classList.add('hidden');
    const status = currentState();
    root.classList.remove('hidden');
    ui.hint.textContent = status.message;
    for (const item of ui.steps) {
      const order = { account: 1, couple: 2, decision: 3 };
      const currentOrder = order[status.step];
      const itemOrder = order[item.dataset.onboardingStep];
      item.classList.toggle('complete', itemOrder < currentOrder || (itemOrder === 1 && state.user));
      item.classList.toggle('active', itemOrder === currentOrder);
    }
    ui.action.textContent = status.action === 'decision' ? '첫 공동결정 시작하기' : status.action === 'wait' ? '연결 상태 확인하기' : '커플 연결 시작하기';
    queueMicrotask(() => ui.action.focus());
  }

  function dismiss(complete = false) {
    if (complete && completionKey()) localStorage.setItem(completionKey(), 'true');
    if (complete) localStorage.removeItem('tow_pick_onboarding_pending');
    root.classList.add('hidden');
  }

  ui.action.addEventListener('click', async () => {
    const status = currentState();
    if (status.action === 'decision') {
      dismiss(true);
      location.hash = 'decision';
      return;
    }
    dismiss(false);
    if (status.action === 'wait' && elements.refreshCoupleButton && !elements.refreshCoupleButton.classList.contains('hidden')) {
      elements.refreshCoupleButton.click();
    }
    document.querySelector('#connection-actions, #connected-card')?.scrollIntoView({ behavior: 'smooth', block: 'center' });
  });
  ui.close.addEventListener('click', () => dismiss(false));
  ui.later.addEventListener('click', () => dismiss(false));
  root.addEventListener('keydown', (event) => { if (event.key === 'Escape') dismiss(false); });
  window.addEventListener('twopick:session-changed', render);
  render();
})();
