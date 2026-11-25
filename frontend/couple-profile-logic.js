(function exposeCoupleProfileLogic(root) {
  function maskEmail(email) {
    const [local = '', domain = ''] = String(email || '').split('@');
    if (!domain) return '';
    const visible = local.slice(0, Math.min(2, local.length));
    return `${visible}${'*'.repeat(Math.max(2, local.length - visible.length))}@${domain}`;
  }

  function buildMemberProfiles(couple, currentUserId) {
    const members = Array.isArray(couple?.members) ? couple.members : [];
    return members.map((member) => ({
      id: member.id,
      nickname: member.nickname || '사용자',
      initial: String(member.nickname || '?').slice(0, 1).toUpperCase(),
      email: maskEmail(member.email),
      isMe: member.id === currentUserId,
    }));
  }

  root.TwoPickCoupleProfileLogic = { maskEmail, buildMemberProfiles };
}(typeof window !== 'undefined' ? window : globalThis));
