(function exposeNotificationLogic(root) {
  function unreadCount(items = [], readIds = []) {
    const read = new Set(readIds.map(String));
    return items.filter((item) => !read.has(String(item.id))).length;
  }

  function markRead(readIds = [], id) {
    return Array.from(new Set([...readIds.map(String), String(id)]));
  }

  function sortNotifications(items = []) {
    return items.slice().sort((a, b) => String(b.created_at).localeCompare(String(a.created_at)));
  }

  root.TwoPickNotificationLogic = { unreadCount, markRead, sortNotifications };
}(typeof window !== 'undefined' ? window : globalThis));
