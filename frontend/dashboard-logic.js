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
    const start = new Date(from.getFullYear(), from.getMonth(), from.getDate());
    return items
      .filter((item) => /^\d{4}-\d{2}-\d{2}$/.test(item.date || '') && new Date(`${item.date}T00:00:00`) >= start)
      .sort((a, b) => a.date.localeCompare(b.date))
      .slice(0, 3);
  }

  root.TwoPickDashboardLogic = { summarizeDecisions, upcomingSchedules };
}(typeof window !== 'undefined' ? window : globalThis));
