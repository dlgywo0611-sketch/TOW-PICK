const state = {
  token: sessionStorage.getItem('tow_pick_token'),
  user: null,
  couple: null,
};

const elements = {
  alert: document.querySelector('#alert'),
  authView: document.querySelector('#auth-view'),
  coupleView: document.querySelector('#couple-view'),
  loginForm: document.querySelector('#login-form'),
  signupForm: document.querySelector('#signup-form'),
  joinForm: document.querySelector('#join-form'),
  createCoupleButton: document.querySelector('#create-couple-button'),
  logoutButton: document.querySelector('#logout-button'),
  profileName: document.querySelector('#profile-name'),
  profileAvatar: document.querySelector('#profile-avatar'),
  navCouple: document.querySelector('#nav-couple'),
  coupleStatus: document.querySelector('#couple-status'),
  connectionActions: document.querySelector('#connection-actions'),
  inviteCode: document.querySelector('#invite-code'),
  connectedCard: document.querySelector('#connected-card'),
  connectedTitle: document.querySelector('#connected-title'),
  connectedCode: document.querySelector('#connected-code'),
  memberA: document.querySelector('#member-a'),
  memberB: document.querySelector('#member-b'),
  connectUsb: document.querySelector('#connect-usb'),
  connectBle: document.querySelector('#connect-ble'),
  petdockStatus: document.querySelector('#petdock-status'),
  petEvent: document.querySelector('#pet-event'),
  ledControls: document.querySelector('#led-controls'),
};

const petDock = new PetDockBridge();
const deviceState = { usb: false, ble: false };

const errorMessages = {
  'Incorrect email or password': '이메일 또는 비밀번호가 올바르지 않습니다.',
  'Email already registered': '이미 가입된 이메일입니다.',
  'Invite code not found': '초대 코드를 찾을 수 없습니다.',
  'User already belongs to a couple': '이미 커플에 연결된 계정입니다.',
  'Couple already has two members': '이미 두 명이 연결된 커플입니다.',
  'User does not belong to a couple': '아직 커플에 연결되지 않았습니다.',
  'Could not validate credentials': '로그인이 만료되었습니다. 다시 로그인해 주세요.',
  'Token has been revoked': '로그아웃된 세션입니다. 다시 로그인해 주세요.',
};

function showAlert(message, success = false) {
  elements.alert.textContent = message;
  elements.alert.classList.remove('hidden', 'success');
  if (success) elements.alert.classList.add('success');
}

function hideAlert() {
  elements.alert.classList.add('hidden');
}

function renderDeviceState() {
  const connected = deviceState.usb || deviceState.ble;
  const labels = [deviceState.usb && 'USB', deviceState.ble && 'BLE'].filter(Boolean);
  elements.petdockStatus.classList.toggle('online', connected);
  elements.petdockStatus.innerHTML = `<i></i> ${connected ? `${labels.join(' + ')} 연결됨` : '연결 대기'}`;
  elements.connectUsb.textContent = deviceState.usb ? 'USB 연결됨' : 'USB 연결';
  elements.connectUsb.disabled = deviceState.usb;
  elements.connectBle.textContent = deviceState.ble ? '블루투스 연결됨' : '블루투스 연결';
  elements.connectBle.disabled = deviceState.ble;
  elements.ledControls.querySelectorAll('button').forEach((button) => {
    button.disabled = !deviceState.ble;
  });
}

function setButtonBusy(button, busy, label) {
  if (!button.dataset.label) button.dataset.label = button.innerHTML;
  button.disabled = busy;
  button.textContent = busy ? label : '';
  if (!busy) button.innerHTML = button.dataset.label;
}

async function api(path, options = {}) {
  const headers = new Headers(options.headers || {});
  if (state.token) headers.set('Authorization', `Bearer ${state.token}`);
  if (options.body && !(options.body instanceof URLSearchParams)) {
    headers.set('Content-Type', 'application/json');
  }

  const response = await fetch(path, { ...options, headers });
  if (!response.ok) {
    const payload = await response.json().catch(() => ({}));
    const detail = payload.detail || '요청을 처리하지 못했습니다.';
    throw new Error(errorMessages[detail] || detail);
  }
  return response.status === 204 ? null : response.json();
}

function saveToken(token) {
  state.token = token;
  sessionStorage.setItem('tow_pick_token', token);
}

function clearSession() {
  state.token = null;
  state.user = null;
  state.couple = null;
  sessionStorage.removeItem('tow_pick_token');
}

function render() {
  const authenticated = Boolean(state.user);
  elements.authView.classList.toggle('hidden', authenticated);
  elements.coupleView.classList.toggle('hidden', !authenticated);
  elements.logoutButton.classList.toggle('hidden', !authenticated);
  elements.navCouple.classList.toggle('active', authenticated);
  document.querySelector('.step:first-child').classList.toggle('complete', authenticated);
  document.querySelector('.step:first-child').classList.toggle('active', !authenticated);

  if (!authenticated) return;
  elements.profileName.textContent = state.user.nickname;
  elements.profileAvatar.textContent = state.user.nickname.slice(0, 1).toUpperCase();

  const connected = Boolean(state.couple && state.couple.members.length >= 2);
  const hasCouple = Boolean(state.couple);
  elements.connectionActions.classList.toggle('hidden', hasCouple);
  elements.connectedCard.classList.toggle('hidden', !hasCouple);
  elements.coupleStatus.classList.toggle('online', connected);
  elements.coupleStatus.innerHTML = `<i></i> ${connected ? '연결됨' : hasCouple ? '상대 대기' : '연결 전'}`;

  if (!hasCouple) return;
  const me = state.couple.members.find((member) => member.id === state.user.id) || state.user;
  const partner = state.couple.members.find((member) => member.id !== state.user.id);
  elements.memberA.textContent = me.nickname.slice(0, 1);
  elements.memberB.textContent = partner ? partner.nickname.slice(0, 1) : '?';
  elements.connectedTitle.textContent = partner
    ? `${me.nickname}님과 ${partner.nickname}님이 연결됐어요.`
    : '초대 코드를 상대방에게 전달해 주세요.';
  elements.connectedCode.textContent = state.couple.invite_code;
}

async function loadCurrentSession() {
  if (!state.token) return render();
  try {
    state.user = await api('/users/me');
    try {
      state.couple = await api('/couples/me');
    } catch (error) {
      if (error.message !== errorMessages['User does not belong to a couple']) throw error;
    }
  } catch (error) {
    clearSession();
    showAlert(error.message);
  }
  render();
}

elements.loginForm.addEventListener('submit', async (event) => {
  event.preventDefault();
  hideAlert();
  const button = event.submitter;
  setButtonBusy(button, true, '로그인 중…');
  const formData = new FormData(elements.loginForm);
  const body = new URLSearchParams({ username: formData.get('email'), password: formData.get('password') });
  try {
    const result = await api('/token', { method: 'POST', body });
    saveToken(result.access_token);
    await loadCurrentSession();
    showAlert('로그인되었습니다.', true);
  } catch (error) {
    showAlert(error.message);
  } finally {
    setButtonBusy(button, false, '');
  }
});

elements.signupForm.addEventListener('submit', async (event) => {
  event.preventDefault();
  hideAlert();
  const button = event.submitter;
  setButtonBusy(button, true, '계정 만드는 중…');
  const formData = new FormData(elements.signupForm);
  try {
    await api('/users', {
      method: 'POST',
      body: JSON.stringify({ email: formData.get('email'), nickname: formData.get('nickname'), password: formData.get('password') }),
    });
    elements.loginForm.email.value = formData.get('email');
    elements.loginForm.password.focus();
    showAlert('계정을 만들었습니다. 왼쪽에서 로그인해 주세요.', true);
  } catch (error) {
    showAlert(error.message);
  } finally {
    setButtonBusy(button, false, '');
  }
});

elements.createCoupleButton.addEventListener('click', async () => {
  hideAlert();
  setButtonBusy(elements.createCoupleButton, true, '만드는 중…');
  try {
    state.couple = await api('/couples', { method: 'POST' });
    elements.inviteCode.textContent = state.couple.invite_code;
    elements.inviteCode.classList.add('ready');
    showAlert('초대 코드를 만들었습니다. 상대방에게 전달해 주세요.', true);
    render();
  } catch (error) {
    showAlert(error.message);
  } finally {
    setButtonBusy(elements.createCoupleButton, false, '');
  }
});

elements.joinForm.addEventListener('submit', async (event) => {
  event.preventDefault();
  hideAlert();
  const button = event.submitter;
  setButtonBusy(button, true, '연결 중…');
  const formData = new FormData(elements.joinForm);
  try {
    state.couple = await api('/couples/join', {
      method: 'POST',
      body: JSON.stringify({ invite_code: formData.get('invite_code').trim().toUpperCase() }),
    });
    showAlert('커플 연결이 완료됐습니다.', true);
    render();
  } catch (error) {
    showAlert(error.message);
  } finally {
    setButtonBusy(button, false, '');
  }
});

elements.logoutButton.addEventListener('click', async () => {
  hideAlert();
  try {
    await api('/logout', { method: 'POST' });
  } catch (error) {
    // 로컬 세션은 서버 응답과 관계없이 정리한다.
  }
  clearSession();
  render();
  showAlert('로그아웃되었습니다.', true);
});

elements.connectUsb.addEventListener('click', async () => {
  hideAlert();
  setButtonBusy(elements.connectUsb, true, '연결 중…');
  try {
    await petDock.connectUsb();
    showAlert('Arduino USB가 연결되었습니다.', true);
  } catch (error) {
    showAlert(error.message);
  } finally {
    if (!deviceState.usb) setButtonBusy(elements.connectUsb, false, '');
  }
});

elements.connectBle.addEventListener('click', async () => {
  hideAlert();
  setButtonBusy(elements.connectBle, true, '검색 중…');
  try {
    await petDock.connectBluetooth();
    showAlert('Meem 블루투스가 연결되었습니다.', true);
  } catch (error) {
    showAlert(error.message);
  } finally {
    if (!deviceState.ble) setButtonBusy(elements.connectBle, false, '');
  }
});

elements.ledControls.addEventListener('click', async (event) => {
  const button = event.target.closest('[data-led]');
  if (!button) return;
  hideAlert();
  try {
    await petDock.setLed(button.dataset.led);
  } catch (error) {
    showAlert(error.message);
  }
});

petDock.addEventListener('usbstate', (event) => {
  deviceState.usb = event.detail.connected;
  renderDeviceState();
});

petDock.addEventListener('blestate', (event) => {
  deviceState.ble = event.detail.connected;
  renderDeviceState();
});

petDock.addEventListener('button', (event) => {
  elements.petEvent.textContent = event.detail.button === 'A'
    ? '펫 반응 요청 (버튼 A)'
    : '펫 상태 확인 (버튼 B)';
});

petDock.addEventListener('led', (event) => {
  const colorNames = { red: '빨강', green: '초록', blue: '파랑', off: '꺼짐' };
  elements.petEvent.textContent = `LED 상태: ${colorNames[event.detail.color]}`;
});

petDock.addEventListener('error', (event) => showAlert(event.detail.message));

renderDeviceState();
loadCurrentSession();
