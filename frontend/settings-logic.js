(function exposeSettingsLogic(root) {
  const DEFAULT_NOTIFICATION_SETTINGS = Object.freeze({ consent: false, d1_enabled: false, day_of_enabled: false, send_time: '09:00' });

  function normalizeNickname(value) {
    return String(value || '').trim().replace(/\s+/g, ' ').slice(0, 50);
  }

  function validateNickname(value) {
    const nickname = normalizeNickname(value);
    if (!nickname) return { valid: false, message: '표시 이름을 입력해 주세요.', value: '' };
    return { valid: true, message: '', value: nickname };
  }

  function normalizeNotificationSettings(value = {}) {
    const sendTime = String(value.send_time || '09:00').slice(0, 5);
    return { consent: value.consent === true, d1_enabled: value.d1_enabled === true, day_of_enabled: value.day_of_enabled === true, send_time: /^([01]\d|2[0-3]):[0-5]\d$/.test(sendTime) ? sendTime : '09:00' };
  }

  root.TwoPickSettingsLogic = { DEFAULT_NOTIFICATION_SETTINGS, normalizeNickname, validateNickname, normalizeNotificationSettings };
}(typeof window !== 'undefined' ? window : globalThis));
