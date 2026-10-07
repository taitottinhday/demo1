const $ = id => document.getElementById(id);
const accountLink=document.createElement('a');accountLink.className='staff-link';accountLink.href='/account';accountLink.textContent='Đăng nhập / đăng ký';document.querySelector('.topbar nav')?.prepend(accountLink);
const privacyNote=document.querySelector('.privacy');if(privacyNote)privacyNote.textContent='Bạn có thể dùng ẩn danh hoặc đăng nhập để lưu lịch sử và theo dõi yêu cầu.';
const stateNames = {waiting:'Đang chờ', in_progress:'Đang xử lý', resolved:'Đã giải quyết',cancelled:'Đã hủy',rejected:'Đã từ chối'};
let messages = [], programs = [], requestKey = '', busy = false;
function updateAccountNav(student){
  if(!student){
    if(!accountLink.isConnected)document.querySelector('.topbar nav')?.prepend(accountLink);
    return;
  }
  if(!accountLink.isConnected)return;
  const name=node('span','account-name',student.name || student.email);
  name.title=student.email;
  const logout=node('button','nav-link account-logout','\u0110\u0103ng xu\u1ea5t');
  logout.type='button';
  logout.onclick=async()=>{logout.disabled=true;try{await api('/auth/logout',{method:'POST'});location.href='/account';}catch(error){logout.disabled=false;$('chat-error').textContent=error.message;}};
  accountLink.replaceWith(name,logout);
}
function updateSuggestions(){
  const code=$('program').value;const box=$('follow-up');box.replaceChildren();
  const choices=code?[[`Phương thức ${code}`,`Phương thức xét tuyển ${code} là gì?`],[`Học phí ${code}`,`Học phí ${code} là bao nhiêu?`],[`Ngoại ngữ ${code}`,`Điều kiện ngoại ngữ ${code} là gì?`]]:[['Số ngành','HUST có bao nhiêu ngành?'],['Đăng ký ĐGTD','Cách đăng ký thi đánh giá tư duy?']];
  choices.forEach(([title,question])=>{const b=node('button','small-action',title);b.type='button';b.onclick=()=>{$('question').value=question;$('question').dispatchEvent(new Event('input'));$('question').focus();};box.append(b);});
}
async function api(path, options = {}) {
  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), 23000);
  try {
    const response = await fetch('/api/v1' + path, {...options, credentials:'include', signal:controller.signal, headers:{'Content-Type':'application/json', ...(options.headers || {})}});
    const data = await response.json();
    if (!response.ok) throw new Error(typeof data.detail === 'string' ? data.detail : 'Nội dung chưa hợp lệ. Vui lòng kiểm tra rồi thử lại.');
    return data;
  } catch (error) {
    if (error.name === 'AbortError') throw new Error('Yêu cầu chưa phản hồi kịp. Hãy thử lại; yêu cầu handover dùng cùng mã sẽ không bị tạo trùng.');
    throw error;
  } finally { clearTimeout(timeout); }
}
function node(tag, className, text) { const n=document.createElement(tag); if(className)n.className=className; if(text)n.textContent=text; return n; }
function link(label, url) { const n=node('a','',label); n.href=url; n.target='_blank'; n.rel='noopener'; return n; }
function addMessage(role, data, save=true) {
  $('welcome')?.remove();
  const box=node('article','message '+role);
  box.append(node('div','speaker',role==='user'?'BẠN':'TRỢ LÝ X'),node('div','body',data.response));
  (data.sources || []).forEach((source,i)=>{
    const card=node('details','source-card');
    card.append(node('summary','',`[${i+1}] ${source.title} · PDF trang ${source.page}${source.end_page!==source.page?'–'+source.end_page:''}`));
    card.append(node('div','quote',source.excerpt),link('Xem PDF trong ứng dụng ↗',source.local_url),link('Nguồn chính thức ↗',source.url));
    box.append(card);
  });
  if(role==='assistant') {
    const labels={answered:'Có nguồn',fallback:'Cần cán bộ kiểm tra',clarification:'Cần làm rõ',error:'Chưa xử lý được'};
    box.append(node('div','meta',`${data.reason==='out_of_scope'?'Ngoài phạm vi tuyển sinh':(labels[data.kind] || 'Trợ lý X')}${data.mode ? ' · '+(data.mode==='llm'?'AI tổng hợp':'Tra cứu tài liệu') : ''}${data.cached?' · Đã lưu đệm':''}`));
    const originalQuestion=[...messages].reverse().find(m=>m.role==='user')?.response || '';
    if(data.request_id){
      const actions=node('div','follow-up');const status=node('span','hint');status.setAttribute('role','status');
      const buttons=[];[['helpful','Hữu ích'],['incorrect','Chưa đúng']].forEach(([rating,title])=>{
        const b=node('button','small-action',title);b.type='button';b.setAttribute('aria-pressed',String(data.feedback===rating));buttons.push(b);
        b.onclick=async()=>{buttons.forEach(x=>x.disabled=true);try{await api('/answers/'+data.request_id+'/feedback',{method:'POST',body:JSON.stringify({rating})});data.feedback=rating;buttons.forEach(x=>x.setAttribute('aria-pressed',String(x===b)));status.textContent=rating==='incorrect'?'Đã ghi nhận. Bạn có thể gửi câu hỏi cho cán bộ.':'Đã ghi nhận đánh giá.';}catch(e){status.textContent=e.message;}finally{buttons.forEach(x=>x.disabled=false);}};actions.append(b);
      });actions.append(status);box.append(actions);
    }
    if(data.request_id&&data.reason!=='out_of_scope') {const b=node('button','small-action','Chuyển câu hỏi này cho cán bộ ↗');b.type='button';b.onclick=()=>openHandover(originalQuestion,data.response);box.append(b);}
  }
  $('messages').append(box);
  $('messages').scrollTop=$('messages').scrollHeight;
  if(save)messages.push({role,...data});
}
async function init() {
  try {
    const [status, list, session] = await Promise.all([api('/status'),api('/programs'),api('/session')]);
    programs=list;
    list.forEach(p=>{const option=node('option','',`${p.code} · ${p.name}`);option.value=p.code;$('program').append(option);});
    $('program').value=session.program || '';
    updateAccountNav(session.student);
    updateSuggestions();
    session.messages.forEach(m=>addMessage(m.role,m));
    $('source-status').textContent=status.status==='ready'?`${status.source.pages} trang PDF · ${status.programs} chương trình · kỳ 2026`:'Nguồn chưa sẵn sàng. Có thể chuyển cán bộ.';
    $('mode-label').textContent=status.mode==='llm'?'AI tổng hợp có kiểm tra trích dẫn.':'Đang dùng chế độ tra cứu tài liệu.';
    $('ticket-count').textContent=session.tickets.length;
  } catch(error) { $('chat-error').textContent='Không kết nối được ứng dụng: '+error.message; }
}
$('question').addEventListener('input',()=>{$('char-count').textContent=$('question').value.length+' / 2000';});
$('question').addEventListener('keydown',e=>{if(e.key==='Enter'&&!e.shiftKey){e.preventDefault();$('chat-form').requestSubmit();}});
$('chat-form').addEventListener('submit',async e=>{
  e.preventDefault();const question=$('question').value.trim();if(!question||busy)return;
  busy=true;$('send').disabled=true;$('clear').disabled=true;$('chat-error').textContent='';
  addMessage('user',{response:question});
  const loading=node('div','message assistant','Đang tra cứu tài liệu…');loading.id='loading';$('messages').append(loading);loading.scrollIntoView({block:'nearest'});
  try {
    const data=await api('/chat',{method:'POST',body:JSON.stringify({message:question,program:$('program').value})});
    loading.remove();addMessage('assistant',data);$('program').value=data.program || '';updateSuggestions();$('question').value='';$('char-count').textContent='0 / 2000';
  } catch(error){loading.remove();$('chat-error').textContent=error.message+' Nội dung vẫn ở ô nhập để thử lại.';}
  finally{busy=false;$('send').disabled=false;$('clear').disabled=false;$('question').focus();}
});
document.querySelectorAll('[data-question]').forEach(b=>b.addEventListener('click',()=>{$('question').value=b.dataset.question;$('question').dispatchEvent(new Event('input'));$('question').focus();}));
$('program').addEventListener('change',updateSuggestions);
$('clear').addEventListener('click',async()=>{
  if(!confirm('Xóa lịch sử và ngữ cảnh chat? Ticket đã gửi vẫn được giữ.'))return;
  try {const data=await api('/session/messages',{method:'DELETE'});messages=[];$('messages').replaceChildren();$('program').value='';updateSuggestions();addMessage('assistant',{response:data.message,kind:'clarification'},false);}
  catch(error){$('chat-error').textContent=error.message;}
});
function openHandover(question=null,answer=null) {
  const last=[...messages].reverse().find(m=>m.role==='user');
  $('summary').value=typeof question==='string'?`Câu hỏi: ${question}\n\nCâu trả lời cần kiểm tra: ${(answer||'').slice(0,900)}`:(last?.response || $('question').value);
  $('consent').checked=false;$('handover-error').textContent='';requestKey=crypto.randomUUID();$('handover-dialog').showModal();$('summary').focus();
}
$('handover-open').onclick=openHandover;
document.querySelectorAll('[data-close]').forEach(b=>b.onclick=()=>$(b.dataset.close).close());
$('handover-form').addEventListener('submit',async e=>{
  e.preventDefault();$('handover-send').disabled=true;$('handover-error').textContent='';
  try {
    await api('/handover',{method:'POST',body:JSON.stringify({summary:$('summary').value,consent:$('consent').checked,request_key:requestKey,reason:'candidate_request'})});
    $('handover-dialog').close();$('track-dialog').showModal();await loadTickets();
  }catch(error){$('handover-error').textContent=error.message;}finally{$('handover-send').disabled=false;}
});
async function loadTickets(){
  try {const list=await api('/tickets');$('ticket-count').textContent=list.length;$('tickets').replaceChildren();
    if($('track-dialog').open&&typeof markRepliesSeen==='function')markRepliesSeen(list);
    if(!list.length)$('tickets').append(node('p','empty-state','Chưa có yêu cầu. Bạn có thể chuyển câu hỏi từ màn hình chat.'));
    list.forEach(t=>{const card=node('article','ticket-card');const head=node('div','ticket-head');head.append(node('b','',t.id),node('span','badge '+t.status,stateNames[t.status]));card.append(head,node('p','',t.summary),node('small','hint',new Date(t.created*1000).toLocaleString('vi-VN')));if(['waiting','in_progress'].includes(t.status)){const cancel=node('button','secondary danger','Hủy yêu cầu');const error=node('p','error-text');error.setAttribute('role','alert');cancel.onclick=async()=>{if(!confirm('Hủy yêu cầu '+t.id+'? Cán bộ sẽ không tiếp tục xử lý yêu cầu này.'))return;cancel.disabled=true;try{await api('/tickets/'+t.id+'/cancel',{method:'POST'});await loadTickets();}catch(e){error.textContent=e.message;cancel.disabled=false;}};card.append(cancel,error);}if(t.reply)card.append(node('div','reply-box',t.reply));$('tickets').append(card);});
  }catch(error){$('tickets').replaceChildren(node('p','error-text',error.message));}
}
$('track-open').onclick=()=>{$('track-dialog').showModal();loadTickets();};$('refresh-tickets').onclick=loadTickets;
setInterval(()=>{if($('track-dialog').open)loadTickets();},10000);
$('guide-open').onclick=async()=>{
  $('guide-dialog').showModal();
  if($('guide-content').children.length)return;
  try{const guide=await api('/guide');$('guide-content').append(node('p','',guide.note));
    guide.steps.forEach((s,i)=>{const card=node('article','ticket-card');const label=node('label','checkbox-label');const check=document.createElement('input');check.type='checkbox';check.checked=sessionStorage.getItem('guide-'+i)==='done';check.onchange=()=>sessionStorage.setItem('guide-'+i,check.checked?'done':'');label.append(check,node('span','',s.title));card.append(label,node('p','',s.text),link('Mở hướng dẫn / nguồn ↗',s.url));$('guide-content').append(card);});
  }catch(error){$('guide-content').append(node('p','error-text',error.message));}
};
init();
$('compare-open').onclick=()=>{
  const box=$('compare-selects');box.replaceChildren();$('compare-error').textContent='';
  for(let i=0;i<3;i++){const label=node('label','',`Chương trình ${i+1}${i===2?' (tùy chọn)':''}`);const select=node('select');select.id='compare-'+i;label.htmlFor=select.id;
    const empty=node('option','','Chọn chương trình');empty.value='';select.append(empty);
    programs.forEach(p=>{const option=node('option','',p.code+' · '+p.name);option.value=p.code;select.append(option);});
    if(i===0)select.value=$('program').value;box.append(label,select);
  }
  $('compare-dialog').showModal();
};
$('compare-form').onsubmit=async e=>{
  e.preventDefault();$('compare-error').textContent='';$('comparison-result').replaceChildren();const button=$('compare-submit');button.disabled=true;
  try{const codes=[0,1,2].map(i=>$('compare-'+i).value).filter(Boolean);const data=await api('/programs/compare',{method:'POST',body:JSON.stringify({codes})});
    const wrap=node('div','comparison-scroll');const table=node('table','comparison-table');const caption=node('caption','','Thông tin chương trình tuyển sinh 2026');table.append(caption);
    const header=node('tr');header.append(node('th','','Thông tin'));data.programs.forEach(p=>header.append(node('th','',p.code+' · '+p.name)));table.append(header);
    [['quota','Chỉ tiêu','program'],['methods','Phương thức / tổ hợp','program'],['fee','Học phí dự kiến','fee'],['language','Ngoại ngữ đầu vào','language'],['note','Ghi chú chương trình','program']].forEach(([key,label,sourceKey])=>{
      const row=node('tr');row.append(node('th','',label));data.programs.forEach(p=>{const cell=node('td','',p[key]);const source=p.sources[sourceKey];if(source)cell.append(node('br'),link('Nguồn · PDF trang '+source.page,source.local_url));if(key==='language')cell.append(node('br'),link('Thông tin chương trình · trang '+p.sources.program.page,p.sources.program.local_url));row.append(cell);});table.append(row);
    });wrap.append(table);$('comparison-result').append(wrap);
  }catch(error){$('compare-error').textContent=error.message;}finally{button.disabled=false;}
};

const seenKey="hust-replies-seen-v1";
function readLocal(key,fallback){try{return JSON.parse(localStorage.getItem(key))||fallback;}catch{return fallback;}}
try{localStorage.removeItem("hust-plan-2026-v1");}catch{}
async function checkReplies(){
  if(document.hidden)return;
  try{const tickets=await api('/tickets');$('ticket-count').textContent=tickets.length;const seen=readLocal(seenKey,{});let count=0;
    tickets.forEach(t=>{if(t.reply&&seen[t.id]!==t.updated)count++;});const badge=$('reply-unread');badge.hidden=count===0;badge.textContent=count+' phản hồi mới';
  }catch{/* A temporary connection failure keeps the last successful notification. */}
}
function markRepliesSeen(tickets){
  const seen={};tickets.forEach(t=>{if(t.reply)seen[t.id]=t.updated;});try{localStorage.setItem(seenKey,JSON.stringify(seen));$('reply-unread').hidden=true;}catch{/* Do not mark read if storage is unavailable. */}
}
setTimeout(checkReplies,1500);setInterval(checkReplies,15000);document.addEventListener('visibilitychange',()=>{if(!document.hidden)checkReplies();});
