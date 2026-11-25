(function exposeMockFeaturesLogic(root) {
  function normalizeRating(value) {
    const rating = Number(value);
    return Number.isInteger(rating) && rating >= 1 && rating <= 5 ? rating : null;
  }

  function filterHistory(items, category = 'all') {
    if (!Array.isArray(items)) return [];
    return category === 'all' ? items.slice() : items.filter((item) => item.category === category);
  }

  function getSatisfactionLabel(value) {
    const labels = ['아쉬워요', '조금 아쉬워요', '괜찮았어요', '만족해요', '정말 좋았어요'];
    const rating = normalizeRating(value);
    return rating ? labels[rating - 1] : '아직 평가하지 않았어요';
  }

  root.MockFeaturesLogic = { normalizeRating, filterHistory, getSatisfactionLabel };
}(typeof window !== 'undefined' ? window : globalThis));
