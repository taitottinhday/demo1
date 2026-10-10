const $=id=>document.getElementById(id);
const names={waiting:'Đang chờ',in_progress:'Đang xử lý',resolved:'Đã giải quyết',rejected:'Đã từ chối',cancelled:'Đã hủy'};
const reasons={user_request:'Ứng viên yêu cầu',low_confidence:'AI không chắc chắn',sensitive:'Câu hỏi nhạy cảm'};
const actions={created:'Tạo ticket',claimed:'Nhận xử lý',reply:'Gửi phản hồi',resolved:'Giải quyết',rejected:'Từ chối',reassigned:'Phân công lại',cancelled:'Ứng viên hủy'};
let officers=[], page=1, total=0, selected=null, assignmentNotice=null, pollingTimer=null, refreshInFlight=false, ticketListRequestId=0, ticketDetailRequestId=0;
const PAGE_SIZE=15;
const POLL_INTERVAL_MS=5000;
document.body.classList.add('admin-page');
function node(tag,cls,text){const n=document.createElement(tag);if(cls)n.className=cls;if(text!==undefined&&text!==null)n.textContent=text;return n;}
function when(ts){return ts?new Date(ts*1000).toLocaleString('vi-VN'):'—';}
function duration(sec){
  if(sec===null||sec===undefined)return '—';
  const value=Number(sec);
  if(!Number.isFinite(value)||value<0)return '—';
  if(value===0)return '0 phút';
  if(value<60)return Math.max(1,Math.round(value))+' giây';
  if(value<3600)return Math.max(1,Math.min(59,Math.round(value/60)))+' phút';
  if(value<86400)return (value/3600).toFixed(1)+' giờ';
  return (value/86400).toFixed(1)+' ngày';
}
function percent(v){return v===null||v===undefined?'—':Math.round(v*1000)/10+'%';}
function kpiValue(k){
  if(k.status==='Chưa đủ dữ liệu'||k.value===null||k.value===undefined)return 'Chưa đủ dữ liệu';
  if(k.key.endsWith('_rate'))return percent(k.value);
  if(k.key==='avg_wait'||k.key==='avg_resolve')return duration(k.value);
  return String(k.value);
}
function kpiWindow(k){const w=k.time_window||{};return `${w.from||'Từ lúc bắt đầu ghi nhận'} → ${w.to||'Hiện tại'}`;}
async function api(path,options={}){
  const r=await fetch('/api/v1'+path,{...options,credentials:'include',headers:{'Content-Type':'application/json'}});
  const data=await r.json();
  if(r.status===401||r.status===403){stopAutoRefresh();$('dashboard').hidden=true;$('login-panel').hidden=false;$('logout').hidden=true;if(r.status===401)$('login-error').textContent='Phiên quản trị đã hết hạn. Vui lòng đăng nhập lại.';}
  if(!r.ok){const detail=data.detail;const error=new Error(typeof detail==='string'?detail:detail?.message||'Nội dung chưa hợp lệ.');error.fields=typeof detail==='object'?(detail.fields||{}):{};throw error;}
  return data;
}
function showDashboard(){$('dashboard').hidden=false;$('login-panel').hidden=true;$('logout').hidden=false;}
function fail(error){$('admin-error').textContent=error.message;}
function stopAutoRefresh(){if(pollingTimer){window.clearInterval(pollingTimer);pollingTimer=null;}}
function startAutoRefresh(){stopAutoRefresh();pollingTimer=window.setInterval(()=>{if(document.hidden||refreshInFlight||hasAdminDraft())return;refresh({silent:true}).catch(fail);},POLL_INTERVAL_MS);}
function hasAdminDraft(){return ['o-name','o-username','o-email','reassign-note'].some(id=>{const field=$(id);return field&&((document.activeElement===field)||field.value.trim());});}
function markLiveUpdated(){const status=$('live-status');if(status)status.textContent=`Đã cập nhật ${new Date().toLocaleTimeString('vi-VN')} · Tự động mỗi 5 giây`;}
const FILTER_STORAGE_KEY='admin-dashboard-filters';
function persistFilters(){
  try{sessionStorage.setItem(FILTER_STORAGE_KEY,JSON.stringify({from:$('from').value,to:$('to').value,status:$('status-filter').value,officer:$('officer-filter').value}));}catch{/* Ignore unavailable browser storage. */}
}
function restoreFilters(){
  try{
    const saved=JSON.parse(sessionStorage.getItem(FILTER_STORAGE_KEY)||'{}');
    if(saved.from)$('from').value=saved.from;
    if(saved.to)$('to').value=saved.to;
    if(saved.status!==undefined)$('status-filter').value=saved.status;
    if(saved.officer!==undefined)$('officer-filter').value=saved.officer;
  }catch{/* Ignore unavailable or malformed browser storage. */}
}
restoreFilters();

// Tabs ---------------------------------------------------------------------
document.querySelectorAll('[data-tab]').forEach(tab=>tab.onclick=()=>{
  tab.id=tab.id||`tab-button-${tab.dataset.tab}`;
  tab.setAttribute('aria-controls',`tab-${tab.dataset.tab}`);
  document.querySelectorAll('[data-tab]').forEach(t=>t.setAttribute('aria-selected',String(t===tab)));
  document.querySelectorAll('.admin-tab').forEach(s=>{s.hidden=s.id!=='tab-'+tab.dataset.tab;s.setAttribute('role','tabpanel');s.setAttribute('aria-labelledby',tab.id);});
});
document.querySelector('[data-tab="overview"]')?.click();

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
  (m.kpis||[]).forEach(k=>{
    const box=node('article','metric kpi-card');
    box.append(node('span','metric-label',k.label),node('b','metric-value',kpiValue(k)));
    const facts=node('div','kpi-facts');
    facts.append(node('small','',`Công thức: ${k.formula||'Chưa xác định'}`));
    facts.append(node('small','',k.denominator===null||k.denominator===undefined?`Số lượng: ${k.value??'—'}`:`Tử số / mẫu số: ${k.numerator??'—'} / ${k.denominator}`));
    facts.append(node('small','',`Khoảng: ${kpiWindow(k)}`));
    facts.append(node('small','',`Múi giờ: ${k.timezone||m.data_timezone||'—'}`));
    facts.append(node('small','',`Cập nhật: ${k.last_updated||m.data_last_updated||'—'}`));
    facts.append(node('small','',`Nguồn: ${k.source||m.data_source||'Chưa xác định'}`));
    box.append(facts);$('metrics').append(box);
  });
  if(!m.kpis?.length){$('metrics').append(node('p','empty-state','Chưa đủ dữ liệu KPI.'));}
  bars($('status-chart'),Object.keys(names).map(k=>({label:names[k],value:s[k]||0,cls:k})));
  bars($('load-chart'),m.officer_load.map(o=>({label:o.name+(o.active?'':' (khóa)'),value:o.open_tickets})));
  $('stale-title').textContent=`Ticket chờ quá ${m.stale_hours} giờ (${m.stale_waiting.length})`;
  $('stale').replaceChildren();
  if(!m.stale_waiting.length)$('stale').append(node('p','empty-state','Không có ticket nào chờ quá lâu.'));
  m.stale_waiting.forEach(t=>{const b=node('button','queue-item');const head=node('div','ticket-head');head.append(node('b','',t.id),node('span','badge waiting','Chờ '+duration(t.waiting_seconds)));b.append(head,node('p','',t.summary.slice(0,140)));b.onclick=()=>openTicket(t.id);$('stale').append(b);});
  const handoverRate=m.handover_rate||{};
  $('rate-note').textContent=handoverRate.reason||'Chưa thể tính tỷ lệ chuyển cán bộ vì nhật ký câu hỏi chưa liên kết định danh với ticket. Xem số yêu cầu chuyển trong KPI cùng khoảng thời gian.';
  $('data-note').textContent=`Nguồn dữ liệu: ${m.data_source||m.rates_source||'Chưa xác định'} · Khoảng: ${(m.data_window?.from||'Từ lúc bắt đầu ghi nhận')} → ${(m.data_window?.to||'Hiện tại')} · Múi giờ: ${m.data_timezone||'—'} · Cập nhật: ${m.data_last_updated||'—'}. Các chỉ số thiếu mẫu số được hiển thị là “Chưa đủ dữ liệu”.`;
}

// Tickets ------------------------------------------------------------------
function ticketFilterSummary(){
  const parts=[];
  const status=$('status-filter').value;
  const officer=$('officer-filter').value;
  if(status)parts.push($('status-filter').selectedOptions[0]?.textContent||status);
  if(officer)parts.push($('officer-filter').selectedOptions[0]?.textContent||'cán bộ đã chọn');
  return parts.join(' · ')||'tất cả ticket';
}
function renderTicketEmpty(hasResults){
  const box=$('detail');box.replaceChildren();
  const empty=node('div','empty-detail');empty.append(node('span','empty-detail-icon','⌁'));
  if(hasResults){
    empty.append(node('h2','', 'Chưa có ticket được chọn'),node('p','', 'Hãy chọn một ticket trong danh sách để xem nội dung, hội thoại và lịch sử xử lý.'));
  }else{
    empty.append(node('h2','', 'Không có ticket phù hợp'),node('p','', `Bộ lọc hiện tại: ${ticketFilterSummary()}. Hãy đổi trạng thái hoặc cán bộ để tìm ticket khác.`));
  }
  box.append(empty);
}
async function loadTickets(){
  const params=new URLSearchParams({page,page_size:PAGE_SIZE});
  if($('status-filter').value)params.set('status',$('status-filter').value);
  if($('officer-filter').value)params.set('officer_id',$('officer-filter').value);
  const requestId=++ticketListRequestId;
  let data;
  try{data=await api('/admin/tickets?'+params);}catch(error){if(requestId!==ticketListRequestId)return false;throw error;}
  if(requestId!==ticketListRequestId)return false;
  total=data.total;
  const table=document.querySelector('#ticket-rows')?.closest('table');
  if(table){table.classList.add('admin-ticket-table');if(!table.querySelector('caption'))table.prepend(node('caption','', 'Danh sách ticket hỗ trợ'));}
  $('ticket-rows').replaceChildren();
  if(!data.items.length){const tr=node('tr');const td=node('td','empty-state','Không có ticket phù hợp.');td.colSpan=5;tr.append(td);$('ticket-rows').append(tr);}
  data.items.forEach(t=>{const tr=node('tr','clickable'+(selected===t.id?' selected':''));tr.tabIndex=0;tr.setAttribute('role','button');tr.setAttribute('aria-label',`Mở chi tiết ticket ${t.id}`);const badge=node('td');badge.dataset.label='Trạng thái';badge.append(node('span','badge '+t.status,names[t.status]));
    const idCell=node('td','nowrap',t.id);idCell.dataset.label='Mã ticket';
    const summaryCell=node('td','',t.summary.slice(0,80));summaryCell.dataset.label='Nội dung';
    const officerCell=node('td','',t.officer_name||'—');officerCell.dataset.label='Cán bộ';
    const createdCell=node('td','nowrap',when(t.created));createdCell.dataset.label='Tạo lúc';
    tr.append(idCell,summaryCell,badge,officerCell,createdCell);
    tr.onclick=()=>openTicket(t.id);tr.onkeydown=e=>{if(e.key==='Enter'||e.key===' '){e.preventDefault();openTicket(t.id);}};$('ticket-rows').append(tr);});
  if(!data.items.length)renderTicketEmpty(false);else if(!selected)renderTicketEmpty(true);
  const pages=Math.max(1,Math.ceil(total/PAGE_SIZE));
  $('page-info').textContent=`Trang ${page}/${pages} · ${total} ticket`;$('prev').disabled=page<=1;$('next').disabled=page>=pages;
}
async function openTicket(id){
  if(selected!==id)assignmentNotice=null;
  selected=id;const requestId=++ticketDetailRequestId;document.querySelector('[data-tab="tickets"]').click();
  try{
    const [t,history]=await Promise.all([api('/admin/tickets/'+id),api('/admin/tickets/'+id+'/history')]);
    if(requestId!==ticketDetailRequestId||selected!==id)return;
    renderDetail(t,history);await loadTickets();
  }catch(e){if(requestId===ticketDetailRequestId&&selected===id)fail(e);}
}
function renderDetail(t,history){
  const box=$('detail');box.replaceChildren();
  box.append(node('span','eyebrow','CHI TIẾT TICKET'),node('h2','',t.id),node('span','badge '+t.status,names[t.status]));
  if(assignmentNotice?.ticketId===t.id){const notice=node('p','notice-text',assignmentNotice.text);notice.setAttribute('role','status');box.append(notice);}
  const facts=node('dl','facts');
  [['Lý do chuyển',reasons[t.handover_reason]||t.handover_reason],['Độ tự tin AI',t.confidence_score===null?'Chưa ghi nhận':t.confidence_score],['Cán bộ',t.officer_name||'—'],['Tạo lúc',when(t.created)],['Nhận lúc',when(t.claimed_at)],['Kết thúc lúc',when(t.resolved_at)]]
    .forEach(([k,v])=>facts.append(node('dt','',k),node('dd','',String(v))));
  box.append(node('div','summary',t.summary),facts);
  box.append(node('h3','','Hội thoại trước khi chuyển'));
  if(!t.conversation.length)box.append(node('p','hint','Không còn lịch sử chat (ứng viên đã xóa hoặc phiên đã hết hạn).'));
  t.conversation.forEach(m=>{const item=node('div','message '+m.role);item.append(node('div','speaker',m.role==='user'?'Ứng viên':'Trợ lý AI'),node('div','body',m.text));
    m.sources.forEach(s=>{const card=node('details','source-card');const location=s.page?` · PDF trang ${s.page}${s.end_page&&s.end_page!==s.page?`–${s.end_page}`:''}`:s.source_type==='html'?' · Trang web':'';card.append(node('summary','',`Nguồn · ${s.title||'Tài liệu'}${location}`),node('div','quote',s.excerpt||''));if(s.local_url){const a=node('a','','Mở PDF');a.href=s.local_url;a.target='_blank';a.rel='noopener';card.append(a);}if(s.url){const a=node('a','','Nguồn chính thức');a.href=s.url;a.target='_blank';a.rel='noopener';card.append(a);}item.append(card);});
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
      button.disabled=true;try{
        const updated=await api('/admin/tickets/'+t.id+'/reassign',{method:'POST',body:JSON.stringify({to_officer_id:to,note:note.value})});
        assignmentNotice={ticketId:t.id,text:updated.officer_id?`Đã phân công ${t.id} cho ${updated.officer_name}. Ticket chuyển sang “Đang xử lý”.`:`Đã trả ${t.id} về hàng chờ.`};
        // Assignment changes the ticket's status and owner. Keep it visible after polling.
        $('status-filter').value=updated.status;
        $('officer-filter').value=updated.officer_id?String(updated.officer_id):'';
        persistFilters();page=1;
        try{await loadOfficers();}catch(refreshError){fail(refreshError);}
        await openTicket(t.id);
      }catch(e){err.textContent=e.message;button.disabled=false;}};
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
function passwordStatusCell(o){
  const cell=node('td');
  cell.dataset.label='Trạng thái mật khẩu';
  const labels={not_activated:'Chưa kích hoạt',activated:'Đã kích hoạt',reset_requested:'Đã yêu cầu đặt lại'};
  const status=o.account_status|| (o.password_status==='ready'?'activated':'not_activated');
  cell.append(node('span','password-status '+status,labels[status]||'Chưa xác định'));
  if(o.invite_sent_at)cell.append(node('small','hint','Email: '+when(o.invite_sent_at)));
  if(o.password_set_at)cell.append(node('small','hint','Cập nhật: '+when(o.password_set_at)));
  return cell;
}
function passwordResetCell(o){
  const cell=node('td');
  cell.dataset.label='Thao tác mật khẩu';
  if(o.password_status!=='ready'){
    const send=node('button','small-action','Gửi lại email');send.type='button';send.title='Gửi lại email thiết lập mật khẩu';
    send.onclick=async()=>{send.disabled=true;try{await api('/admin/officers/'+o.id+'/invite',{method:'POST'});await loadOfficers();}catch(error){fail(error);send.disabled=false;}};
    cell.append(send);return cell;
  }
  const emailReset=node('button','small-action',o.account_status==='reset_requested'?'Gửi lại link đặt lại':'Gửi link đặt lại');
  emailReset.type='button';emailReset.title='Gửi liên kết đặt lại mật khẩu qua email';
  emailReset.onclick=async()=>{emailReset.disabled=true;try{await api('/admin/officers/'+o.id+'/password-reset',{method:'POST'});await loadOfficers();}catch(error){fail(error);emailReset.disabled=false;}};
  cell.append(emailReset);
  const open=node('button','small-action','Đặt lại');open.type='button';open.title='Đặt mật khẩu mới cho cán bộ';
  const form=node('form','password-reset');form.hidden=true;
  const wrap=node('div','password-input');
  const input=document.createElement('input');input.type='password';input.id=`officer-password-${o.id}`;input.minLength=8;input.maxLength=200;input.autocomplete='new-password';input.placeholder='Mật khẩu mới';input.required=true;
  const inputLabel=node('label','sr-only','Mật khẩu mới');inputLabel.htmlFor=input.id;
  const eye=node('button','password-toggle','Hiện');eye.type='button';eye.setAttribute('aria-label','Hiện mật khẩu');bindPasswordToggle(eye,input);
  wrap.append(input,eye);
  const save=node('button','small-action','Lưu');save.type='submit';
  const error=node('p','error-text');error.setAttribute('role','alert');
  form.append(inputLabel,wrap,save,error);
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
  officers.forEach(o=>{const tr=node('tr','officer-card');const makeCell=(labelText,value,cls='')=>{const cell=node('td',cls,value);cell.dataset.label=labelText;return cell;};const toggle=makeCell('Hoạt động','');const label=node('label','switch');const input=node('input');input.type='checkbox';input.checked=o.active;input.setAttribute('aria-label',o.active?`Tài khoản cán bộ ${o.name} đang hoạt động`:`Khóa tài khoản cán bộ ${o.name}`);input.title=input.getAttribute('aria-label');
    input.onchange=async()=>{
      if(!input.checked){const msg=o.open_tickets?`Khóa cán bộ ${o.name}? ${o.open_tickets} ticket đang giữ sẽ được trả về hàng chờ để cán bộ khác tiếp nhận.`:`Khóa tài khoản cán bộ ${o.name}? Cán bộ sẽ không thể đăng nhập hoặc nhận ticket mới.`;if(!confirm(msg)){input.checked=true;return;}}
      input.disabled=true;try{await api('/admin/officers/'+o.id,{method:'PATCH',body:JSON.stringify({active:input.checked})});await refresh();}catch(e){fail(e);input.checked=!input.checked;input.disabled=false;}};
    label.append(input,node('span','',o.active?'Hoạt động':'Đã khóa'));toggle.append(label);
    tr.append(makeCell('Tên',o.name),makeCell('Tài khoản',o.username),makeCell('Email',o.email),makeCell('Đang giữ',String(o.open_tickets)),passwordStatusCell(o),passwordResetCell(o),toggle);$('officer-rows').append(tr);});
}
document.querySelectorAll('[data-password-toggle]').forEach(button=>bindPasswordToggle(button,$(button.dataset.passwordToggle)));
function validateOfficerForm(){const checks=[[$('o-name'),v=>v?'':'Họ và tên là bắt buộc.'],[$('o-username'),v=>/^[a-zA-Z0-9_.-]{3,40}$/.test(v)?'':'Tài khoản phải có 3–40 ký tự chữ, số, _ . - .'],[$('o-email'),v=>/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(v)?'':'Email cán bộ không đúng định dạng.']];for(const [input,message] of checks){input.removeAttribute('aria-invalid');if(!input.value.trim()||message(input.value.trim())){input.setAttribute('aria-invalid','true');$('officer-error').textContent=message(input.value.trim())||'Thông tin chưa hợp lệ.';input.focus();return false;}}return true;}
$('officer-form').addEventListener('submit',async e=>{e.preventDefault();$('officer-error').textContent='';if(!validateOfficerForm())return;const button=e.submitter;button.disabled=true;
  try{await api('/admin/officers',{method:'POST',body:JSON.stringify({name:$('o-name').value,username:$('o-username').value,email:$('o-email').value})});e.target.reset();await loadOfficers();}
  catch(error){$('officer-error').textContent=error.message;}finally{button.disabled=false;}});

// Wiring -------------------------------------------------------------------
async function refresh(options={}){
  const silent=options.silent===true;
  if(refreshInFlight)return;
  refreshInFlight=true;
  if(!silent)$('admin-error').textContent='';
  try{
    const preserveDraft=silent&&hasAdminDraft();
    if(!preserveDraft)await loadOfficers();
    await Promise.all([loadOverview(),loadTickets()]);
    if(selected&&!preserveDraft)await openTicketSilently(selected);
    markLiveUpdated();
  }catch(e){fail(e);}finally{refreshInFlight=false;}
}
async function openTicketSilently(id){
  const requestId=++ticketDetailRequestId;
  const [t,history]=await Promise.all([api('/admin/tickets/'+id),api('/admin/tickets/'+id+'/history')]);
  if(requestId!==ticketDetailRequestId||selected!==id)return;
  renderDetail(t,history);
}
$('range-form').addEventListener('submit',e=>{e.preventDefault();persistFilters();loadOverview().catch(fail);});
$('status-filter').onchange=$('officer-filter').onchange=()=>{selected=null;assignmentNotice=null;ticketDetailRequestId++;persistFilters();page=1;loadTickets().catch(fail);};
$('prev').onclick=()=>{page--;loadTickets().catch(fail);};$('next').onclick=()=>{page++;loadTickets().catch(fail);};
$('refresh').onclick=refresh;
$('login-form').addEventListener('submit',async e=>{e.preventDefault();$('login-error').textContent='';$('username-error').textContent='';$('password-error').textContent='';const username=$('username').value.trim(),password=$('password').value;$('username').removeAttribute('aria-invalid');$('password').removeAttribute('aria-invalid');const first=!username?'username':!password?'password':'';if(first){$(first).setAttribute('aria-invalid','true');$(`${first}-error`).textContent=first==='username'?'Tài khoản là bắt buộc.':'Mật khẩu là bắt buộc.';$(first).focus();return;}const button=e.submitter;button.disabled=true;
  try{await api('/admin/login',{method:'POST',body:JSON.stringify({username,password})});$('password').value='';showDashboard();await refresh();startAutoRefresh();}
  catch(error){const firstField=error.fields?.username?'username':error.fields?.password?'password':'';if(firstField){$(firstField).setAttribute('aria-invalid','true');$(`${firstField}-error`).textContent=error.fields[firstField];$(firstField).focus();}else $('login-error').textContent=error.message;}finally{button.disabled=false;}});
$('logout').onclick=async()=>{try{await api('/admin/logout',{method:'POST'});location.reload();}catch(e){fail(e);}};
(async()=>{try{const session=await api('/admin/session');if(!session.authenticated)return;showDashboard();await refresh();startAutoRefresh();}catch{/* Login form remains visible. */}})();
