(() => {
  'use strict';
  const logic = globalThis.TwoPickSettingsLogic;
  const root = document.querySelector('.couple-profile-panel');
  if (!logic || !root) return;
  const keys = { nickname: 'tow_pick_local_nickname', preferences: 'tow_pick_preferences' };
  const ui = {
    form: root.querySelector('#profile-settings-form'), nickname: root.querySelector('#settings-nickname'),
    email: root.querySelector('#settings-email'), logout: root.querySelector('#settings-logout'),
    decision: root.querySelector('#setting-decision-notifications'),
    schedule: root.querySelector('#setting-schedule-notifications'), pet: root.querySelector('#setting-pet-notifications'),
  };

  function readPreferences() {
    try { return logic.normalizePreferences(JSON.parse(localStorage.getItem(keys.preferences) || '{}')); }
    catch (_) { return logic.normalizePreferences(); }
  }

  function render() {
    if (!state.user) return;
    const localNickname = logic.normalizeNickname(localStorage.getItem(keys.nickname));
    ui.nickname.value = localNickname || state.user.nickname;
    ui.email.value = state.user.email || '';
    const preferences = readPreferences();
    ui.decision.checked = preferences.decision;
    ui.schedule.checked = preferences.schedule;
    ui.pet.checked = preferences.pet;
    if (localNickname) {
      elements.profileName.textContent = localNickname;
      elements.profileAvatar.textContent = localNickname.slice(0, 1).toUpperCase();
    }
  }

  ui.form.addEventListener('submit', (event) => {
    event.preventDefault();
    const result = logic.validateNickname(ui.nickname.value);
    if (!result.valid) { showAlert(result.message); ui.nickname.focus(); return; }
    localStorage.setItem(keys.nickname, result.value);
    ui.nickname.value = result.value;
    render();
    showAlert('표시 이름을 이 기기에 저장했습니다.', true);
  });

  [ui.decision, ui.schedule, ui.pet].forEach((input) => input.addEventListener('change', () => {
    localStorage.setItem(keys.preferences, JSON.stringify({
      decision: ui.decision.checked, schedule: ui.schedule.checked, pet: ui.pet.checked,
    }));
    showAlert('알림 설정을 이 기기에 저장했습니다.', true);
  }));

  ui.logout.addEventListener('click', () => elements.logoutButton.click());
  window.addEventListener('twopick:session-changed', render);
  render();
})();
