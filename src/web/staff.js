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

const ACTION_STATUS_FILTERS = {
  claim: 'in_progress',
  resolve: 'resolved',
  reject: 'rejected',
};

const state = {
  tickets: [],
  selectedId: '',
  detail: null,
  username: '',
  loading: false,
  refreshing: false,
  actionInProgress: false,
};


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
  $('staff-identity').dataset.initial = (state.username || '?').trim().charAt(0).toUpperCase();
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
    status.textContent = `Cập nhật lúc ${new Date().toLocaleTimeString('vi-VN')}`;
  }
}

function setDashboardLoading(loading) {
  state.loading = loading;
  $('dashboard-loading').hidden = !loading;
  $('refresh').disabled = loading;
}

const STATUS_TABS = [
  ['waiting', 'Đang chờ'],
  ['in_progress', 'Đang xử lý'],
  ['resolved', 'Đã giải quyết'],
  ['rejected', 'Từ chối'],
  ['cancelled', 'Đã hủy'],
  ['', 'Tất cả'],
];

function syncStatusTabs() {
  const current = $('status-filter').value;
  $('metrics').querySelectorAll('[data-status]').forEach((tab) => {
    tab.setAttribute('aria-pressed', String(tab.dataset.status === current));
  });
}

function renderMetrics(metrics = {}) {
  const counts = metrics.tickets || {};
  const total = Object.values(counts).reduce((sum, value) => sum + (Number(value) || 0), 0);
  const container = $('metrics');
  container.replaceChildren();
  STATUS_TABS.forEach(([status, label]) => {
    const tab = node('button', `status-tab status-${status || 'all'}`);
    tab.type = 'button';
    tab.dataset.status = status;
    const count = status ? counts[status] || 0 : total;
    tab.append(node('span', 'status-tab-dot'), node('span', '', label), node('span', 'status-tab-count', count));
    tab.addEventListener('click', () => {
      $('status-filter').value = status;
      renderQueueAndSelectFirst();
    });
    container.append(tab);
  });
  syncStatusTabs();

  const oldest = metrics.ticket_metrics && metrics.ticket_metrics.oldest_waiting;
  const oldestBox = $('oldest-waiting');
  oldestBox.replaceChildren();
  if (oldest) {
    oldestBox.hidden = false;
    const open = node('button', 'desk-alert-button');
    open.type = 'button';
    const alertText = `${oldest.id} chờ ${formatAge(oldest.age_seconds)} chưa nhận`;
    open.title = `Ticket chờ lâu nhất: ${alertText}`;
    open.append(node('span', 'desk-alert-dot'), node('span', '', alertText));
    open.addEventListener('click', () => {
      $('status-filter').value = 'waiting';
      renderQueue();
      void selectTicket(oldest.id);
    });
    oldestBox.append(open);
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

  $('queue-count').textContent = `${filtered.length} ticket${query ? ' khớp tìm kiếm' : ''}`;
  syncStatusTabs();
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

  const now = Date.now() / 1000;
  filtered.forEach((ticket) => {
    const item = node('button', `queue-item${ticket.id === state.selectedId ? ' selected' : ''}`);
    item.type = 'button';
    item.setAttribute('aria-current', ticket.id === state.selectedId ? 'true' : 'false');
    const top = node('span', 'ticket-head');
    const updated = Number(ticket.updated || ticket.created) || now;
    const age = node('time', 'ticket-age', formatAge(now - updated));
    age.title = formatDate(updated);
    top.append(node('span', `ticket-dot ${ticket.status || ''}`), node('b', 'ticket-id', ticket.id), age);
    const meta = node('span', 'ticket-meta');
    meta.append(statusBadge(ticket.status), node('span', 'ticket-owner', ticket.owner ? `Phụ trách: ${ticket.owner}` : 'Chưa có người nhận'));
    item.append(top, node('span', 'ticket-summary', ticket.summary || 'Không có nội dung tóm tắt.'), meta);
    item.addEventListener('click', () => selectTicket(ticket.id));
    container.append(item);
  });
}

function renderQueueAndSelectFirst() {
  renderQueue();
  if (state.selectedId || hasStaffDraft()) return;
  const first = filteredTickets()[0];
  if (first) void selectTicket(first.id);
}

function renderDetailLoading() {
  const detail = $('detail');
  detail.replaceChildren();
  const loading = node('div', 'detail-loading');
  loading.append(node('span', 'loading-spinner'), node('p', '', 'Đang tải chi tiết ticket…'));
  detail.append(loading);
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
  const canReject = ticket.status === 'waiting' || (ticket.status === 'in_progress' && ticket.owner === state.username);
  const row = node('div', 'action-row');

  if (ticket.status === 'resolved' && ticket.owner === state.username) {
    const emailState = ticket.email_status || 'not_applicable';
    const labels = {
      sent: 'Đã lưu phản hồi · Email thông báo đã được nhà cung cấp chấp nhận.',
      pending: 'Đã lưu phản hồi · Email thông báo đang chờ gửi.',
      sending: 'Đã lưu phản hồi · Đang gửi email thông báo.',
      failed: 'Đã lưu phản hồi · Gửi email thất bại; có thể gửi lại thông báo.',
      skipped: 'Đã lưu phản hồi · Không gửi email vì tài khoản không có email hợp lệ đã xác minh.',
    };
    if (labels[emailState]) actions.append(node('p', `email-notice-state ${emailState}`, labels[emailState]));
    if (emailState === 'failed') {
      const retry = node('button', 'secondary action-button', 'Gửi lại email thông báo');
      retry.type = 'button';
      retry.addEventListener('click', async () => {
        retry.disabled = true;
        try {
          await api(`/staff/tickets/${encodeURIComponent(ticket.id)}/notification`, { method: 'POST' });
          await refreshDashboard(true);
        } catch (error) {
          if (errorNode) errorNode.textContent = error.message;
          retry.disabled = false;
        }
      });
      actions.append(retry);
    }
  }

  if (ticket.status === 'waiting') {
    const claim = node('button', 'primary action-button', 'Nhận xử lý ticket →');
    claim.type = 'button';
    claim.addEventListener('click', () => performAction(ticket.id, claim, 'claim'));
    row.append(node('p', 'action-hint', 'Nhận ticket để trở thành cán bộ phụ trách và trả lời thí sinh.'), claim);
  } else if (ticket.status === 'in_progress' && ticket.owner === state.username) {
    const replyLabel = node('label', 'sr-only', 'Phản hồi cho thí sinh');
    const reply = node('textarea', 'action-textarea reply-textarea');
    reply.id = 'staff-reply';
    replyLabel.htmlFor = reply.id;
    reply.maxLength = 4000;
    reply.rows = 1;
    reply.placeholder = 'Viết phản hồi cho thí sinh dựa trên thông tin đã kiểm tra…';
    const grow = () => {
      reply.style.height = 'auto';
      reply.style.height = `${Math.min(reply.scrollHeight + 2, 168)}px`;
    };
    reply.addEventListener('input', grow);
    const resolve = node('button', 'primary action-button', 'Gửi phản hồi và đóng →');
    resolve.type = 'button';
    resolve.addEventListener('click', () => performAction(ticket.id, resolve, 'resolve', reply.value, error));
    const replyRow = node('div', 'reply-row');
    replyRow.append(replyLabel, reply, resolve);
    actions.append(replyRow);
  } else if (ticket.status === 'in_progress') {
    actions.append(node('div', 'locked-notice', `Ticket đang được cán bộ ${ticket.owner || 'khác'} xử lý.`));
  }

  if (canReject) {
    const rejectPanel = node('div', 'reject-panel');
    rejectPanel.hidden = true;
    const rejectLabel = node('label', 'action-label reject-label', 'Lý do từ chối (gửi cho thí sinh)');
    const rejectReason = node('textarea', 'action-textarea reject-textarea');
    rejectReason.id = 'reject-reason';
    rejectLabel.htmlFor = rejectReason.id;
    rejectReason.maxLength = 4000;
    rejectReason.rows = 2;
    rejectReason.placeholder = 'Nêu rõ lý do để thí sinh biết hướng xử lý tiếp theo…';
    const confirmReject = node('button', 'secondary danger action-button', 'Xác nhận từ chối');
    confirmReject.type = 'button';
    confirmReject.addEventListener('click', () => {
      if (!rejectReason.value.trim()) {
        error.textContent = 'Vui lòng nhập lý do từ chối.';
        rejectReason.focus();
        return;
      }
      if (window.confirm('Từ chối ticket và gửi lý do cho thí sinh?')) {
        performAction(ticket.id, confirmReject, 'reject', rejectReason.value, error);
      }
    });
    rejectPanel.append(rejectLabel, rejectReason, confirmReject);
    const toggle = node('button', 'text-action', 'Từ chối yêu cầu…');
    toggle.type = 'button';
    toggle.setAttribute('aria-expanded', 'false');
    toggle.addEventListener('click', () => {
      rejectPanel.hidden = !rejectPanel.hidden;
      toggle.setAttribute('aria-expanded', String(!rejectPanel.hidden));
      toggle.textContent = rejectPanel.hidden ? 'Từ chối yêu cầu…' : 'Ẩn phần từ chối';
      if (!rejectPanel.hidden) rejectReason.focus();
    });
    row.prepend(toggle);
    actions.append(rejectPanel);
  }

  if (row.children.length) actions.append(row);
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
    const nextStatus = ACTION_STATUS_FILTERS[action];
    if (nextStatus) $('status-filter').value = nextStatus;
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

function convoMessage(kind, who, avatar, text) {
  const message = node('article', `convo-msg from-${kind}`);
  const body = node('div', 'convo-body');
  body.append(node('span', 'convo-who', who), node('div', 'convo-bubble', text));
  const avatarNode = node('span', 'convo-avatar', kind === 'ai' ? '' : avatar);
  if (kind === 'ai') {
    const logo = document.createElement('img');
    logo.className = 'brand-logo';
    logo.src = '/assets/hust-logo.png';
    logo.alt = '';
    avatarNode.append(logo);
  }
  message.append(avatarNode, body);
  return message;
}

function renderDetail(detail) {
  const ticket = detail.ticket || detail;
  const container = $('detail');
  container.replaceChildren();

  const header = node('header', 'detail-header');
  const titleGroup = node('div');
  const meta = node('p', 'detail-meta');
  meta.append(
    node('span', '', `Tạo ${formatDate(ticket.created)}`),
    node('span', '', `Cập nhật ${formatDate(ticket.updated)}`),
    node('span', '', ticket.owner ? `Phụ trách: ${ticket.owner}` : 'Chưa có người nhận'),
  );
  titleGroup.append(node('h2', '', ticket.id), meta);
  header.append(titleGroup, statusBadge(ticket.status));
  container.append(header);

  const scroll = node('div', 'detail-scroll');
  const convo = node('div', 'convo');
  convo.append(convoMessage('candidate', 'Thí sinh đồng ý chia sẻ', 'TS', detail.shared_content || ticket.summary || 'Chưa có dữ liệu.'));
  if (ticket.reason) convo.append(node('p', 'convo-note', `Lý do chuyển cán bộ: ${ticket.reason}`));

  const original = valueText(optionalValue(ticket, detail, ['original_question', 'question', 'context', 'context_text']));
  const aiAnswer = valueText(optionalValue(ticket, detail, ['ai_answer', 'ai_response', 'answer', 'response']));
  const sources = valueText(optionalValue(ticket, detail, ['sources', 'related_sources', 'source']));
  if (original) convo.append(convoMessage('candidate', 'Câu hỏi gốc / ngữ cảnh', 'TS', original));
  if (aiAnswer || sources) {
    convo.append(convoMessage('ai', 'Trợ lý AI đã trả lời', '', [aiAnswer, sources ? `Nguồn:\n${sources}` : ''].filter(Boolean).join('\n\n')));
  }
  if (!original && !aiAnswer && !sources) {
    convo.append(node('p', 'convo-note muted', 'Thí sinh chỉ đồng ý chia sẻ nội dung ở trên; câu hỏi gốc và câu trả lời AI không được chuyển kèm.'));
  }
  if (ticket.reply) {
    const rejected = ticket.status === 'rejected';
    const who = ticket.owner || 'cán bộ';
    convo.append(convoMessage(rejected ? 'rejected' : 'staff', rejected ? `Lý do từ chối · ${who}` : `Phản hồi của ${who}`, who.slice(0, 2).toUpperCase(), ticket.reply));
  }
  scroll.append(convo);

  if (Array.isArray(detail.events) && detail.events.length) {
    const history = node('details', 'event-history');
    history.append(node('summary', '', `Lịch sử xử lý (${detail.events.length})`));
    const list = node('ol', 'event-list');
    detail.events.forEach((event) => {
      const item = node('li');
      item.append(node('span', 'event-action', EVENT_NAMES[event.action] || event.action));
      item.append(node('small', '', `${formatDate(event.created)}${event.actor ? ` · ${event.actor}` : ''}`));
      list.append(item);
    });
    history.append(list);
    scroll.append(history);
  }
  container.append(scroll);

  const composer = node('footer', 'detail-composer');
  appendActions(composer, ticket);
  if (composer.children.length) container.append(composer);
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
      const first = filteredTickets()[0];
      if (first) await selectTicket(first.id, silent);
      else renderEmptyDetail({ query: normalizeSearch($('queue-search').value), status: $('status-filter').value });
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
$('status-filter').addEventListener('change', renderQueueAndSelectFirst);
$('queue-sort').addEventListener('change', renderQueueAndSelectFirst);
$('queue-search').addEventListener('input', renderQueueAndSelectFirst);

const loginError = new URLSearchParams(window.location.search).get('login_error');
if (loginError) $('login-error').textContent = decodeURIComponent(loginError.replaceAll('+', ' '));

const demoLoginButton = $('demo-login');
fetch('/api/v1/demo/status').then((response) => response.json()).then((result) => {
  demoLoginButton.hidden = !result.enabled;
}).catch(() => {});
demoLoginButton.addEventListener('click', async () => {
  demoLoginButton.disabled = true;
  try {
    const response = await fetch('/api/v1/demo/staff', { method: 'POST', credentials: 'include' });
    if (!response.ok) throw new Error('Không thể mở phiên demo. Vui lòng thử lại.');
    window.location.reload();
  } catch (error) {
    $('login-error').textContent = error.message;
    demoLoginButton.disabled = false;
  }
});

(async () => {
  try {
    const session = await api('/staff/session');
    if (!session.authenticated) return;
    state.username = session.username || '';
    showDashboard();
    await refreshDashboard(false);
  } catch {
    // The login panel is the expected state for an unauthenticated visitor.
  }
})();

// Read-only view of candidate ratings on AI answers.
const feedbackView = window.FeedbackView?.mount($('feedback-view'), {
  api,
  editable: false,
  basePath: '/staff/feedback',
  onError: (error) => renderGlobalError(error.message),
});
function setFeedbackViewOpen(open) {
  $('feedback-view').hidden = !open;
  document.querySelector('#dashboard > .desk-body').hidden = open;
  $('metrics').hidden = open;
  $('feedback-toggle').setAttribute('aria-pressed', String(open));
  $('feedback-toggle').textContent = open ? '← Về hàng chờ' : 'Đánh giá AI';
  $('dashboard-title').textContent = open ? 'Đánh giá câu trả lời AI' : 'Hàng chờ hỗ trợ';
  if (open) feedbackView?.load().catch((error) => renderGlobalError(error.message));
}
$('feedback-toggle')?.addEventListener('click', () => setFeedbackViewOpen($('feedback-view').hidden));
