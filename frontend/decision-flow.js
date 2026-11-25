/* TWO-PICK P0 decision web flow, independent of PET DOCK hardware events.
 * The existing /static/app.js declares `state`, `api`, and `showAlert` in
 * a classic script. This script is deferred after that script in index.html.
 * No partner's private condition text is ever requested or rendered.
 */
(() => {
  'use strict';
  const logic = globalThis.TwoPickDecisionLogic;
  if (!logic) throw new Error('TWO-PICK decision-flow-logic.js is missing');

  const root = document.querySelector('#decision-workspace');
  const $ = (selector) => root.querySelector(selector);
  const ui = {
    navConditions: document.querySelector('#nav-conditions'),
    navDecision: document.querySelector('#nav-decision'),
    refresh: $('#decision-refresh'),
    createForm: $('#decision-create-form'),
    list: $('#decision-list'),
    empty: $('#decision-empty'),
    detailBody: $('#decision-detail-body'),
    selectedTitle: $('#decision-current-title'),
    selectedStatus: $('#decision-current-state'),
    progress: $('#decision-progress'),
    progressMessage: $('#decision-progress-message'),
    conditionForm: $('#decision-condition-form'),
    conditionButton: $('#decision-save-condition'),
    conditionCount: $('#decision-submit-count'),
    conditionMembers: $('#decision-submit-members'),
    recommendForm: $('#decision-recommend-form'),
    options: $('#decision-options'),
    addOption: $('#decision-add-option'),
    recommendButton: $('#decision-recommend-button'),
    consent: $('#decision-one-shot-consent'),
    recommendationNotice: $('#decision-recommendation-notice'),
    recommendationNoticeTitle: $('#decision-recommendation-notice-title'),
    recommendationNoticeMessage: $('#decision-recommendation-notice-message'),
    openManual: $('#decision-open-manual'),
    startNew: $('#decision-start-new'),
    candidateText: $('#decision-candidate-text'),
    approvalCount: $('#decision-approval-count'),
    approvalMembers: $('#decision-approval-members'),
    approveButton: $('#decision-approve-button'),
    manualForm: $('#decision-manual-form'),
    manualButton: $('#decision-manual-button'),
    manualInput: $('#decision-manual-content'),
  };
  const flow = {
    key: null,
    seq: 0,
    list: [],
    selectedId: null,
    detail: null,
    status: null,
    ownConditions: null,
    attempted: new Set(),
    recommendationError: '',
    busy: false,
  };

  function report(error) {
    showAlert(error instanceof Error ? error.message : '요청을 처리하지 못했어요.');
  }

  function activeKey() {
    if (!state.user || !state.token || !state.couple || state.couple.members.length !== 2) {
      return null;
    }
    return `${state.user.id}:${state.couple.id}`;
  }

  function currentMembers() {
    return Array.isArray(state.couple?.members) ? state.couple.members : [];
  }

  function drawList() {
    ui.list.replaceChildren();
    if (!flow.list.length) {
      ui.list.textContent = '아직 공동결정이 없어요.';
      return;
    }
    for (const decision of flow.list) {
      const button = document.createElement('button');
      button.className = 'decision-list-button';
      button.type = 'button';
      button.setAttribute('aria-pressed', String(flow.selectedId === decision.id));
      const title = document.createElement('strong');
      title.textContent = decision.title;
      const statusLabel = document.createElement('span');
      statusLabel.textContent = decision.status === 'confirmed' ? '결정 완료' : '진행 중';
      button.append(title, statusLabel);
      button.addEventListener('click', () => selectDecision(decision.id));
      ui.list.append(button);
    }
    window.dispatchEvent(new CustomEvent('twopick:decisions-changed', { detail: { decisions: flow.list.slice() } }));
  }

  function renderMemberStatuses() {
    ui.conditionMembers.replaceChildren();
    const list = logic.getMemberStates(currentMembers(), flow.status);
    ui.conditionCount.textContent = `조건 제출 ${list.filter((x) => x.submitted).length}/2 · 상세 조건은 본인만 볼 수 있어요.`;
    for (const member of list) {
      const item = document.createElement('li');
      item.textContent = `${member.id === state.user.id ? '나' : member.nickname}: ${member.submitted ? '제출 완료' : '미제출'}`;
      ui.conditionMembers.append(item);
    }
  }

  function renderApprovals() {
    ui.approvalMembers.replaceChildren();
    const current = flow.detail?.current_candidate;
    ui.candidateText.textContent = current
      ? `v${current.version} · ${current.content}`
      : '후보가 아직 없어요. 두 사람의 조건을 제출한 다음 추천 또는 직접 등록해 주세요.';
    ui.approvalCount.textContent = current
      ? `승인 ${current.approval_count}/2${flow.detail.confirmed ? ' · 최종 확정!' : ''}`
      : '승인 0/2';
    for (const member of currentMembers()) {
      const approval = current?.member_approvals?.find((item) => item.user_id === member.id);
      const item = document.createElement('li');
      item.textContent = `${member.id === state.user.id ? '나' : member.nickname}: ${approval?.approved ? '승인 완료' : '승인 대기'}`;
      ui.approvalMembers.append(item);
    }
    ui.approveButton.disabled = flow.busy || !logic.canApprove(flow.detail, state.user.id);
    ui.approveButton.textContent = flow.detail?.confirmed ? '두 사람 모두 승인 · 확정 완료' :
      current?.member_approvals?.find((item) => item.user_id === state.user.id)?.approved
        ? '내 승인 완료 · 상대방을 기다려요' : '이 후보 승인하기';
  }

  function renderRecommendationNotice() {
    const fallback = logic.getRecommendationFallbackState(
      flow.detail,
      flow.status,
      flow.attempted.has(flow.selectedId),
      flow.recommendationError,
    );
    ui.recommendationNotice.classList.toggle('hidden', !fallback.visible);
    ui.recommendationNotice.classList.toggle('warning', fallback.tone === 'warning');
    ui.recommendationNoticeTitle.textContent = fallback.title;
    ui.recommendationNoticeMessage.textContent = fallback.message;
    ui.openManual.disabled = flow.busy || !fallback.canUseManual;
  }

  function renderProgress() {
    const stage = logic.getDecisionStage(flow.detail, flow.status, state.user.id);
    ui.progress.dataset.stage = stage.key;
    ui.progressMessage.textContent = stage.message;
    const items = ui.progress.querySelectorAll('[data-decision-stage]');
    items.forEach((item, index) => {
      item.classList.toggle('complete', index < stage.index || stage.key === 'confirmed');
      item.classList.toggle('active', index === stage.index && stage.key !== 'confirmed');
      item.setAttribute('aria-current', index === stage.index ? 'step' : 'false');
    });
  }

  function renderDetails() {
    const detail = flow.detail;
    ui.detailBody.classList.toggle('hidden', !flow.selectedId);
    ui.empty.classList.toggle('hidden', Boolean(flow.selectedId));
    if (!flow.selectedId) return;
    ui.selectedTitle.textContent = detail?.title || '결정 불러오는 중…';
    ui.selectedStatus.textContent = detail?.confirmed ? '최종 확정' : '진행 중';
    ui.selectedStatus.classList.toggle('confirmed', Boolean(detail?.confirmed));

    const editable = logic.canEditConditions(detail);
    for (const control of ui.conditionForm.querySelectorAll('input, textarea, button')) {
      control.disabled = flow.busy || !editable;
    }
    if (flow.ownConditions) {
      for (const name of ['max_budget', 'available_time', 'preferences', 'avoidances']) {
        ui.conditionForm.elements.namedItem(name).value = String(flow.ownConditions[name] ?? '');
      }
    } else {
      ui.conditionForm.reset();
    }
    ui.conditionButton.textContent = editable ? (flow.ownConditions ? '내 조건 수정·저장하기' : '내 조건 저장하기') :
      '후보 생성 후 조건 수정 불가';
    renderMemberStatuses();
    renderApprovals();
    renderRecommendationNotice();
    renderProgress();
    const allowRecommendation = logic.canRecommend(detail, flow.status, flow.attempted.has(flow.selectedId));
    ui.recommendButton.disabled = flow.busy || !allowRecommendation;
    ui.addOption.disabled = flow.busy || !allowRecommendation || ui.options.children.length >= 8;
    for (const input of ui.recommendForm.querySelectorAll('input:not([type=checkbox]), button[data-remove-option]')) {
      input.disabled = flow.busy || !allowRecommendation;
    }
    ui.consent.disabled = flow.busy || !allowRecommendation;
    ui.manualButton.disabled = flow.busy || detail?.status !== 'open' || !logic.conditionsReady(flow.status);
  }

  function resetOptions() {
    ui.options.replaceChildren();
    ui.consent.checked = false;
    addOptionRow();
    addOptionRow();
  }

  function addOptionRow() {
    if (ui.options.children.length >= 8) return;
    const item = document.createElement('div');
    item.className = 'decision-option';
    // Constant markup only. All values from the API and user input are inserted via textContent/value.
    item.innerHTML = `
      <label>후보 이름<input name="title" maxlength="180" required placeholder="예: 조용한 한식 식사" /></label>
      <label>2인 예상 총액(원)<input name="estimated_total_cost_krw" type="number" min="0" max="1000000000" step="1" required placeholder="예: 18000" /></label>
      <label>시간 슬롯<input name="time_slot" maxlength="100" required placeholder="예: 토 18:00-20:00" /></label>
      <label>공개 태그(쉼표 구분)<input name="tags" placeholder="예: 한식, 조용한 곳" /></label>
      <button type="button" data-remove-option class="decision-remove">삭제</button>`;
    item.querySelector('[data-remove-option]').addEventListener('click', () => {
      if (ui.options.children.length <= 2) {
        showAlert('추천 후보는 최소 2개가 필요해요.');
        return;
      }
      item.remove();
      renderDetails();
    });
    ui.options.append(item);
    ui.addOption.disabled = ui.options.children.length >= 8;
  }

  function selectedSnapshot(key = flow.key, id = flow.selectedId, seq = flow.seq) {
    return key !== null && key === flow.key && id === flow.selectedId && seq === flow.seq;
  }

  async function loadDetail() {
    const key = flow.key;
    const id = flow.selectedId;
    const seq = ++flow.seq;
    if (!key || id === null) return;
    try {
      const detail = await api(`/decisions/${id}`);
      const status = await api(`/decisions/${id}/conditions/status`);
      if (!selectedSnapshot(key, id, seq)) return;
      let own = null;
      const mySubmitted = status.member_conditions.some(
        (member) => member.user_id === state.user.id && member.submitted,
      );
      if (mySubmitted) own = await api(`/decisions/${id}/conditions/me`);
      if (!selectedSnapshot(key, id, seq)) return;
      flow.detail = detail;
      flow.status = status;
      flow.ownConditions = own;
      renderDetails();
    } catch (error) {
      if (selectedSnapshot(key, id, seq)) report(error);
    }
  }

  async function selectDecision(id) {
    if (!flow.key || flow.busy) return;
    flow.selectedId = id;
    flow.detail = null;
    flow.status = null;
    flow.ownConditions = null;
    flow.recommendationError = '';
    ui.conditionForm.reset();
    resetOptions();
    drawList();
    renderDetails();
    await loadDetail();
  }

  async function refreshDecisions() {
    if (!flow.key || flow.busy) return;
    const key = flow.key;
    try {
      const list = await api('/decisions');
      if (flow.key !== key) return;
      flow.list = list;
      const known = list.some((decision) => decision.id === flow.selectedId);
      if (!known) {
        const next = list.length ? list[0].id : null;
        if (next !== null) {
          await selectDecision(next);
          return;
        }
        flow.selectedId = null;
        flow.detail = null;
        flow.status = null;
        flow.ownConditions = null;
      }
      drawList();
      renderDetails();
      if (flow.selectedId !== null) await loadDetail();
    } catch (error) {
      if (flow.key === key) report(error);
    }
  }

  function onSessionChange() {
    const key = activeKey();
    root.classList.toggle('hidden', !key);
    for (const step of [ui.navConditions, ui.navDecision]) {
      step.classList.toggle('disabled', !key);
      step.classList.toggle('active', Boolean(key));
    }
    if (key === flow.key) return;
    flow.key = key;
    flow.seq += 1;
    flow.list = [];
    flow.selectedId = null;
    flow.detail = null;
    flow.status = null;
    flow.ownConditions = null;
    flow.recommendationError = '';
    flow.attempted.clear();
    flow.busy = false;
    ui.refresh.disabled = false;
    ui.createForm.querySelector('button[type=submit]').disabled = false;
    ui.createForm.reset();
    ui.conditionForm.reset();
    ui.manualForm.reset();
    resetOptions();
    drawList();
    renderDetails();
    if (key) void refreshDecisions();
  }

  function setBusy(busy) {
    flow.busy = busy;
    ui.createForm.querySelector('button[type=submit]').disabled = busy;
    ui.refresh.disabled = busy;
    renderDetails();
  }

  async function action(work, after, onError) {
    if (flow.busy || !flow.key) return;
    const key = flow.key;
    setBusy(true);
    try {
      const result = await work();
      if (key !== flow.key) return;
      if (after) await after(result);
    } catch (error) {
      if (key === flow.key) {
        if (onError) onError(error);
        report(error);
      }
    } finally {
      if (key === flow.key) setBusy(false);
    }
  }

  ui.refresh.addEventListener('click', () => void refreshDecisions());
  ui.createForm.addEventListener('submit', (event) => {
    event.preventDefault();
    const title = String(new FormData(ui.createForm).get('title') ?? '').trim();
    if (!title) return showAlert('결정 제목을 입력해 주세요.');
    void action(
      () => api('/decisions', { method: 'POST', body: JSON.stringify({ title }) }),
      async (created) => {
        ui.createForm.reset();
        flow.list.unshift(created);
        showAlert('새 공동결정을 만들었어요. 각자 비공개 조건을 입력해 주세요.', true);
        // Avoid selectDecision's busy guard; load selected details directly.
        flow.selectedId = created.id;
        flow.detail = null;
        flow.status = null;
        flow.ownConditions = null;
        resetOptions();
        drawList();
        renderDetails();
        await loadDetail();
      },
    );
  });

  ui.conditionForm.addEventListener('submit', (event) => {
    event.preventDefault();
    if (!logic.canEditConditions(flow.detail)) return;
    const form = new FormData(ui.conditionForm);
    const rawBudget = String(form.get('max_budget') ?? '').trim();
    if (!/^\d+$/.test(rawBudget)) return showAlert('2인 총액 상한은 0 이상의 정수로 입력해 주세요.');
    const payload = {
      max_budget: Number(rawBudget),
      available_time: String(form.get('available_time') ?? '').trim(),
      preferences: String(form.get('preferences') ?? '').trim(),
      avoidances: String(form.get('avoidances') ?? '').trim(),
    };
    const id = flow.selectedId;
    void action(
      () => api(`/decisions/${id}/conditions/me`, { method: 'PUT', body: JSON.stringify(payload) }),
      async () => {
        showAlert('내 비공개 조건을 저장했어요. 상대방에게는 제출 여부만 보여요.', true);
        await loadDetail();
      },
    );
  });

  ui.addOption.addEventListener('click', () => addOptionRow());
  ui.openManual.addEventListener('click', () => {
    ui.manualForm.scrollIntoView({ behavior: 'smooth', block: 'center' });
    ui.manualInput.focus({ preventScroll: true });
  });
  ui.startNew.addEventListener('click', () => {
    ui.createForm.scrollIntoView({ behavior: 'smooth', block: 'center' });
    ui.createForm.querySelector('input[name="title"]').focus({ preventScroll: true });
    showAlert('새로운 공동결정은 새로운 조건과 1회의 추천 기회를 사용합니다.');
  });
  ui.manualForm.addEventListener('click', (event) => {
    const template = event.target.closest('[data-manual-template]');
    if (!template) return;
    ui.manualInput.value = template.dataset.manualTemplate;
    ui.manualInput.focus();
  });
  ui.recommendForm.addEventListener('submit', (event) => {
    event.preventDefault();
    if (!logic.canRecommend(flow.detail, flow.status, flow.attempted.has(flow.selectedId))) return;
    if (!ui.consent.checked) return showAlert('추천 1회 정책에 동의해 주세요.');
    let options;
    try {
      options = logic.makeOptions(Array.from(ui.options.children, (element) => {
        const find = (name) => element.querySelector(`[name="${name}"]`).value;
        return { title: find('title'), estimated_total_cost_krw: find('estimated_total_cost_krw'),
          time_slot: find('time_slot'), tags: find('tags') };
      }));
    } catch (error) {
      return report(error);
    }
    const id = flow.selectedId;
    flow.recommendationError = '';
    void action(
      () => api(`/decisions/${id}/recommendations`, { method: 'POST',
        body: JSON.stringify({ options }) }),
      async () => {
        flow.attempted.add(id);
        flow.recommendationError = '';
        showAlert('균형 추천 후보가 생성됐어요. 두 사람이 각각 승인해야 확정돼요.', true);
        await loadDetail();
      },
      (error) => {
        if (/No mutually suitable option|Recommendation already attempted|추천 기회는 소진|추천 기회는 이미 사용/.test(error.message)) {
          flow.attempted.add(id);
          flow.recommendationError = error.message;
          renderDetails();
        }
      },
    );
  });

  ui.approveButton.addEventListener('click', () => {
    if (!logic.canApprove(flow.detail, state.user.id)) return;
    const id = flow.selectedId;
    const candidateId = flow.detail.current_candidate.id;
    void action(
      () => api(`/candidates/${candidateId}/approve`, { method: 'POST' }),
      async () => {
        showAlert('승인을 기록했어요. 상대방이 아직 승인하지 않았다면 새로고침하여 상태를 확인해 주세요.', true);
        await loadDetail();
        if (flow.detail?.confirmed) showAlert('두 사람 모두 승인해 최종 결정이 확정됐어요!', true);
        const updatedList = await api('/decisions');
        if (flow.key === activeKey()) {
          flow.list = updatedList;
          drawList();
        }
      },
    );
  });

  ui.manualForm.addEventListener('submit', (event) => {
    event.preventDefault();
    const id = flow.selectedId;
    if (!flow.detail || flow.detail.status !== 'open' || !logic.conditionsReady(flow.status)) return;
    const content = String(new FormData(ui.manualForm).get('content') ?? '').trim();
    if (!content) return showAlert('후보 내용을 입력해 주세요.');
    const already = flow.detail.current_candidate;
    if (already && !globalThis.confirm('새 후보로 변경하면 기존 승인 상태가 새 후보로 승계되지 않습니다. 계속할까요?')) return;
    void action(
      () => api(`/decisions/${id}/candidates`, { method: 'POST', body: JSON.stringify({ content }) }),
      async () => {
        ui.manualForm.reset();
        flow.recommendationError = '';
        showAlert('새 후보 버전을 등록했어요. 두 계정이 최신 후보를 각각 승인해야 해요.', true);
        await loadDetail();
      },
    );
  });

  window.addEventListener('twopick:session-changed', onSessionChange);
  onSessionChange();
})();
