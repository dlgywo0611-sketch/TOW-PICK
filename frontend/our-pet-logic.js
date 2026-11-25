(function exposeOurPetLogic(root) {
  function growthState(experience, maximum = 100) {
    const max = Number(maximum) > 0 ? Number(maximum) : 100;
    const exp = Math.max(0, Math.min(max, Number(experience) || 0));
    return { experience: exp, maximum: max, percent: Math.round((exp / max) * 100), remaining: max - exp };
  }

  function deviceSummary({ usb = false, ble = false } = {}) {
    if (usb && ble) return { connected: true, label: 'USB와 BLE가 모두 연결됐어요.' };
    if (usb) return { connected: true, label: 'Arduino USB가 연결됐어요. BLE 연결을 기다려요.' };
    if (ble) return { connected: true, label: 'Meem BLE가 연결됐어요. USB 연결을 기다려요.' };
    return { connected: false, label: 'USB와 BLE 연결을 기다리고 있어요.' };
  }

  root.TwoPickOurPetLogic = { growthState, deviceSummary };
}(typeof window !== 'undefined' ? window : globalThis));
