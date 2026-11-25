(function exposeHistoryApiLogic(root) {
  function buildHistory(decisions = [], confirmations = [], details = []) {
    const confirmationByDecision = new Map(confirmations.map((item) => [item.decision_id, item]));
    const detailByDecision = new Map(details.map((item) => [item.id, item]));
    return decisions.filter((item) => item.status === 'confirmed').map((decision) => {
      const confirmation = confirmationByDecision.get(decision.id);
      const candidate = detailByDecision.get(decision.id)?.current_candidate;
      if (!confirmation && !candidate) return null;
      return {
        decisionId: decision.id, title: decision.title,
        candidateId: confirmation?.candidate_id ?? candidate?.id,
        version: confirmation?.candidate_version ?? candidate?.version,
        result: confirmation?.content_snapshot ?? candidate?.content,
        confirmedAt: confirmation?.confirmed_at ?? null,
        source: confirmation ? 'confirmation' : 'legacy',
      };
    }).filter(Boolean).sort((a, b) => {
      if (a.confirmedAt && b.confirmedAt) return b.confirmedAt.localeCompare(a.confirmedAt);
      if (a.confirmedAt) return -1;
      if (b.confirmedAt) return 1;
      return b.decisionId - a.decisionId;
    });
  }

  function normalizeFeedback(value) {
    const score = Number(value?.score);
    return { score: Number.isInteger(score) && score >= 1 && score <= 5 ? score : null, comment: typeof value?.comment === 'string' ? value.comment : '' };
  }

  root.TwoPickHistoryApiLogic = { buildHistory, normalizeFeedback };
}(typeof window !== 'undefined' ? window : globalThis));
