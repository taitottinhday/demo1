const $ = (id) => document.getElementById(id);

const STATUS_NAMES = {
  waiting: 'Đang chờ',
  in_progress: 'Đang xử lý',
  resolved: 'Đã giải quyết',
  rejected: 'Đã từ chối',
  cancelled: 'Đã hủy',
};

const EVENT_NAMES = {
  created: 'Đã tạo yêu cầu',
  claimed: 'Đã nhận xử lý',
  reply: 'Đã gửi phản hồi',
  resolved: 'Đã gửi phản hồi và đóng',
  rejected: 'Đã từ chối yêu cầu',
  cancelled: 'Đã hủy yêu cầu',
  reassigned: 'Đã phân công lại',
};

const state = {
  tickets: [],
  selectedId: '',
  detail: null,
  username: '',
  loading: false,
  refreshing: false,
  actionInProgress: false,
  pollTimer: null,
};

const POLL_INTERVAL_MS = 5000;

function node(tag, className = '', text = '') {
  const element = document.createElement(tag);
  if (className) element.className = className;
  if (text !== '') element.textContent = String(text);
  return element;
}

function formatDate(value) {
  const timestamp = Number(value);
  if (!Number.isFinite(timestamp) || timestamp <= 0) return 'Chưa có dữ liệu';
  return new Date(timestamp * 1000).toLocaleString('vi-VN', {
    dateStyle: 'medium',
    timeStyle: 'short',
  });
}

function formatAge(seconds) {
  const age = Math.max(0, Number(seconds) || 0);
  if (age < 3600) return `${Math.max(1, Math.floor(age / 60))} phút`;
  if (age < 86400) return `${Math.floor(age / 3600)} giờ`;
  return `${Math.floor(age / 86400)} ngày`;
}

function normalizeSearch(value) {
  return String(value || '')
    .toLowerCase()
    .normalize('NFD')
    .replace(/[\u0300-\u036f]/g, '')
    .replaceAll('đ', 'd');
}

function statusBadge(status) {
  return node('span', `badge ${status || ''}`, STATUS_NAMES[status] || 'Không xác định');
}

async function api(path, options = {}) {
  const headers = new Headers(options.headers || {});
  if (options.body && !headers.has('Content-Type')) headers.set('Content-Type', 'application/json');
  const response = await fetch(`/api/v1${path}`, {
    ...options,
    headers,
    credentials: 'include',
  });
  const raw = await response.text();
  let data = {};
  try {
    data = raw ? JSON.parse(raw) : {};
  } catch {
    data = {};
  }
  if (response.status === 401 && !$('dashboard').hidden) {
    showLogin('Phiên đăng nhập đã hết hạn. Vui lòng đăng nhập lại.');
  }
  if (!response.ok) {
    const detail = data.detail;
    const error = new Error(typeof detail === 'string' ? detail : detail?.message || 'Không thể hoàn tất yêu cầu.');
    error.fields = typeof detail === 'object' ? detail.fields || {} : {};
    throw error;
  }
  return data;
}

function showLogin(message = '') {
  stopAutoRefresh();
  $('dashboard').hidden = true;
  $('login-panel').hidden = false;
  $('logout').hidden = true;
  $('staff-identity').hidden = true;
  $('login-error').textContent = message;
}

function showDashboard() {
  $('dashboard').hidden = false;
  $('login-panel').hidden = true;
  $('logout').hidden = false;
  $('staff-identity').hidden = false;
  $('staff-identity').textContent = state.username;
}

function stopAutoRefresh() {
  if (state.pollTimer) {
    window.clearInterval(state.pollTimer);
    state.pollTimer = null;
  }
}

function startAutoRefresh() {
  stopAutoRefresh();
  state.pollTimer = window.setInterval(() => {
    if (document.hidden || state.refreshing || state.actionInProgress) return;
    refreshDashboard(true, true).catch((error) => renderGlobalError(error.message));
  }, POLL_INTERVAL_MS);
}

function hasStaffDraft() {
  return ['staff-reply', 'reject-reason'].some((id) => {
    const field = $(id);
    return field && (document.activeElement === field || field.value.trim());
  });
}

function markLiveUpdated() {
  const status = $('live-status');
  if (status) {
    status.textContent = `Đã cập nhật ${new Date().toLocaleTimeString('vi-VN')} · Tự động mỗi 5 giây`;
  }
}

function setDashboardLoading(loading) {
  state.loading = loading;
  $('dashboard-loading').hidden = !loading;
  $('refresh').disabled = loading;
}

function renderMetrics(metrics = {}) {
  const counts = metrics.tickets || {};
  const cards = [
    ['waiting', 'Đang chờ', 'Ưu tiên xử lý'],
    ['in_progress', 'Đang xử lý', 'Đang có cán bộ phụ trách'],
    ['resolved', 'Đã giải quyết', 'Đã gửi phản hồi'],
    ['rejected', 'Đã từ chối', 'Có lý do kèm theo'],
    ['cancelled', 'Đã hủy', 'Đã đóng bởi ứng viên'],
  ];
  const container = $('metrics');
  container.replaceChildren();
  cards.forEach(([status, label, note]) => {
    const card = node('div', `metric metric-${status}`);
    card.append(node('span', 'metric-label', label), node('b', 'metric-value', counts[status] || 0), node('small', '', note));
    container.append(card);
  });

  const oldest = metrics.ticket_metrics && metrics.ticket_metrics.oldest_waiting;
  const oldestBox = $('oldest-waiting');
  oldestBox.replaceChildren();
  if (oldest) {
    oldestBox.hidden = false;
    oldestBox.append(
      node('span', 'oldest-dot', '●'),
      node('span', '', `Ticket chờ lâu nhất: ${oldest.id}`),
      node('b', '', `${formatAge(oldest.age_seconds)} chưa nhận xử lý`),
    );
  } else {
    oldestBox.hidden = true;
  }
}

function ticketMatches(ticket, query) {
  const content = [ticket.id, ticket.summary, ticket.reason, ticket.owner, ticket.status].join(' ');
  return normalizeSearch(content).includes(query);
}

function sortTickets(tickets) {
  const sort = $('queue-sort').value;
  const status = $('status-filter').value;
  return [...tickets].sort((a, b) => {
    if (!status) {
      const rank = { waiting: 0, in_progress: 1, resolved: 2, rejected: 3, cancelled: 4 };
      const statusDifference = (rank[a.status] ?? 9) - (rank[b.status] ?? 9);
      if (statusDifference) return statusDifference;
    }
    const left = Number(a.created) || 0;
    const right = Number(b.created) || 0;
    return sort === 'oldest' ? left - right : right - left;
  });
}

function staffCanSeeTicket(ticket) {
  // The API remains the authority for access control. This client-side guard
  // prevents an accidentally broad response from exposing another owner's
  // claimed ticket in the queue UI.
  return ticket.status === 'waiting' || !ticket.owner || ticket.owner === state.username;
}

function filteredTickets() {
  const query = normalizeSearch($('queue-search').value);
  const status = $('status-filter').value;
  return sortTickets(state.tickets.filter((ticket) => {
    return staffCanSeeTicket(ticket) && (!status || ticket.status === status) && ticketMatches(ticket, query);
  }));
}

function renderEmptyDetail({ query = '', status = '' } = {}) {
  const detail = $('detail');
  detail.replaceChildren();
  const empty = node('div', 'empty-detail');
  empty.append(node('span', 'empty-detail-icon', query || status ? '⌕' : '✓'));
  empty.append(node('h2', '', 'Chưa có ticket phù hợp'));
  let explanation = 'Ticket mới sẽ xuất hiện tại đây khi ứng viên chuyển yêu cầu và hệ thống ghi nhận thành công.';
  if (query) explanation = `Không có ticket khớp từ khóa “${$('queue-search').value.trim()}” trong bộ lọc hiện tại.`;
  else if (status) explanation = status === 'waiting'
    ? 'Ticket mới sẽ xuất hiện trong hàng chờ “Đang chờ” sau khi ứng viên gửi yêu cầu có đồng ý chuyển cho cán bộ.'
    : 'Ticket mới sẽ xuất hiện trong mục “Đang chờ”; ticket đã nhận chỉ hiện với cán bộ phụ trách.';
  empty.append(node('p', '', explanation));
  detail.append(empty);
}

function queueActionLabel(ticket) {
  if (ticket.status === 'waiting') return 'Nhận xử lý';
  if (ticket.status === 'in_progress') return 'Mở để phản hồi';
  return 'Xem chi tiết';
}

function renderQueue() {
  const container = $('queue');
  const query = normalizeSearch($('queue-search').value);
  const status = $('status-filter').value;
  const filtered = filteredTickets();

  $('queue-count').textContent = `${filtered.length}/${state.tickets.length}`;
  container.replaceChildren();
  if (!filtered.length) {
    const empty = node('div', 'queue-empty');
    empty.append(node('span', 'queue-empty-icon', query || status ? '⌕' : '✓'));
    empty.append(node('strong', '', query ? 'Không tìm thấy ticket' : 'Chưa có ticket phù hợp'));
    empty.append(node('p', '', query
      ? 'Thử từ khóa khác hoặc xóa bộ lọc để xem lại hàng chờ.'
      : 'Ticket mới sẽ xuất hiện trong hàng chờ “Đang chờ” sau khi ứng viên chuyển yêu cầu.'));
    const controls = node('div', 'queue-empty-actions');
    if (query) {
      const clearSearch = node('button', 'secondary small-action', 'Xóa từ khóa');
      clearSearch.type = 'button';
      clearSearch.id = 'clear-search';
      clearSearch.addEventListener('click', () => {
        $('queue-search').value = '';
        renderQueue();
        $('queue-search').focus();
      });
      controls.append(clearSearch);
    }
    if (status) {
      const clearFilter = node('button', 'secondary small-action', 'Xóa bộ lọc');
      clearFilter.type = 'button';
      clearFilter.id = 'clear-filter';
      clearFilter.addEventListener('click', () => {
        $('status-filter').value = '';
        renderQueue();
        $('status-filter').focus();
      });
      controls.append(clearFilter);
    }
    if (controls.children.length) empty.append(controls);
    container.append(empty);
    if (!hasStaffDraft()) {
      state.selectedId = '';
      state.detail = null;
      renderEmptyDetail({ query, status });
    }
    return;
  }

  const selectedIsVisible = filtered.some((ticket) => ticket.id === state.selectedId);
  if (state.selectedId && !selectedIsVisible && !hasStaffDraft()) {
    state.selectedId = '';
    state.detail = null;
    renderEmptyDetail({ query, status });
  }

  filtered.forEach((ticket) => {
    const item = node('button', `queue-item${ticket.id === state.selectedId ? ' selected' : ''}`);
    item.type = 'button';
    item.setAttribute('aria-current', ticket.id === state.selectedId ? 'true' : 'false');
    const header = node('div', 'ticket-head');
    header.append(node('b', 'ticket-id', ticket.id), statusBadge(ticket.status));
    item.append(header);
    item.append(node('p', 'ticket-summary', ticket.summary || 'Không có nội dung tóm tắt.'));
    const meta = node('div', 'ticket-meta');
    meta.append(node('span', '', `Cập nhật ${formatDate(ticket.updated || ticket.created)}`));
    meta.append(node('span', 'ticket-owner', `Phụ trách: ${ticket.owner || 'Chưa nhận'}`));
    item.append(meta);
    item.append(node('span', 'queue-item-action', queueActionLabel(ticket)));
    item.addEventListener('click', () => selectTicket(ticket.id));
    container.append(item);
  });
}

function renderDetailLoading() {
  const detail = $('detail');
  detail.replaceChildren();
  const loading = node('div', 'detail-loading');
  loading.append(node('span', 'loading-spinner'), node('p', '', 'Đang tải chi tiết ticket…'));
  detail.append(loading);
}

function appendField(container, label, value, className = '') {
  const field = node('div', `detail-field ${className}`);
  field.append(node('dt', '', label), node('dd', '', value || 'Chưa có dữ liệu'));
  container.append(field);
}

function appendSection(container, title, value, className = '') {
  const section = node('section', `detail-section ${className}`);
  section.append(node('h3', '', title), node('div', 'detail-content', value || 'Chưa có dữ liệu.'));
  container.append(section);
}

function optionalValue(ticket, detail, keys) {
  for (const source of [detail, ticket]) {
    for (const key of keys) {
      if (source && source[key]) return source[key];
    }
  }
  return '';
}

function valueText(value) {
  if (Array.isArray(value)) {
    return value.map((item) => typeof item === 'string' ? item : (item.title || item.name || item.url || '')).filter(Boolean).join('\n');
  }
  if (value && typeof value === 'object') return value.text || value.content || value.response || '';
  return String(value || '');
}

function appendActions(container, ticket) {
  const actions = node('div', 'ticket-actions');
  const error = node('p', 'error-text action-error');
  error.setAttribute('role', 'alert');

  if (ticket.status === 'waiting') {
    const claim = node('button', 'primary action-button', 'Nhận xử lý ticket →');
    claim.type = 'button';
    claim.addEventListener('click', () => performAction(ticket.id, claim, 'claim'));
    actions.append(node('p', 'action-hint', 'Nhận ticket để trở thành cán bộ phụ trách.'), claim);
  } else if (ticket.status === 'in_progress' && ticket.owner === state.username) {
    const replyLabel = node('label', 'action-label', 'Phản hồi cho ứng viên');
    const reply = node('textarea', 'action-textarea');
    reply.id = 'staff-reply';
    replyLabel.htmlFor = reply.id;
    reply.maxLength = 4000;
    reply.placeholder = 'Nhập phản hồi dựa trên thông tin đã kiểm tra…';
    const resolve = node('button', 'primary action-button', 'Gửi phản hồi và đóng');
    resolve.type = 'button';
    resolve.addEventListener('click', () => performAction(ticket.id, resolve, 'resolve', reply.value, error));
    actions.append(replyLabel, reply, node('p', 'action-hint', 'Phản hồi sẽ được gửi vào phiên của ứng viên.'), resolve);
  } else if (ticket.status === 'in_progress') {
    actions.append(node('div', 'locked-notice', `Ticket đang được cán bộ ${ticket.owner || 'khác'} xử lý.`));
  }

  if (ticket.status === 'waiting' || (ticket.status === 'in_progress' && ticket.owner === state.username)) {
    const rejectLabel = node('label', 'action-label reject-label', 'Lý do từ chối');
    const rejectReason = node('textarea', 'action-textarea reject-textarea');
    rejectReason.id = 'reject-reason';
    rejectLabel.htmlFor = rejectReason.id;
    rejectReason.maxLength = 4000;
    rejectReason.placeholder = 'Nêu rõ lý do để ứng viên biết hướng xử lý tiếp theo…';
    const reject = node('button', 'secondary danger action-button', 'Từ chối yêu cầu');
    reject.type = 'button';
    reject.addEventListener('click', () => {
      if (!rejectReason.value.trim()) {
        error.textContent = 'Vui lòng nhập lý do từ chối.';
        rejectReason.focus();
        return;
      }
      if (window.confirm('Từ chối ticket và gửi lý do cho ứng viên?')) {
        performAction(ticket.id, reject, 'reject', rejectReason.value, error);
      }
    });
    actions.append(rejectLabel, rejectReason, reject);
  }

  if (actions.children.length) {
    actions.append(error);
    container.append(actions);
  }
}

async function performAction(ticketId, button, action, reply = '', errorNode = null) {
  if ((action === 'resolve' || action === 'reject') && !reply.trim()) {
    if (errorNode) errorNode.textContent = action === 'resolve' ? 'Vui lòng nhập phản hồi.' : 'Vui lòng nhập lý do từ chối.';
    return;
  }
  const actionButtons = [...$('detail').querySelectorAll('button, textarea')];
  const originalLabel = button.textContent;
  const loadingLabels = {
    claim: 'Đang nhận ticket…',
    resolve: 'Đang gửi phản hồi…',
    reject: 'Đang từ chối…',
  };
  actionButtons.forEach((element) => { element.disabled = true; });
  button.classList.add('is-loading');
  button.setAttribute('aria-busy', 'true');
  button.textContent = loadingLabels[action] || 'Đang xử lý…';
  if (errorNode) errorNode.textContent = '';
  state.actionInProgress = true;
  try {
    const body = action === 'claim' ? undefined : JSON.stringify({ reply: reply.trim() });
    await api(`/staff/tickets/${encodeURIComponent(ticketId)}/${action}`, { method: 'POST', body });
    await refreshDashboard(false);
    await selectTicket(ticketId);
  } catch (error) {
    if (errorNode) errorNode.textContent = error.message;
    else renderGlobalError(error.message);
    button.classList.remove('is-loading');
    button.removeAttribute('aria-busy');
    button.textContent = originalLabel;
    actionButtons.forEach((element) => { element.disabled = false; });
  } finally {
    state.actionInProgress = false;
  }
}

function renderDetail(detail) {
  const ticket = detail.ticket || detail;
  const container = $('detail');
  container.replaceChildren();

  const header = node('div', 'detail-header');
  const titleGroup = node('div');
  titleGroup.append(node('p', 'section-label', 'CHI TIẾT TICKET'), node('h2', '', ticket.id));
  header.append(titleGroup, statusBadge(ticket.status));
  container.append(header);

  const fields = node('dl', 'detail-fields');
  appendField(fields, 'Người phụ trách', ticket.owner || 'Chưa nhận xử lý');
  appendField(fields, 'Thời gian tạo', formatDate(ticket.created));
  appendField(fields, 'Cập nhật gần nhất', formatDate(ticket.updated));
  container.append(fields);

  appendSection(container, 'Nội dung ứng viên đồng ý chia sẻ', detail.shared_content || ticket.summary);
  appendSection(container, 'Lý do chuyển cán bộ', ticket.reason, 'muted-section');

  const original = valueText(optionalValue(ticket, detail, ['original_question', 'question', 'context', 'context_text']));
  const aiAnswer = valueText(optionalValue(ticket, detail, ['ai_answer', 'ai_response', 'answer', 'response']));
  const sources = valueText(optionalValue(ticket, detail, ['sources', 'related_sources', 'source']));
  appendSection(container, 'Câu hỏi gốc / ngữ cảnh', original || 'Backend hiện chưa cung cấp ngữ cảnh bổ sung.');
  appendSection(container, 'Câu trả lời AI và nguồn liên quan', [aiAnswer, sources ? `Nguồn:\n${sources}` : ''].filter(Boolean).join('\n\n') || 'Backend hiện chưa cung cấp câu trả lời AI hoặc nguồn liên quan.');

  if (ticket.reply) appendSection(container, ticket.status === 'rejected' ? 'Lý do từ chối' : 'Phản hồi đã gửi', ticket.reply, 'reply-section');
  appendActions(container, ticket);

  if (Array.isArray(detail.events) && detail.events.length) {
    const history = node('section', 'detail-section event-history');
    history.append(node('h3', '', 'Lịch sử xử lý'));
    const list = node('ol', 'event-list');
    detail.events.forEach((event) => {
      const item = node('li');
      item.append(node('span', 'event-action', EVENT_NAMES[event.action] || event.action));
      item.append(node('small', '', `${formatDate(event.created)}${event.actor ? ` · ${event.actor}` : ''}`));
      list.append(item);
    });
    history.append(list);
    container.append(history);
  }
}

async function selectTicket(ticketId, silent = false) {
  state.selectedId = ticketId;
  renderQueue();
  if (!silent) renderDetailLoading();
  try {
    const detail = await api(`/staff/tickets/${encodeURIComponent(ticketId)}`);
    if (state.selectedId !== ticketId) return;
    state.detail = detail;
    renderDetail(detail);
  } catch (error) {
    if (state.selectedId === ticketId) {
      $('detail').replaceChildren(node('p', 'error-state', error.message));
    }
  }
}

function renderGlobalError(message) {
  $('staff-error').textContent = message || '';
}

async function refreshDashboard(keepDetail = true, silent = false) {
  if (state.refreshing) return;
  state.refreshing = true;
  if (!silent) {
    renderGlobalError('');
    setDashboardLoading(true);
  }
  try {
    const [tickets, metrics] = await Promise.all([api('/staff/tickets'), api('/staff/metrics')]);
    state.tickets = Array.isArray(tickets) ? tickets : [];
    renderMetrics(metrics);
    renderQueue();
    markLiveUpdated();
    if (keepDetail && state.selectedId && !(silent && hasStaffDraft())) {
      await selectTicket(state.selectedId, silent);
    } else if (!state.selectedId) {
      renderEmptyDetail({ query: normalizeSearch($('queue-search').value), status: $('status-filter').value });
    }
  } catch (error) {
    renderGlobalError(error.message);
  } finally {
    state.refreshing = false;
    if (!silent) setDashboardLoading(false);
  }
}

async function login(event) {
  event.preventDefault();
  const username = $('username').value.trim();
  const password = $('password').value;
  $('login-error').textContent = '';
  $('username-error').textContent = '';
  $('password-error').textContent = '';
  $('username').removeAttribute('aria-invalid');
  $('password').removeAttribute('aria-invalid');
  if (!username || !password) {
    const first = !username ? $('username') : $('password');
    first.setAttribute('aria-invalid', 'true');
    $(`${first.id}-error`).textContent = !username ? 'Tài khoản là bắt buộc.' : 'Mật khẩu là bắt buộc.';
    first.focus();
    return;
  }
  const button = $('login-submit');
  button.disabled = true;
  button.querySelector('.button-label').textContent = 'Đang đăng nhập…';
  try {
    const user = await api('/staff/login', { method: 'POST', body: JSON.stringify({ username, password }) });
    state.username = user.username || username;
    $('password').value = '';
    showDashboard();
    await refreshDashboard(false);
    startAutoRefresh();
  } catch (error) {
    if (error.fields?.username || error.fields?.password) {
      const first = error.fields.username ? $('username') : $('password');
      first.setAttribute('aria-invalid', 'true');
      $(`${first.id}-error`).textContent = error.fields[first.name];
      first.focus();
    } else $('login-error').textContent = error.message;
  } finally {
    button.disabled = false;
    button.querySelector('.button-label').textContent = 'Đăng nhập';
  }
}

$('login-form').addEventListener('submit', login);
$('logout').addEventListener('click', async () => {
  $('logout').disabled = true;
  try {
    await api('/staff/logout', { method: 'POST' });
    window.location.reload();
  } catch (error) {
    $('logout').disabled = false;
    renderGlobalError(error.message);
  }
});

$('toggle-password').addEventListener('click', () => {
  const input = $('password');
  const visible = input.type === 'text';
  input.type = visible ? 'password' : 'text';
  $('toggle-password').textContent = visible ? 'Hiện' : 'Ẩn';
  $('toggle-password').setAttribute('aria-label', visible ? 'Hiện mật khẩu' : 'Ẩn mật khẩu');
});

$('refresh').addEventListener('click', () => refreshDashboard(true));
$('status-filter').addEventListener('change', renderQueue);
$('queue-sort').addEventListener('change', renderQueue);
$('queue-search').addEventListener('input', renderQueue);

const loginError = new URLSearchParams(window.location.search).get('login_error');
if (loginError) $('login-error').textContent = decodeURIComponent(loginError.replaceAll('+', ' '));

(async () => {
  try {
    const me = await api('/staff/me');
    state.username = me.username || '';
    showDashboard();
    await refreshDashboard(false);
    startAutoRefresh();
  } catch {
    // The login panel is the expected state for an unauthenticated visitor.
  }
})();
