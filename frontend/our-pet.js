(() => {
  'use strict';
  const logic = globalThis.TwoPickOurPetLogic;
  const data = globalThis.TwoPickFeatureData;
  const root = document.querySelector('.our-pet-profile');
  if (!logic || !data || !root) return;
  const ui = {
    bar: root.querySelector('#our-pet-exp-bar'), label: root.querySelector('#our-pet-exp-label'),
    next: root.querySelector('#our-pet-next-level'), dot: root.querySelector('#our-pet-device-dot'),
    device: root.querySelector('#our-pet-device-text'), progress: root.querySelector('.our-pet-progress'),
    showDevice: root.querySelector('#our-pet-show-device'),
  };
  const pet = data.getMockData('pet');
  const growth = logic.growthState(pet.experience, pet.maximum);
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
