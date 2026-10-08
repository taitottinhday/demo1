const $=id=>document.getElementById(id);
let currentEmail='';
async function api(path, options={}){
  const response=await fetch('/api/v1'+path,{...options,credentials:'include',headers:{'Content-Type':'application/json',...(options.headers||{})}});
  const data=await response.json();
  if(!response.ok)throw new Error(typeof data.detail==='string'?data.detail:'Không thể hoàn tất yêu cầu.');
  return data;
}
function feedback(message=''){ $('auth-feedback').textContent=message; }
const loginError=new URLSearchParams(location.search).get('login_error');if(loginError)feedback(loginError);
function show(view){
  document.querySelectorAll('.auth-view').forEach(form=>form.hidden=form.id!==view+'-view');
  const isMain=view==='login'||view==='register';
  $('auth-tabs').hidden=!isMain;
  $('google-login').hidden=!isMain;
  $('account-divider').hidden=!isMain;
  $('auth-switch').hidden=!isMain;
  $('register-link').dataset.view=view==='login'?'register':'login';
  $('auth-switch').firstChild.textContent=view==='login'?'Chưa có tài khoản? ':'Đã có tài khoản? ';
  $('register-link').textContent=view==='login'?'Tạo tài khoản miễn phí':'Đăng nhập';
  document.querySelectorAll('.account-tabs button').forEach(button=>button.classList.toggle('active',button.dataset.view===view));
  const titles={login:['Đăng nhập để tiếp tục','Theo dõi yêu cầu hỗ trợ và lịch sử hỏi đáp.'],register:['Tạo tài khoản học viên','Xác nhận email để hoàn tất đăng ký.'],verify:['Xác nhận email','Kiểm tra hộp thư để hoàn tất đăng ký.'],forgot:['Lấy lại mật khẩu','Nhận mã xác nhận qua email.'],reset:['Đặt lại mật khẩu','Chọn mật khẩu mới cho tài khoản của bạn.']};
  $('auth-title').textContent=titles[view][0];$('auth-subtitle').textContent=titles[view][1];feedback('');
}
document.querySelectorAll('.account-tabs button').forEach(button=>button.onclick=()=>show(button.dataset.view));
$('register-link').onclick=()=>show($('register-link').dataset.view||'register');
$('login-view').onsubmit=async event=>{event.preventDefault();try{await api('/auth/login',{method:'POST',body:JSON.stringify({email:$('login-email').value,password:$('login-password').value})});location.href='/';}catch(error){feedback(error.message);}};
$('register-view').onsubmit=async event=>{event.preventDefault();try{const email=$('register-email').value.trim().toLowerCase();await api('/auth/register',{method:'POST',body:JSON.stringify({name:$('register-name').value,email,password:$('register-password').value})});currentEmail=email;$('verify-email-label').textContent=email;$('reset-email').value=email;show('verify');}catch(error){feedback(error.message);}};
$('verify-view').onsubmit=async event=>{event.preventDefault();try{await api('/auth/verify-email',{method:'POST',body:JSON.stringify({email:currentEmail,code:$('verify-code').value})});$('login-email').value=currentEmail;show('login');feedback('Email đã xác nhận. Hãy đăng nhập bằng mật khẩu của bạn.');}catch(error){feedback(error.message);}};
$('resend-code').onclick=async()=>{try{await api('/auth/resend-code',{method:'POST',body:JSON.stringify({email:currentEmail})});feedback('Mã mới đã được gửi.');}catch(error){feedback(error.message);}};
$('forgot-open').onclick=()=>{ $('forgot-email').value=$('login-email').value;show('forgot'); };
$('forgot-view').onsubmit=async event=>{event.preventDefault();try{const email=$('forgot-email').value.trim().toLowerCase();await api('/auth/forgot-password',{method:'POST',body:JSON.stringify({email})});$('reset-email').value=email;show('reset');feedback('Nếu email đã tồn tại, mã đặt lại đã được gửi.');}catch(error){feedback(error.message);}};
$('reset-view').onsubmit=async event=>{event.preventDefault();try{const email=$('reset-email').value.trim().toLowerCase();await api('/auth/reset-password',{method:'POST',body:JSON.stringify({email,code:$('reset-code').value,password:$('reset-password').value})});$('login-email').value=email;show('login');feedback('Mật khẩu đã được cập nhật.');}catch(error){feedback(error.message);}};
(async()=>{try{const session=await api('/auth/me');if(session.authenticated){location.href='/';}}catch{/* Logged out. */}})();
