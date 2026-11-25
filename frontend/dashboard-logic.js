(function exposeDashboardLogic(root) {
  function summarizeDecisions(decisions = [], confirmations = []) {
    const active = decisions.filter((item) => item.status !== 'confirmed').slice(0, 3);
    const confirmedById = new Map(confirmations.map((item) => [item.decision_id, item]));
    const confirmed = decisions
      .filter((item) => item.status === 'confirmed')
      .map((item) => ({ ...item, confirmation: confirmedById.get(item.id) || null }))
      .slice(0, 3);
    return { active, confirmed };
  }

  function upcomingSchedules(items = [], from = new Date()) {
    const parts = new Intl.DateTimeFormat('en-CA', { timeZone: 'Asia/Seoul', year: 'numeric', month: '2-digit', day: '2-digit' }).formatToParts(from).reduce((result, part) => ({ ...result, [part.type]: part.value }), {});
    const start = `${parts.year}-${parts.month}-${parts.day}`;
    return items
      .filter((item) => /^\d{4}-\d{2}-\d{2}$/.test(item.date || '') && item.date >= start)
      .sort((a, b) => a.date.localeCompare(b.date))
      .slice(0, 3);
  }

  root.TwoPickDashboardLogic = { summarizeDecisions, upcomingSchedules };
}(typeof window !== 'undefined' ? window : globalThis));
