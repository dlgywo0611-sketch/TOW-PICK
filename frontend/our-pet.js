(() => {
  'use strict';
  const logic = globalThis.TwoPickOurPetLogic;
  const root = document.querySelector('.our-pet-profile');
  if (!logic || !root) return;
  const ui = {
    bar: root.querySelector('#our-pet-exp-bar'), label: root.querySelector('#our-pet-exp-label'),
    next: root.querySelector('#our-pet-next-level'), dot: root.querySelector('#our-pet-device-dot'),
    device: root.querySelector('#our-pet-device-text'), progress: root.querySelector('.our-pet-progress'),
    showDevice: root.querySelector('#our-pet-show-device'),
  };
  const growth = logic.growthState(65, 100);
  ui.bar.style.width = `${growth.percent}%`;
  ui.label.textContent = `${growth.experience} / ${growth.maximum} EXP`;
  ui.next.textContent = `다음 레벨까지 ${growth.remaining} EXP 남았어요.`;
  ui.progress.setAttribute('aria-valuenow', String(growth.percent));
  ui.showDevice.addEventListener('click', () => document.querySelector('#petdock-device-section')?.scrollIntoView({ behavior: 'smooth' }));

  window.addEventListener('twopick:pet-state', (event) => {
    const summary = logic.deviceSummary(event.detail);
    ui.dot.classList.toggle('connected', summary.connected);
    ui.device.textContent = summary.label;
  });
})();
