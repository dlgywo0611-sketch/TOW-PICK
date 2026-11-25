(function exposeSessionScopeLogic(root) {
  'use strict';
  function createSessionScope() {
    let revision = 0;
    return {
      invalidate() { revision += 1; return revision; },
      snapshot() { return revision; },
      isCurrent(snapshot) { return snapshot === revision; },
    };
  }
  function staleSessionError() {
    const error = new Error('');
    error.staleSession = true;
    return error;
  }
  root.TwoPickSessionScopeLogic = { createSessionScope, staleSessionError };
}(typeof window !== 'undefined' ? window : globalThis));
