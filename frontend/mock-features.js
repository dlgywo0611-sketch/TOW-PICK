(() => {
  const logic = window.MockFeaturesLogic;
  if (!logic) return;

  const history = [
    { id: 'dinner-1', category: 'meal', icon: '🍝', title: '금요일 저녁 메뉴', date: '2026. 11. 20.', result: '동네 파스타 식당', summary: '퇴근 후 가까운 곳에서 천천히 저녁을 먹기로 했어요.' },
    { id: 'weekend-1', category: 'date', icon: '🌿', title: '주말 데이트', date: '2026. 11. 15.', result: '서울숲 산책', summary: '사람이 적은 오전 시간에 만나 따뜻한 음료와 함께 산책했어요.' },
    { id: 'movie-1', category: 'home', icon: '🎬', title: '오늘 볼 영화', date: '2026. 11. 8.', result: '어바웃 타임', summary: '집에서 간단한 간식과 함께 다시 보고 싶던 영화를 골랐어요.' },
  ];
  const ratingKey = 'tow_pick_mock_satisfaction';
  const elements = {
    filter: document.querySelector('#history-filter'), list: document.querySelector('#history-list'),
    title: document.querySelector('#history-detail-title'), meta: document.querySelector('#history-detail-meta'),
    result: document.querySelector('#history-detail-result'), summary: document.querySelector('#history-detail-summary'),
    buttons: document.querySelector('#satisfaction-buttons'), status: document.querySelector('#satisfaction-status'),
  };
  if (!elements.list) return;

  let selectedId = history[0].id;
  const ratings = JSON.parse(localStorage.getItem(ratingKey) || '{}');

  function selectedItem() {
    return history.find((item) => item.id === selectedId) || history[0];
  }

  function saveRating(itemId, value) {
    const rating = logic.normalizeRating(value);
    if (!rating) return;
    ratings[itemId] = rating;
    localStorage.setItem(ratingKey, JSON.stringify(ratings));
    renderDetail();
  }

  function renderList() {
    const items = logic.filterHistory(history, elements.filter.value);
    elements.list.innerHTML = items.length ? items.map((item) => `
      <button type="button" class="history-item" data-history-id="${item.id}" aria-pressed="${item.id === selectedId}">
        <span class="history-icon" aria-hidden="true">${item.icon}</span>
        <span><strong>${item.title}</strong><small>${item.date} · ${item.result}</small></span>
        <span aria-hidden="true">→</span>
      </button>`).join('') : '<p class="decision-empty">이 분류의 기록이 아직 없어요.</p>';
    if (items.length && !items.some((item) => item.id === selectedId)) selectedId = items[0].id;
    renderDetail();
  }

  function renderDetail() {
    const item = selectedItem();
    const currentRating = logic.normalizeRating(ratings[item.id]);
    elements.title.textContent = item.title;
    elements.meta.textContent = `${item.date} · 두 사람 모두 승인`;
    elements.result.textContent = item.result;
    elements.summary.textContent = item.summary;
    elements.buttons.innerHTML = [1, 2, 3, 4, 5].map((rating) => `
      <button type="button" data-rating="${rating}" aria-label="만족도 ${rating}점" aria-pressed="${currentRating === rating}">${rating}<span>♥</span></button>`).join('');
    elements.status.textContent = currentRating
      ? `${currentRating}점 · ${logic.getSatisfactionLabel(currentRating)} (이 브라우저의 테스트 데이터에 저장됨)`
      : logic.getSatisfactionLabel(null);
  }

  elements.filter.addEventListener('change', renderList);
  elements.list.addEventListener('click', (event) => {
    const button = event.target.closest('[data-history-id]');
    if (!button) return;
    selectedId = button.dataset.historyId;
    renderList();
  });
  elements.buttons.addEventListener('click', (event) => {
    const button = event.target.closest('[data-rating]');
    if (button) saveRating(selectedItem().id, button.dataset.rating);
  });
  renderList();
})();
