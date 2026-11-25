(function exposeErrorHandlingLogic(root) {
  function normalizeApiDetail(detail, messages = {}) {
    if (Array.isArray(detail)) {
      const first = detail[0];
      const field = Array.isArray(first?.loc) ? first.loc.at(-1) : '';
      return field ? `${field} 입력값을 확인해 주세요.` : '입력값을 확인해 주세요.';
    }
    if (typeof detail === 'string' && detail.trim()) return messages[detail] || detail;
    return '요청을 처리하지 못했습니다. 잠시 후 다시 시도해 주세요.';
  }

  function friendlyFetchError(error) {
    if (error?.name === 'AbortError') return '응답 시간이 길어 요청을 중단했습니다. 잠시 후 다시 시도해 주세요.';
    return '서버에 연결할 수 없습니다. 인터넷 연결을 확인한 뒤 다시 시도해 주세요.';
  }

  function isMutation(method = 'GET') {
    return !['GET', 'HEAD', 'OPTIONS'].includes(String(method).toUpperCase());
  }

  root.TwoPickErrorHandlingLogic = { normalizeApiDetail, friendlyFetchError, isMutation };
}(typeof window !== 'undefined' ? window : globalThis));
