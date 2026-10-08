const $ = id => document.getElementById(id);
const token = new URLSearchParams(location.hash.slice(1)).get('token') || new URLSearchParams(location.search).get('token') || '';
const resetMode = location.pathname.endsWith('/reset');
const form = $('activate-form');

if (resetMode) {
  $('activate-kicker').textContent = 'ĐẶT LẠI MẬT KHẨU';
  $('activate-title').textContent = 'Tạo mật khẩu mới';
  $('activate-intro').textContent = 'Liên kết đặt lại chỉ dùng một lần và có thời hạn. Mật khẩu hiện tại không được gửi hoặc hiển thị.';
}

function clearErrors() {
  form.querySelectorAll('.field-error').forEach(node => { node.textContent = ''; });
  form.querySelectorAll('[aria-invalid="true"]').forEach(node => node.removeAttribute('aria-invalid'));
  $('activate-error').textContent = '';
}

function errorFor(input, message) {
  input.setAttribute('aria-invalid', 'true');
  $(input.getAttribute('aria-describedby')).textContent = message;
  input.focus();
}

if (!token) {
  $('activate-error').textContent = 'Liên kết bảo mật không hợp lệ hoặc đã bị thiếu.';
  $('activate-submit').disabled = true;
}

$('toggle-password').onclick = () => {
  const input = $('password');
  const hidden = input.type === 'password';
  input.type = hidden ? 'text' : 'password';
  $('toggle-password').textContent = hidden ? 'Ẩn' : 'Hiện';
  $('toggle-password').setAttribute('aria-label', hidden ? 'Ẩn mật khẩu' : 'Hiện mật khẩu');
};

form.onsubmit = async event => {
  event.preventDefault();
  clearErrors();
  const password = $('password').value;
  const confirmation = $('password-confirm').value;
  if (password.length < 10) return errorFor($('password'), 'Mật khẩu phải có ít nhất 10 ký tự.');
  if (password !== confirmation) return errorFor($('password-confirm'), 'Hai mật khẩu chưa giống nhau.');
  const submit = $('activate-submit');
  submit.disabled = true;
  try {
    const response = await fetch('/api/v1/staff/activate', {
      method: 'POST',
      credentials: 'include',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ token, password }),
    });
    const data = await response.json().catch(() => ({}));
    if (!response.ok) {
      const detail = data.detail;
      const fields = typeof detail === 'object' ? detail.fields || {} : {};
      if (fields.password) errorFor($('password'), fields.password);
      else $('activate-error').textContent = typeof detail === 'string' ? detail : detail?.message || 'Không thể thiết lập mật khẩu.';
      submit.disabled = false;
      return;
    }
    history.replaceState({}, document.title, resetMode ? '/staff/reset' : '/staff/activate');
    $('activate-success').textContent = data.message || 'Mật khẩu đã được thiết lập.';
    $('activate-success').hidden = false;
    form.querySelectorAll('input,button').forEach(control => { control.disabled = true; });
  } catch {
    $('activate-error').textContent = 'Không thể kết nối máy chủ. Vui lòng thử lại sau.';
    submit.disabled = false;
  }
};
