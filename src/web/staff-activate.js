const $=id=>document.getElementById(id);
const token=new URLSearchParams(location.search).get('token')||'';
const form=$('activate-form');
if(!token){$('activate-error').textContent='Liên kết kích hoạt không hợp lệ hoặc đã bị thiếu.';form.querySelector('button[type="submit"]').disabled=true;}
$('toggle-password').onclick=()=>{
  const input=$('password');const hidden=input.type==='password';input.type=hidden?'text':'password';
  $('toggle-password').textContent=hidden?'Ẩn':'Hiện';$('toggle-password').setAttribute('aria-label',hidden?'Ẩn mật khẩu':'Hiện mật khẩu');
};
form.onsubmit=async event=>{
  event.preventDefault();$('activate-error').textContent='';$('activate-success').hidden=true;
  if($('password').value!==$('password-confirm').value){$('activate-error').textContent='Hai mật khẩu chưa giống nhau.';return;}
  const submit=$('activate-submit');submit.disabled=true;
  try{
    const response=await fetch('/api/v1/staff/activate',{method:'POST',credentials:'include',headers:{'Content-Type':'application/json'},body:JSON.stringify({token,password:$('password').value})});
    const data=await response.json();if(!response.ok)throw new Error(typeof data.detail==='string'?data.detail:'Không thể thiết lập mật khẩu.');
    history.replaceState({},document.title,'/staff/activate');$('activate-success').textContent=data.message||'Mật khẩu đã được thiết lập.';$('activate-success').hidden=false;form.querySelectorAll('input,button').forEach(control=>{control.disabled=true;});
  }catch(error){$('activate-error').textContent=error.message;submit.disabled=false;}
};
