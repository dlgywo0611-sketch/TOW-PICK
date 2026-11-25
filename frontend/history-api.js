(() => {
  'use strict';
  const logic = globalThis.TwoPickHistoryApiLogic;
  const root = document.querySelector('[data-service-page="history"]');
  if (!logic || !root) return;
  const ui = {
    list: root.querySelector('#history-list'), detail: root.querySelector('#history-detail'), title: root.querySelector('#history-detail-title'),
    meta: root.querySelector('#history-detail-meta'), result: root.querySelector('#history-detail-result'), summary: root.querySelector('#history-detail-summary'),
    buttons: root.querySelector('#satisfaction-buttons'), comment: root.querySelector('#satisfaction-comment'), save: root.querySelector('#satisfaction-save'),
    status: root.querySelector('#satisfaction-status'), refresh: root.querySelector('#history-refresh'),
  };
  let items = []; let selectedId = null; let selectedScore = null; let busy = false;
  const escapeHtml = (value) => String(value).replace(/[&<>'"]/g, (character) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', "'": '&#39;', '"': '&quot;' }[character]));
  const selectedItem = () => items.find((item) => item.decisionId === selectedId) || items[0] || null;
  const dateLabel = (value) => value ? `${new Date(value).toLocaleString('ko-KR', { timeZone: 'Asia/Seoul' })} 확정` : '이전 확정 기록 · 확정 시각 정보 없음';

  function renderFeedback(feedback = {}) {
    const normalized = logic.normalizeFeedback(feedback);
    selectedScore = normalized.score;
    ui.comment.value = normalized.comment;
    ui.buttons.innerHTML = [1, 2, 3, 4, 5].map((score) => `<button type="button" data-rating="${score}" aria-label="만족도 ${score}점" aria-pressed="${selectedScore === score}">${score}<span>♥</span></button>`).join('');
    ui.save.disabled = !selectedScore;
    ui.status.textContent = selectedScore ? `${selectedScore}점 · 내 평가만 표시됩니다.` : '아직 작성한 내 평가가 없어요.';
  }

  async function loadFeedback() {
    const item = selectedItem();
    if (!item) return;
    renderFeedback();
    try { renderFeedback(await api(`/decisions/${item.decisionId}/feedback/me`)); }
    catch (error) { if (error.status !== 404) ui.status.textContent = error.message; }
  }

  function render() {
    const item = selectedItem();
    if (!item) { ui.list.innerHTML = '<p class="decision-empty">확정된 공동결정 기록이 아직 없어요.</p>'; ui.detail.classList.add('hidden'); return; }
    ui.detail.classList.remove('hidden');
    ui.list.innerHTML = items.map((entry) => `<button type="button" class="history-item" data-history-id="${entry.decisionId}" aria-pressed="${entry.decisionId === item.decisionId}"><span class="history-icon" aria-hidden="true">✓</span><span><strong>${escapeHtml(entry.title)}</strong><small>후보 v${entry.version} · ${escapeHtml(dateLabel(entry.confirmedAt))}</small></span><span aria-hidden="true">→</span></button>`).join('');
    ui.title.textContent = item.title; ui.meta.textContent = `${dateLabel(item.confirmedAt)} · 두 사람 모두 승인`; ui.result.textContent = item.result;
    ui.summary.textContent = `확정 후보 버전 v${item.version} · ${item.source === 'legacy' ? '기존 결정 상세에서 보완한 기록' : '확정 이력 API 기록'}`;
    void loadFeedback();
  }

  async function refresh() {
    if (!state.user || !state.couple || busy) return;
    busy = true; ui.refresh.disabled = true; ui.refresh.textContent = '불러오는 중…';
    try {
      const [decisions, confirmations] = await Promise.all([api('/decisions'), api('/decision-confirmations')]);
      const recorded = new Set(confirmations.map((item) => item.decision_id));
      const legacy = decisions.filter((item) => item.status === 'confirmed' && !recorded.has(item.id));
      const details = await Promise.all(legacy.map((item) => api(`/decisions/${item.id}`)));
      items = logic.buildHistory(decisions, confirmations, details);
      if (!items.some((item) => item.decisionId === selectedId)) selectedId = items[0]?.decisionId ?? null;
      render();
    } catch (error) { ui.list.innerHTML = `<p class="decision-empty">${escapeHtml(error.message)}</p>`; ui.detail.classList.add('hidden'); }
    finally { busy = false; ui.refresh.disabled = false; ui.refresh.textContent = '기록 새로고침'; }
  }

  ui.list.addEventListener('click', (event) => { const button = event.target.closest('[data-history-id]'); if (!button) return; selectedId = Number(button.dataset.historyId); render(); });
  ui.buttons.addEventListener('click', (event) => {
    const button = event.target.closest('[data-rating]'); if (!button) return; selectedScore = Number(button.dataset.rating);
    ui.buttons.querySelectorAll('[data-rating]').forEach((item) => item.setAttribute('aria-pressed', String(Number(item.dataset.rating) === selectedScore)));
    ui.save.disabled = false; ui.status.textContent = `${selectedScore}점을 선택했어요. 저장 버튼을 눌러 반영하세요.`;
  });
  ui.save.addEventListener('click', async () => {
    const item = selectedItem(); if (!item || !selectedScore) return; setButtonBusy(ui.save, true, '저장 중…');
    try {
      const feedback = await api(`/decisions/${item.decisionId}/feedback/me`, { method: 'PUT', body: JSON.stringify({ score: selectedScore, comment: ui.comment.value.trim() || null }) });
      renderFeedback(feedback); showAlert('내 만족도 평가를 저장했습니다.', true);
    } catch (error) { ui.status.textContent = error.message; }
    finally { setButtonBusy(ui.save, false, ''); }
  });
  ui.refresh.addEventListener('click', refresh);
  window.addEventListener('twopick:session-changed', refresh);
  window.addEventListener('twopick:decisions-changed', refresh);
  void refresh();
})();
