/* Shared, framework-free UI data rules; available in a browser and Node tests. */
(function setupTwoPickDecisionLogic(root) {
  'use strict';

  function splitTags(raw) {
    if (typeof raw !== 'string') throw new Error('태그는 문자열이어야 해요.');
    const seen = new Set();
    const tags = [];
    for (const piece of raw.split(/[,;\n]/)) {
      const text = piece.trim();
      if (!text) continue;
      if (text.length > 60) throw new Error('태그는 60자 이하로 입력해 주세요.');
      const key = text.toLocaleLowerCase();
      if (seen.has(key)) throw new Error('같은 태그가 중복되어 있어요.');
      seen.add(key);
      tags.push(text);
    }
    if (tags.length > 12) throw new Error('후보 태그는 최대 12개까지 입력할 수 있어요.');
    return tags;
  }

  function makeOptions(rows) {
    if (!Array.isArray(rows) || rows.length < 2 || rows.length > 8) {
      throw new Error('추천 후보는 2~8개 입력해 주세요.');
    }
    const seenTitles = new Set();
    return rows.map((row) => {
      const title = String(row.title ?? '').trim();
      const slot = String(row.time_slot ?? '').trim();
      const costInput = String(row.estimated_total_cost_krw ?? '').trim();
      if (!title || title.length > 180) throw new Error('후보 이름은 1~180자로 입력해 주세요.');
      if (!slot || slot.length > 100) throw new Error('시간 슬롯은 1~100자로 입력해 주세요.');
      if (!/^\d+$/.test(costInput)) throw new Error('2인 총액은 0 이상의 정수로 입력해 주세요.');
      const cost = Number(costInput);
      if (!Number.isSafeInteger(cost) || cost > 1_000_000_000) {
        throw new Error('2인 총액은 10억 원 이하로 입력해 주세요.');
      }
      const key = title.toLocaleLowerCase();
      if (seenTitles.has(key)) throw new Error('후보 이름이 중복되어 있어요.');
      seenTitles.add(key);
      return {
        title,
        estimated_total_cost_krw: cost,
        time_slot: slot,
        tags: splitTags(String(row.tags ?? '')),
      };
    });
  }

  function canEditConditions(detail) {
    return Boolean(detail && detail.status === 'open' && !detail.current_candidate);
  }

  function conditionsReady(status) {
    return Boolean(status && status.member_conditions?.length === 2 &&
      status.member_conditions.every((item) => item.submitted === true));
  }

  function canRecommend(detail, status, attemptedLocally = false) {
    return canEditConditions(detail) && conditionsReady(status) && !attemptedLocally;
  }

  function canApprove(detail, userId) {
    const candidate = detail?.current_candidate;
    if (!candidate || detail.status !== 'open' || detail.confirmed) return false;
    const entry = candidate.member_approvals?.find((item) => item.user_id === userId);
    return Boolean(entry && !entry.approved);
  }

  function getMemberStates(members, statuses) {
    const submitted = new Map((statuses?.member_conditions || []).map(
      (entry) => [entry.user_id, entry.submitted],
    ));
    return members.map((member) => ({
      id: member.id,
      nickname: member.nickname,
      submitted: submitted.get(member.id) === true,
    }));
  }

  const logic = { splitTags, makeOptions, canEditConditions, conditionsReady,
    canRecommend, canApprove, getMemberStates };
  if (typeof module !== 'undefined' && module.exports) module.exports = logic;
  root.TwoPickDecisionLogic = logic;
}(typeof globalThis !== 'undefined' ? globalThis : this));
