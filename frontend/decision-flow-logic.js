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

  function getRecommendationFallbackState(detail, statuses, attemptedLocally = false, errorMessage = '') {
    const hasCandidate = Boolean(detail?.current_candidate);
    const attempted = attemptedLocally || Boolean(errorMessage);
    const canUseManual = Boolean(detail?.status === 'open' && conditionsReady(statuses));
    if (hasCandidate || !attempted) {
      return { visible: false, canUseManual, tone: 'info', title: '', message: '' };
    }
    return {
      visible: true,
      canUseManual,
      tone: 'warning',
      title: '자동 추천을 완료하지 못했어요.',
      message: errorMessage ? `${errorMessage} 조건 수정과 재추천은 불가능합니다. 수동 후보를 등록하거나 새로운 공동결정을 시작해 주세요.` : '추천 기회가 사용됐지만 적합한 후보가 없습니다. 조건 수정과 재추천은 불가능하며, 수동 후보를 등록하거나 새로운 공동결정을 시작할 수 있어요.',
    };
  }

  function getDecisionStage(detail, statuses, userId) {
    if (detail?.confirmed || detail?.status === 'confirmed') {
      return { key: 'confirmed', index: 3, message: '두 사람의 승인이 모여 최종 결정이 확정됐어요.' };
    }
    if (!conditionsReady(statuses)) {
      const mine = statuses?.member_conditions?.find((item) => item.user_id === userId)?.submitted === true;
      return {
        key: 'conditions',
        index: 0,
        message: mine ? '내 조건은 제출됐어요. 상대방의 비공개 조건 제출을 기다리고 있어요.' :
          '내 비공개 조건을 먼저 저장해 주세요. 상대방에게는 제출 여부만 보여요.',
      };
    }
    if (!detail?.current_candidate) {
      return { key: 'candidate', index: 1, message: '두 사람의 조건이 준비됐어요. 추천을 실행하거나 후보를 직접 등록해 주세요.' };
    }
    const mine = detail.current_candidate.member_approvals?.find((item) => item.user_id === userId)?.approved === true;
    return {
      key: 'approval',
      index: 2,
      message: mine ? '내 승인은 완료됐어요. 상대방이 최신 후보를 승인하면 확정됩니다.' :
        '최신 후보를 확인한 뒤 내 계정에서 직접 승인해 주세요.',
    };
  }

  const logic = { splitTags, makeOptions, canEditConditions, conditionsReady,
    canRecommend, canApprove, getMemberStates, getRecommendationFallbackState, getDecisionStage };
  if (typeof module !== 'undefined' && module.exports) module.exports = logic;
  root.TwoPickDecisionLogic = logic;
}(typeof globalThis !== 'undefined' ? globalThis : this));
