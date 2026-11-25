(function exposeFeatureData(root) {
  const sources = Object.freeze({
    auth: 'api', couple: 'api', decisions: 'api', confirmations: 'api',
    history: 'api', satisfaction: 'api', schedules: 'api', notifications: 'mock',
    petGrowth: 'mock', profileSettings: 'local', notificationSettings: 'local',
  });
  const mockData = Object.freeze({
    history: Object.freeze([
      { id: 'dinner-1', category: 'meal', icon: '🍝', title: '금요일 저녁 메뉴', date: '2026. 11. 20.', result: '동네 파스타 식당', summary: '퇴근 후 가까운 곳에서 천천히 저녁을 먹기로 했어요.' },
      { id: 'weekend-1', category: 'date', icon: '🌿', title: '주말 데이트', date: '2026. 11. 15.', result: '서울숲 산책', summary: '사람이 적은 오전 시간에 만나 따뜻한 음료와 함께 산책했어요.' },
      { id: 'movie-1', category: 'home', icon: '🎬', title: '오늘 볼 영화', date: '2026. 11. 8.', result: '어바웃 타임', summary: '집에서 간단한 간식과 함께 다시 보고 싶던 영화를 골랐어요.' },
    ]),
    schedules: Object.freeze([
      { id: 'seed-1', title: '우리의 첫 만남 기념일', date: '2026-11-26', type: 'anniversary' },
      { id: 'seed-2', title: '겨울 전시회 데이트', date: '2026-11-29', type: 'date' },
      { id: 'seed-3', title: '함께 장보기', date: '2026-12-05', type: 'todo' },
    ]),
    notifications: Object.freeze([
      { id: 'condition', type: 'condition', title: '상대방이 조건을 제출했어요', message: '공동결정 화면에서 후보 추천을 이어갈 수 있어요.', created_at: '2026-11-25T09:30:00', route: 'decision' },
      { id: 'approval', type: 'approval', title: '후보 승인을 기다리고 있어요', message: '최신 후보를 확인하고 내 계정에서 직접 승인해 주세요.', created_at: '2026-11-25T08:40:00', route: 'decision' },
      { id: 'confirmed', type: 'confirmed', title: '두 사람의 결정이 확정됐어요', message: '확정된 선택은 기록 화면에서 다시 볼 수 있어요.', created_at: '2026-11-24T20:15:00', route: 'history' },
      { id: 'schedule', type: 'schedule', title: '내일은 첫 만남 기념일이에요', message: '등록된 일정과 준비할 내용을 확인해 보세요.', created_at: '2026-11-24T09:00:00', route: 'schedule' },
    ]),
    pet: Object.freeze({ level: 3, experience: 65, maximum: 100, name: 'OUR PET' }),
  });

  function getFeatureSource(name) { return sources[name] || 'unknown'; }
  function getMockData(name) {
    const value = mockData[name];
    return value == null ? null : JSON.parse(JSON.stringify(value));
  }

  root.TwoPickFeatureData = { sources, getFeatureSource, getMockData };
}(typeof window !== 'undefined' ? window : globalThis));
