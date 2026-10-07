const $=id=>document.getElementById(id);
const names={waiting:'Đang chờ',in_progress:'Đang xử lý',resolved:'Đã giải quyết',rejected:'Đã từ chối',cancelled:'Đã hủy'};
const reasons={user_request:'Ứng viên yêu cầu',low_confidence:'AI không chắc chắn',sensitive:'Câu hỏi nhạy cảm'};
const actions={created:'Tạo ticket',claimed:'Nhận xử lý',resolved:'Giải quyết',rejected:'Từ chối',reassigned:'Phân công lại',cancelled:'Ứng viên hủy'};
let officers=[], page=1, total=0, selected=null;
const PAGE_SIZE=15;
function node(tag,cls,text){const n=document.createElement(tag);if(cls)n.className=cls;if(text!==undefined&&text!==null)n.textContent=text;return n;}
function when(ts){return ts?new Date(ts*1000).toLocaleString('vi-VN'):'—';}
function duration(sec){if(sec===null||sec===undefined)return '—';if(sec<3600)return Math.round(sec/60)+' phút';if(sec<86400)return (sec/3600).toFixed(1)+' giờ';return (sec/86400).toFixed(1)+' ngày';}
function percent(v){return v===null||v===undefined?'—':Math.round(v*1000)/10+'%';}
async function api(path,options={}){
  const r=await fetch('/api/v1'+path,{...options,credentials:'include',headers:{'Content-Type':'application/json'}});
  const data=await r.json();
  if(r.status===401||r.status===403){$('dashboard').hidden=true;$('login-panel').hidden=false;$('logout').hidden=true;}
  if(!r.ok)throw new Error(typeof data.detail==='string'?data.detail:'Nội dung chưa hợp lệ.');
  return data;
}
function showDashboard(){$('dashboard').hidden=false;$('login-panel').hidden=true;$('logout').hidden=false;}
function fail(error){$('admin-error').textContent=error.message;}

// Tabs ---------------------------------------------------------------------
document.querySelectorAll('[data-tab]').forEach(tab=>tab.onclick=()=>{
  document.querySelectorAll('[data-tab]').forEach(t=>t.setAttribute('aria-selected',String(t===tab)));
  document.querySelectorAll('.admin-tab').forEach(s=>s.hidden=s.id!=='tab-'+tab.dataset.tab);
});

// Overview -----------------------------------------------------------------
function bars(container,rows){
  container.replaceChildren();const max=Math.max(1,...rows.map(r=>r.value));
  if(!rows.length){container.append(node('p','empty-state','Chưa có dữ liệu.'));return;}
  rows.forEach(r=>{const row=node('div','bar-row');const track=node('div','bar-track');const fill=node('div','bar-fill '+(r.cls||''));fill.style.width=(100*r.value/max)+'%';track.append(fill);row.append(node('span','bar-label',r.label),track,node('b','',String(r.value)));container.append(row);});
}
async function loadOverview(){
  const params=new URLSearchParams();if($('from').value)params.set('from',$('from').value);if($('to').value)params.set('to',$('to').value);
  const m=await api('/admin/metrics?'+params);
  const s=m.tickets_by_status;
  $('metrics').replaceChildren();
  [['Đang chờ cán bộ',s.waiting,'Ticket ở hàng chờ'],['Chờ trung bình',duration(m.avg_wait_seconds),'Từ lúc tạo đến khi nhận'],['Xử lý trung bình',duration(m.avg_resolve_seconds),'Từ lúc nhận đến khi giải quyết'],['Tỷ lệ từ chối',percent(m.reject_rate),'Từ chối / (giải quyết + từ chối)']]
    .forEach(([label,value,note])=>{const box=node('div','metric');box.append(node('span','',label),node('b','',String(value)),node('small','',note));$('metrics').append(box);});
  bars($('status-chart'),Object.keys(names).map(k=>({label:names[k],value:s[k]||0,cls:k})));
  bars($('load-chart'),m.officer_load.map(o=>({label:o.name+(o.active?'':' (khóa)'),value:o.open_tickets})));
  $('stale-title').textContent=`Ticket chờ quá ${m.stale_hours} giờ (${m.stale_waiting.length})`;
  $('stale').replaceChildren();
  if(!m.stale_waiting.length)$('stale').append(node('p','empty-state','Không có ticket nào chờ quá lâu.'));
  m.stale_waiting.forEach(t=>{const b=node('button','queue-item');const head=node('div','ticket-head');head.append(node('b','',t.id),node('span','badge waiting','Chờ '+duration(t.waiting_seconds)));b.append(head,node('p','',t.summary.slice(0,140)));b.onclick=()=>openTicket(t.id);$('stale').append(b);});
  $('rate-note').textContent=`Tỷ lệ AI trả lời trực tiếp: ${percent(m.direct_answer_rate)} · Tỷ lệ chuyển cán bộ: ${m.handover_rate===null?'chưa đo được':percent(m.handover_rate)}. Tỷ lệ trả lời lấy từ log sự kiện chat; tỷ lệ chuyển cần bảng chat_logs do bên AI ghi.`;
}

// Tickets ------------------------------------------------------------------
async function loadTickets(){
  const params=new URLSearchParams({page,page_size:PAGE_SIZE});
  if($('status-filter').value)params.set('status',$('status-filter').value);
  if($('officer-filter').value)params.set('officer_id',$('officer-filter').value);
  const data=await api('/admin/tickets?'+params);total=data.total;
  $('ticket-rows').replaceChildren();
  if(!data.items.length){const tr=node('tr');const td=node('td','empty-state','Không có ticket phù hợp.');td.colSpan=5;tr.append(td);$('ticket-rows').append(tr);}
  data.items.forEach(t=>{const tr=node('tr','clickable'+(selected===t.id?' selected':''));tr.tabIndex=0;const badge=node('td');badge.append(node('span','badge '+t.status,names[t.status]));
    tr.append(node('td','nowrap',t.id),node('td','',t.summary.slice(0,80)),badge,node('td','',t.officer_name||'—'),node('td','nowrap',when(t.created)));
    tr.onclick=()=>openTicket(t.id);tr.onkeydown=e=>{if(e.key==='Enter')openTicket(t.id);};$('ticket-rows').append(tr);});
  const pages=Math.max(1,Math.ceil(total/PAGE_SIZE));
  $('page-info').textContent=`Trang ${page}/${pages} · ${total} ticket`;$('prev').disabled=page<=1;$('next').disabled=page>=pages;
}
async function openTicket(id){
  selected=id;document.querySelector('[data-tab="tickets"]').click();
  try{const [t,history]=await Promise.all([api('/admin/tickets/'+id),api('/admin/tickets/'+id+'/history')]);renderDetail(t,history);await loadTickets();}catch(e){fail(e);}
}
function renderDetail(t,history){
  const box=$('detail');box.replaceChildren();
  box.append(node('span','eyebrow','CHI TIẾT TICKET'),node('h2','',t.id),node('span','badge '+t.status,names[t.status]));
  const facts=node('dl','facts');
  [['Lý do chuyển',reasons[t.handover_reason]||t.handover_reason],['Độ tự tin AI',t.confidence_score===null?'Chưa ghi nhận':t.confidence_score],['Cán bộ',t.officer_name||'—'],['Tạo lúc',when(t.created)],['Nhận lúc',when(t.claimed_at)],['Kết thúc lúc',when(t.resolved_at)]]
    .forEach(([k,v])=>facts.append(node('dt','',k),node('dd','',String(v))));
  box.append(node('div','summary',t.summary),facts);
  box.append(node('h3','','Hội thoại trước khi chuyển'));
  if(!t.conversation.length)box.append(node('p','hint','Không còn lịch sử chat (ứng viên đã xóa hoặc phiên đã hết hạn).'));
  t.conversation.forEach(m=>{const item=node('div','message '+m.role);item.append(node('div','speaker',m.role==='user'?'Ứng viên':'Trợ lý AI'),node('div','body',m.text));
    m.sources.forEach(s=>{const card=node('details','source-card');card.append(node('summary','',`Nguồn · ${s.title||'Tài liệu'} · trang ${s.page}`),node('div','quote',s.excerpt||''));if(s.local_url){const a=node('a','','Mở PDF');a.href=s.local_url;a.target='_blank';a.rel='noopener';card.append(a);}item.append(card);});
    box.append(item);});
  if(t.reply)box.append(node('h3','',t.status==='rejected'?'Lý do từ chối':'Phản hồi của cán bộ'),node('div','reply-box',t.reply));
  box.append(node('h3','','Lịch sử'));const list=node('ol','timeline');
  history.forEach(e=>{const li=node('li');let text=actions[e.action]||e.action;
    if(e.action==='reassigned')text+=`: ${e.from_officer_name||'hàng chờ'} → ${e.to_officer_name||'hàng chờ'}`;
    li.append(node('b','',text),node('span','',' · '+(e.actor_name||'Ứng viên')+' · '+when(e.created)));if(e.note)li.append(node('div','hint',e.note));list.append(li);});
  box.append(list);
  if(t.status==='waiting'||t.status==='in_progress'){
    const err=node('p','error-text');err.setAttribute('role','alert');
    const label=node('label','','Phân công lại');label.htmlFor='reassign-to';const select=node('select');select.id='reassign-to';
    select.append(new Option('— Chọn cán bộ —',''));
    officers.filter(o=>o.active&&o.id!==t.officer_id).forEach(o=>select.append(new Option(`${o.name} (đang giữ ${o.open_tickets})`,o.id)));
    if(t.status==='in_progress')select.append(new Option('↩ Trả về hàng chờ','queue'));
    const noteLabel=node('label','','Ghi chú');noteLabel.htmlFor='reassign-note';const note=node('input');note.id='reassign-note';note.maxLength=500;note.placeholder='Lý do phân công lại';
    const button=node('button','primary','Xác nhận phân công →');
    button.onclick=async()=>{err.textContent='';if(!select.value){err.textContent='Hãy chọn cán bộ nhận hoặc "Trả về hàng chờ".';select.focus();return;}
      const to=select.value==='queue'?null:Number(select.value);
      if(to===null&&!confirm(`Trả ${t.id} về hàng chờ? ${t.officer_name} sẽ không còn phụ trách ticket này.`))return;
      button.disabled=true;try{await api('/admin/tickets/'+t.id+'/reassign',{method:'POST',body:JSON.stringify({to_officer_id:to,note:note.value})});await loadOfficers();await openTicket(t.id);}catch(e){err.textContent=e.message;button.disabled=false;}};
    box.append(label,select,noteLabel,note,button,err);
  }
}

// Officers -----------------------------------------------------------------
function bindPasswordToggle(button,input){
  button.onclick=()=>{
    const hidden=input.type==='password';
    input.type=hidden?'text':'password';
    button.textContent=hidden?'Ẩn':'Hiện';
    button.setAttribute('aria-label',hidden?'Ẩn mật khẩu':'Hiện mật khẩu');
  };
}
function passwordResetCell(o){
  const cell=node('td');
  const open=node('button','small-action','Đặt lại');open.type='button';open.title='Đặt mật khẩu mới cho cán bộ';
  const form=node('form','password-reset');form.hidden=true;
  const wrap=node('div','password-input');
  const input=document.createElement('input');input.type='password';input.minLength=8;input.maxLength=200;input.autocomplete='new-password';input.placeholder='Mật khẩu mới';input.required=true;
  const eye=node('button','password-toggle','Hiện');eye.type='button';eye.setAttribute('aria-label','Hiện mật khẩu');bindPasswordToggle(eye,input);
  wrap.append(input,eye);
  const save=node('button','small-action','Lưu');save.type='submit';
  const error=node('p','error-text');error.setAttribute('role','alert');
  form.append(wrap,save,error);
  open.onclick=()=>{form.hidden=!form.hidden;if(!form.hidden)input.focus();};
  form.onsubmit=async event=>{
    event.preventDefault();error.textContent='';
    if(input.value.length<8){error.textContent='Mật khẩu mới phải có ít nhất 8 ký tự.';input.focus();return;}
    save.disabled=true;
    try{
      await api('/admin/officers/'+o.id+'/password',{method:'POST',body:JSON.stringify({password:input.value})});
      input.value='';form.hidden=true;open.textContent='Đã đặt lại';
    }catch(err){error.textContent=err.message;}
    finally{save.disabled=false;}
  };
  cell.append(open,form);return cell;
}
async function loadOfficers(){
  officers=await api('/admin/officers');
  const current=$('officer-filter').value;$('officer-filter').replaceChildren(new Option('Tất cả cán bộ',''));
  officers.forEach(o=>$('officer-filter').append(new Option(o.name,o.id)));$('officer-filter').value=current;
  $('officer-rows').replaceChildren();
  officers.forEach(o=>{const tr=node('tr');const toggle=node('td');const label=node('label','switch');const input=node('input');input.type='checkbox';input.checked=o.active;input.setAttribute('aria-label',(o.active?'Khóa ':'Mở khóa ')+o.name);
    input.onchange=async()=>{
      if(!input.checked){const msg=o.open_tickets?`Khóa ${o.name}? ${o.open_tickets} ticket sẽ được trả về hàng chờ.`:`Khóa ${o.name}?`;if(!confirm(msg)){input.checked=true;return;}}
      input.disabled=true;try{await api('/admin/officers/'+o.id,{method:'PATCH',body:JSON.stringify({active:input.checked})});await refresh();}catch(e){fail(e);input.checked=!input.checked;input.disabled=false;}};
    label.append(input,node('span','',o.active?'Hoạt động':'Đã khóa'));toggle.append(label);
    tr.append(node('td','',o.name),node('td','',o.username),node('td','',o.email),node('td','',String(o.open_tickets)),passwordResetCell(o),toggle);$('officer-rows').append(tr);});
}
document.querySelectorAll('[data-password-toggle]').forEach(button=>bindPasswordToggle(button,$(button.dataset.passwordToggle)));
$('officer-form').addEventListener('submit',async e=>{e.preventDefault();$('officer-error').textContent='';const button=e.submitter;button.disabled=true;
  try{await api('/admin/officers',{method:'POST',body:JSON.stringify({name:$('o-name').value,username:$('o-username').value,email:$('o-email').value,password:$('o-password').value})});e.target.reset();await loadOfficers();}
  catch(error){$('officer-error').textContent=error.message;}finally{button.disabled=false;}});

// Wiring -------------------------------------------------------------------
async function refresh(){
  $('admin-error').textContent='';
  try{await loadOfficers();await Promise.all([loadOverview(),loadTickets()]);if(selected)await openTicketSilently(selected);}catch(e){fail(e);}
}
async function openTicketSilently(id){const [t,history]=await Promise.all([api('/admin/tickets/'+id),api('/admin/tickets/'+id+'/history')]);renderDetail(t,history);}
$('range-form').addEventListener('submit',e=>{e.preventDefault();loadOverview().catch(fail);});
$('status-filter').onchange=$('officer-filter').onchange=()=>{page=1;loadTickets().catch(fail);};
$('prev').onclick=()=>{page--;loadTickets().catch(fail);};$('next').onclick=()=>{page++;loadTickets().catch(fail);};
$('refresh').onclick=refresh;
$('login-form').addEventListener('submit',async e=>{e.preventDefault();$('login-error').textContent='';const button=e.submitter;button.disabled=true;
  try{await api('/admin/login',{method:'POST',body:JSON.stringify({username:$('username').value,password:$('password').value})});$('password').value='';showDashboard();await refresh();}
  catch(error){$('login-error').textContent=error.message;}finally{button.disabled=false;}});
$('logout').onclick=async()=>{try{await api('/admin/logout',{method:'POST'});location.reload();}catch(e){fail(e);}};
(async()=>{try{await api('/admin/me');showDashboard();await refresh();}catch{/* Login form remains visible. */}})();
