(function exposeOnboardingLogic(root) {
  function getOnboardingState({ authenticated = false, hasCouple = false, connected = false } = {}) {
    if (!authenticated) return { step: 'account', action: 'login', message: '먼저 가입한 계정으로 로그인해 주세요.' };
    if (!hasCouple) return { step: 'couple', action: 'connect', message: '초대 코드를 만들거나 상대방의 코드를 입력해 주세요.' };
    if (!connected) return { step: 'couple', action: 'wait', message: '초대 코드를 전달한 뒤 상대방의 연결을 기다려 주세요.' };
    return { step: 'decision', action: 'decision', message: '연결이 완료됐어요. 이제 첫 공동결정을 만들어 보세요.' };
  }

  root.TwoPickOnboardingLogic = { getOnboardingState };
}(typeof window !== 'undefined' ? window : globalThis));
