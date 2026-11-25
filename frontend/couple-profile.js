(() => {
  'use strict';
  const logic = globalThis.TwoPickCoupleProfileLogic;
  const root = document.querySelector('.couple-profile-panel');
  if (!logic || !root) return;
  const ui = {
    status: root.querySelector('#profile-couple-status'), members: root.querySelector('#couple-profile-members'),
    code: root.querySelector('#profile-invite-code'), copy: root.querySelector('#copy-profile-invite'),
  };

  function escapeHtml(value) {
    return String(value).replace(/[&<>'"]/g, (character) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', "'": '&#39;', '"': '&quot;' }[character]));
  }

  function render() {
    if (!state.user || !state.couple) {
      ui.members.innerHTML = '<p class="decision-empty">커플 연결 후 프로필을 확인할 수 있어요.</p>';
      ui.code.textContent = '-';
      return;
    }
    const profiles = logic.buildMemberProfiles(state.couple, state.user.id);
    const connected = profiles.length === 2;
    ui.status.classList.toggle('online', connected);
    ui.status.innerHTML = `<i></i> ${connected ? '두 사람 연결됨' : '상대 대기'}`;
    ui.code.textContent = state.couple.invite_code || '-';
    ui.copy.disabled = !state.couple.invite_code;
    ui.members.innerHTML = profiles.map((profile) => `<article class="couple-member-card ${profile.isMe ? 'me' : ''}"><span class="couple-member-avatar">${escapeHtml(profile.initial)}</span><div><small>${profile.isMe ? '나' : '상대방'}</small><strong>${escapeHtml(profile.nickname)}</strong><p>${escapeHtml(profile.email)}</p></div><i>${profile.isMe ? 'MY PROFILE' : 'PARTNER'}</i></article>`).join('') + (!connected ? '<article class="couple-member-card waiting"><span class="couple-member-avatar">?</span><div><small>상대방</small><strong>연결을 기다리고 있어요</strong><p>초대 코드를 전달해 주세요.</p></div></article>' : '');
  }

  ui.copy.addEventListener('click', async () => {
    try {
      await navigator.clipboard.writeText(state.couple.invite_code);
      showAlert('커플 연결 코드를 복사했습니다.', true);
    } catch (_) {
      showAlert(`연결 코드: ${state.couple.invite_code}`);
    }
  });
  window.addEventListener('twopick:session-changed', render);
  render();
})();
