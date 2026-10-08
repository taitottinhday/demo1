const $ = id => document.getElementById(id);
let currentEmail = '';
let currentOtpPurpose = 'verify';
let resendTimer = null;
let expiryTimer = null;

function maskEmail(email) {
  const [local, domain] = String(email || '').split('@');
  if (!domain) return '***';
  const visible = local.length > 2 ? local.slice(0, 2) : local.slice(0, 1);
  return `${visible}${'*'.repeat(Math.max(2, local.length - visible.length))}@${domain}`;
}

async function api(path, options = {}) {
  const response = await fetch('/api/v1' + path, {
    ...options,
    credentials: 'include',
    headers: { 'Content-Type': 'application/json', ...(options.headers || {}) },
  });
  const data = await response.json().catch(() => ({}));
  if (!response.ok) {
    const detail = data.detail;
    const error = new Error(typeof detail === 'string' ? detail : detail?.message || 'Không thể hoàn tất yêu cầu.');
    error.fields = typeof detail === 'object' ? (detail.fields || {}) : {};
    throw error;
  }
  return data;
}

function feedback(message = '') { $('auth-feedback').textContent = message; }

function clearErrors(form) {
  form?.querySelectorAll('.field-error').forEach(node => { node.textContent = ''; });
  form?.querySelectorAll('[aria-invalid="true"]').forEach(node => node.removeAttribute('aria-invalid'));
}

function field(form, name) { return form?.querySelector(`[name="${name}"]`); }

function showFieldErrors(form, fields = {}) {
  clearErrors(form);
  const invalid = [];
  Object.entries(fields).forEach(([name, message]) => {
    const input = field(form, name);
    if (!input) return;
    input.setAttribute('aria-invalid', 'true');
    const error = $(input.getAttribute('aria-describedby') || `${input.id}-error`);
    if (error) error.textContent = message;
    invalid.push(input);
  });
  if (invalid[0]) invalid[0].focus();
  return invalid.length > 0;
}

function validate(form, rules) {
  clearErrors(form);
  const errors = {};
  Object.entries(rules).forEach(([name, rule]) => {
    const input = field(form, name);
    const value = input?.value.trim() || '';
    const message = rule(value);
    if (message) errors[name] = message;
  });
  if (Object.keys(errors).length) {
    showFieldErrors(form, errors);
    feedback('Vui lòng kiểm tra các trường được đánh dấu.');
    return false;
  }
  return true;
}

const required = label => value => value ? '' : `${label} là bắt buộc.`;
const emailRule = value => {
  if (!value) return 'Email là bắt buộc.';
  return /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(value) ? '' : 'Email không đúng định dạng.';
};
const passwordRule = value => !value ? 'Mật khẩu là bắt buộc.' : value.length < 10 ? 'Mật khẩu phải có ít nhất 10 ký tự.' : '';
const codeRule = value => !/^\d{6}$/.test(value) ? 'Mã xác nhận phải gồm đúng 6 chữ số.' : '';

function applyApiError(form, error) {
  if (!showFieldErrors(form, error.fields)) feedback(error.message);
  else feedback('Dữ liệu chưa hợp lệ.');
}

function stopOtpTimers() {
  if (resendTimer) window.clearInterval(resendTimer);
  if (expiryTimer) window.clearInterval(expiryTimer);
  resendTimer = null;
  expiryTimer = null;
}

function formatCountdown(seconds) {
  const value = Math.max(0, Math.ceil(seconds));
  return `${Math.floor(value / 60)}:${String(value % 60).padStart(2, '0')}`;
}

function startOtp(meta, email, purpose) {
  stopOtpTimers();
  currentEmail = email;
  currentOtpPurpose = purpose;
  const seconds = Number(meta?.expires_in) || 600;
  const resendAfter = Number(meta?.resend_after) || 30;
  const startedAt = Date.now();
  const target = purpose === 'verify' ? $('verify-otp-meta') : $('reset-otp-meta');
  if (target) target.textContent = `Mã đã gửi đến ${meta?.email || maskEmail(email)} · hết hạn sau ${Math.ceil(seconds / 60)} phút.`;
  const resend = purpose === 'verify' ? $('resend-code') : $('resend-reset-code');
  if (resend) {
    resend.disabled = true;
    resend.textContent = `Gửi lại mã (${formatCountdown(resendAfter)})`;
    let remaining = resendAfter;
    resendTimer = window.setInterval(() => {
      remaining -= 1;
      if (remaining <= 0) {
        window.clearInterval(resendTimer);
        resendTimer = null;
        resend.disabled = false;
        resend.textContent = 'Gửi lại mã';
      } else resend.textContent = `Gửi lại mã (${formatCountdown(remaining)})`;
    }, 1000);
  }
  let expires = seconds;
  expiryTimer = window.setInterval(() => {
    expires = seconds - (Date.now() - startedAt) / 1000;
    if (expires <= 0) {
      window.clearInterval(expiryTimer);
      expiryTimer = null;
      if (target) target.textContent = `Mã đã gửi đến ${meta?.email || maskEmail(email)} · mã đã hết hạn, hãy gửi lại mã.`;
    } else if (target) target.textContent = `Mã đã gửi đến ${meta?.email || maskEmail(email)} · còn ${formatCountdown(expires)}.`;
  }, 1000);
}

async function resendOtp(purpose) {
  const button = purpose === 'verify' ? $('resend-code') : $('resend-reset-code');
  button.disabled = true;
  try {
    const data = await api('/auth/resend-code', { method: 'POST', body: JSON.stringify({ email: currentEmail, purpose }) });
    if (data.otp) startOtp(data.otp, currentEmail, purpose);
    else { button.disabled = false; button.textContent = 'Gửi lại mã'; }
    feedback('Mã mới đã được gửi đến email của bạn.');
  } catch (error) {
    button.disabled = false;
    applyApiError(null, error);
  }
}

function show(view) {
  document.querySelectorAll('.auth-view').forEach(form => { form.hidden = form.id !== `${view}-view`; clearErrors(form); });
  const isMain = view === 'login' || view === 'register';
  $('auth-tabs').hidden = !isMain;
  $('google-login').hidden = !isMain;
  $('account-divider').hidden = !isMain;
  $('auth-switch').hidden = !isMain;
  $('register-link').dataset.view = view === 'login' ? 'register' : 'login';
  $('auth-switch').firstChild.textContent = view === 'login' ? 'Chưa có tài khoản? ' : 'Đã có tài khoản? ';
  $('register-link').textContent = view === 'login' ? 'Tạo tài khoản miễn phí' : 'Đăng nhập';
  const titles = {
    login: ['Đăng nhập để tiếp tục', 'Lưu lịch sử hỏi đáp và theo dõi yêu cầu hỗ trợ của bạn.'],
    register: ['Tạo tài khoản học viên', 'Xác nhận email để bảo vệ tài khoản của bạn.'],
    verify: ['Xác nhận email', 'Nhập mã 6 số trong email. Bạn có thể dán trực tiếp mã vào ô bên dưới.'],
    forgot: ['Lấy lại mật khẩu', 'Bạn sẽ nhận một mã xác nhận qua email.'],
    reset: ['Đặt lại mật khẩu', 'Mã chỉ dùng một lần và có thời hạn.'],
  };
  $('auth-title').textContent = titles[view][0];
  $('auth-subtitle').textContent = titles[view][1];
  feedback('');
}

function pasteCode(input) {
  input.addEventListener('input', () => { input.value = input.value.replace(/\D/g, '').slice(0, 6); });
  input.addEventListener('paste', event => {
    const pasted = (event.clipboardData || window.clipboardData).getData('text').replace(/\D/g, '').slice(0, 6);
    if (!pasted) return;
    event.preventDefault();
    input.value = pasted;
    input.dispatchEvent(new Event('input', { bubbles: true }));
  });
}

document.querySelectorAll('.account-tabs button').forEach(button => { button.onclick = () => show(button.dataset.view); });
$('register-link').onclick = () => show($('register-link').dataset.view || 'register');
pasteCode($('verify-code'));
pasteCode($('reset-code'));

$('login-view').onsubmit = async event => {
  event.preventDefault();
  const form = event.currentTarget;
  if (!validate(form, { email: emailRule, password: required('Mật khẩu') })) return;
  try {
    await api('/auth/login', { method: 'POST', body: JSON.stringify({ email: field(form, 'email').value.trim().toLowerCase(), password: field(form, 'password').value }) });
    location.href = '/';
  } catch (error) { applyApiError(form, error); }
};

$('register-view').onsubmit = async event => {
  event.preventDefault();
  const form = event.currentTarget;
  if (!validate(form, { email: emailRule, password: passwordRule })) return;
  const email = field(form, 'email').value.trim().toLowerCase();
  try {
    const data = await api('/auth/register', { method: 'POST', body: JSON.stringify({ name: field(form, 'name').value, email, password: field(form, 'password').value }) });
    currentEmail = email;
    $('verify-email-label').textContent = data.otp?.email || maskEmail(email);
    $('reset-email').value = email;
    show('verify');
    startOtp(data.otp, email, 'verify');
    feedback(data.message || 'Mã xác nhận đã được gửi đến email của bạn.');
  } catch (error) { applyApiError(form, error); }
};

$('verify-view').onsubmit = async event => {
  event.preventDefault();
  const form = event.currentTarget;
  if (!validate(form, { code: codeRule })) return;
  try {
    await api('/auth/verify-email', { method: 'POST', body: JSON.stringify({ email: currentEmail, code: field(form, 'code').value }) });
    stopOtpTimers();
    $('login-email').value = currentEmail;
    show('login');
    feedback('Email đã xác nhận. Hãy đăng nhập bằng mật khẩu của bạn.');
  } catch (error) { applyApiError(form, error); }
};

$('resend-code').onclick = () => resendOtp('verify');
$('resend-reset-code').onclick = () => resendOtp('reset');
$('forgot-open').onclick = () => { $('forgot-email').value = $('login-email').value; show('forgot'); };

$('forgot-view').onsubmit = async event => {
  event.preventDefault();
  const form = event.currentTarget;
  if (!validate(form, { email: emailRule })) return;
  const email = field(form, 'email').value.trim().toLowerCase();
  try {
    const data = await api('/auth/forgot-password', { method: 'POST', body: JSON.stringify({ email }) });
    $('reset-email').value = email;
    show('reset');
    startOtp(data.otp, email, 'reset');
    feedback(data.message || 'Nếu email đã tồn tại, mã đặt lại đã được gửi.');
  } catch (error) { applyApiError(form, error); }
};

$('reset-view').onsubmit = async event => {
  event.preventDefault();
  const form = event.currentTarget;
  if (!validate(form, { email: emailRule, code: codeRule, password: passwordRule })) return;
  const email = field(form, 'email').value.trim().toLowerCase();
  try {
    await api('/auth/reset-password', { method: 'POST', body: JSON.stringify({ email, code: field(form, 'code').value, password: field(form, 'password').value }) });
    stopOtpTimers();
    $('login-email').value = email;
    show('login');
    feedback('Mật khẩu đã được cập nhật. Các phiên đăng nhập cũ đã bị đăng xuất.');
  } catch (error) { applyApiError(form, error); }
};

(async () => {
  try {
    const session = await api('/auth/me');
    if (session.authenticated) location.href = '/';
  } catch { /* Logged out. */ }
})();

const loginError = new URLSearchParams(location.search).get('login_error');
if (loginError) feedback(loginError);
