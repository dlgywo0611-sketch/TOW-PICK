(function exposeSettingsLogic(root) {
  const DEFAULT_PREFERENCES = Object.freeze({ decision: true, schedule: true, pet: true });

  function normalizeNickname(value) {
    return String(value || '').trim().replace(/\s+/g, ' ').slice(0, 50);
  }

  function validateNickname(value) {
    const nickname = normalizeNickname(value);
    if (!nickname) return { valid: false, message: '표시 이름을 입력해 주세요.', value: '' };
    return { valid: true, message: '', value: nickname };
  }

  function normalizePreferences(value = {}) {
    return Object.fromEntries(Object.entries(DEFAULT_PREFERENCES).map(([key, fallback]) => [
      key, typeof value[key] === 'boolean' ? value[key] : fallback,
    ]));
  }

  root.TwoPickSettingsLogic = { DEFAULT_PREFERENCES, normalizeNickname, validateNickname, normalizePreferences };
}(typeof window !== 'undefined' ? window : globalThis));
