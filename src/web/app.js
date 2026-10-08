const $ = id => document.getElementById(id);
const accountLink=document.querySelector('#account-nav')||document.createElement('a');accountLink.classList.add('role-menu-item');accountLink.href='/account';if(!accountLink.textContent.trim())accountLink.textContent='Đăng nhập học viên';if(!accountLink.isConnected)document.querySelector('#role-menu-student')?.append(accountLink);
const roleMenu=$('role-menu'),roleMenuTrigger=$('role-menu-trigger');
document.addEventListener('click',event=>{if(roleMenu?.open&&!roleMenu.contains(event.target))roleMenu.open=false;});
document.addEventListener('keydown',event=>{if(event.key==='Escape'&&roleMenu?.open){roleMenu.open=false;roleMenuTrigger?.focus();event.preventDefault();event.stopImmediatePropagation();}});
const privacyNote=document.querySelector('.privacy');if(privacyNote)privacyNote.textContent='Không gửi thông tin cá nhân nhạy cảm.';
const toolsToggle=$('tools-toggle'),toolsBackdrop=$('tools-backdrop');
function setToolsOpen(open){document.body.classList.toggle('tools-open',open);toolsToggle?.setAttribute('aria-expanded',String(open));toolsToggle?.setAttribute('aria-label',open?'Đóng danh mục tra cứu':'Mở danh mục tra cứu');if(window.innerWidth<=820){sidebarToggle?.setAttribute('aria-expanded',String(open));sidebarToggle?.setAttribute('aria-label',open?'Đóng danh mục':'Mở danh mục tra cứu');sidebarToggle?.setAttribute('title',open?'Đóng danh mục':'Mở danh mục tra cứu');}if(open)(document.querySelector('#program-picker:not(:disabled)')||document.querySelector('.topics button'))?.focus();else if(window.innerWidth<=820)toolsToggle?.focus();}
toolsToggle?.addEventListener('click',()=>setToolsOpen(!document.body.classList.contains('tools-open')));
toolsBackdrop?.addEventListener('click',()=>setToolsOpen(false));
document.addEventListener('keydown',event=>{if(event.key==='Escape'&&!document.querySelector('dialog[open]'))setToolsOpen(false);});
window.addEventListener('resize',()=>{if(window.innerWidth>820)setToolsOpen(false);});
const sidebarToggle=$('sidebar-toggle'),sidebarCollapsedKey='hust-sidebar-collapsed-v1';
function setSidebarCollapsed(collapsed,moveFocus=false){
  document.body.classList.toggle('sidebar-collapsed',collapsed);
  sidebarToggle?.setAttribute('aria-expanded',String(!collapsed));
  sidebarToggle?.setAttribute('aria-label',collapsed?'Mở danh mục tra cứu':'Thu gọn danh mục');
  sidebarToggle?.setAttribute('title',collapsed?'Mở danh mục tra cứu':'Thu gọn danh mục');
  $('rail-expand')?.setAttribute('aria-expanded',String(!collapsed));
  if(window.innerWidth>820){try{localStorage.setItem(sidebarCollapsedKey,collapsed?'1':'0');}catch{}}
  if(moveFocus)requestAnimationFrame(()=>$(collapsed?'rail-expand':'sidebar-toggle')?.focus());
}
try{if(window.innerWidth>820&&localStorage.getItem(sidebarCollapsedKey)==='1')setSidebarCollapsed(true);}catch{}
sidebarToggle?.addEventListener('click',()=>{if(window.innerWidth<=820)setToolsOpen(false);else setSidebarCollapsed(!document.body.classList.contains('sidebar-collapsed'),true);});
$('rail-expand')?.addEventListener('click',()=>setSidebarCollapsed(false,true));
$('rail-program')?.addEventListener('click',()=>programPicker.click());
$('rail-compare')?.addEventListener('click',()=>$('compare-open').click());
$('rail-guide')?.addEventListener('click',()=>$('guide-open').click());
const stateNames = {waiting:'Đang chờ', in_progress:'Đang xử lý', resolved:'Đã giải quyết',cancelled:'Đã hủy',rejected:'Đã từ chối'};
let messages = [], programs = [], requestKey = '', busy = false;
const programDialog=$('program-dialog'), programPicker=$('program-picker');
function searchKey(value){return String(value||'').normalize('NFD').replace(/[\u0300-\u036f]/g,'').replace(/đ/g,'d').toLowerCase();}
function renderProgramSelection(){
  const selected=programs.find(item=>item.code===$('program').value);
  const label=selected?`${selected.code} · ${selected.name}`:'Chưa chọn ngành';
  programPicker.disabled=programs.length===0;
  $('program-selected-name').textContent=label;
  programPicker.classList.toggle('has-selection',Boolean(selected));
  programPicker.setAttribute('aria-label',selected?`Ngành quan tâm: ${label}. Thay đổi ngành`:'Chọn ngành quan tâm');
}
function renderProgramResults(query=''){
  const list=$('program-results'), normalized=searchKey(query.trim());
  list.replaceChildren();
  let matches;
  if(normalized){
    matches=programs.filter(item=>searchKey(`${item.code} ${item.name}`).includes(normalized));
    $('program-results-label').textContent='Kết quả tìm kiếm';
    $('program-results-count').textContent=`${matches.length} ngành`;
    matches=matches.slice(0,8);
  }else{
    const preferred=['IT1','IT2','ITE10'].map(code=>programs.find(item=>item.code===code)).filter(Boolean);
    const selected=programs.find(item=>item.code===$('program').value);
    matches=selected&&!preferred.some(item=>item.code===selected.code)?[selected,...preferred.slice(0,2)]:preferred;
    $('program-results-label').textContent=selected?'Đang chọn & gợi ý':'Gợi ý phổ biến';
    $('program-results-count').textContent=`${matches.length} ngành`;
  }
  if(!matches.length){list.append(node('p','program-empty','Không tìm thấy ngành phù hợp. Thử mã ngành hoặc tên khác.'));return;}
  matches.forEach(item=>{
    const button=node('button','program-option');button.type='button';button.setAttribute('aria-pressed',String(item.code===$('program').value));
    button.append(node('span','program-code',item.code),node('span','program-name',item.name));
    if(item.code===$('program').value){const check=node('span','program-selected-mark','Đang chọn');check.setAttribute('aria-hidden','true');button.append(check);}
    button.onclick=()=>{$('program').value=item.code;renderProgramSelection();updateSuggestions();programPicker.setAttribute('aria-expanded','false');programDialog.close();};
    list.append(button);
  });
}
function openProgramPicker(){
  $('program-search').value='';renderProgramResults();
  programPicker.setAttribute('aria-expanded','true');programDialog.showModal();$('program-search').focus();
}
programPicker.addEventListener('click',openProgramPicker);
$('program-search').addEventListener('input',event=>renderProgramResults(event.currentTarget.value));
$('program-search').addEventListener('keydown',event=>{if(event.key==='Enter'&&searchKey(event.currentTarget.value.trim())){event.preventDefault();$('program-results').querySelector('.program-option')?.click();}});
$('program-clear').addEventListener('click',()=>{$('program').value='';renderProgramSelection();updateSuggestions();programPicker.setAttribute('aria-expanded','false');programDialog.close();});
programDialog.addEventListener('close',()=>{programPicker.setAttribute('aria-expanded','false');programPicker.focus();});
programDialog.addEventListener('click',event=>{if(event.target===programDialog)programDialog.close();});
function updateAccountNav(student){
  if(!student){
    $('role-menu-label').textContent='Đăng nhập';
    if(!accountLink.isConnected)document.querySelector('#role-menu-student')?.append(accountLink);
    return;
  }
  if(!accountLink.isConnected)return;
  $('role-menu-label').textContent='Tài khoản';
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
    $('program').value=session.program || '';
    renderProgramSelection();
    updateAccountNav(session.student);
    updateSuggestions();
    session.messages.forEach(m=>addMessage(m.role,m));
    $('source-status').textContent=status.status==='ready'?`${status.source.pages} trang PDF · ${status.programs} chương trình · kỳ 2026`:'Nguồn chưa sẵn sàng. Có thể chuyển cán bộ.';
    $('mode-label').textContent=status.mode==='llm'?'AI tổng hợp có kiểm tra trích dẫn.':'Đang dùng chế độ tra cứu tài liệu.';
    $('ticket-count').textContent=session.tickets.length;
  } catch(error) { $('chat-error').textContent='Không kết nối được ứng dụng: '+error.message; }
}
$('question').addEventListener('input',()=>{
  const field=$('question');$('char-count').textContent=field.value.length+' / 2000';
  field.style.height='auto';const maxHeight=116;field.style.height=Math.min(field.scrollHeight,maxHeight)+'px';field.style.overflowY=field.scrollHeight>maxHeight?'auto':'hidden';
});
$('question').addEventListener('keydown',e=>{if(e.key==='Enter'&&!e.shiftKey){e.preventDefault();$('chat-form').requestSubmit();}});
$('chat-form').addEventListener('submit',async e=>{
  e.preventDefault();const question=$('question').value.trim();if(!question||busy)return;
  busy=true;$('send').disabled=true;$('clear').disabled=true;$('chat-error').textContent='';
  addMessage('user',{response:question});
  const loading=node('div','message assistant','Đang tra cứu tài liệu…');loading.id='loading';$('messages').append(loading);loading.scrollIntoView({block:'nearest'});
  try {
    const data=await api('/chat',{method:'POST',body:JSON.stringify({message:question,program:$('program').value})});
    loading.remove();addMessage('assistant',data);$('program').value=data.program || '';renderProgramSelection();updateSuggestions();$('question').value='';$('question').style.height='';$('question').style.overflowY='hidden';$('char-count').textContent='0 / 2000';
  } catch(error){loading.remove();$('chat-error').textContent=error.message+' Nội dung vẫn ở ô nhập để thử lại.';}
  finally{busy=false;$('send').disabled=false;$('clear').disabled=false;$('question').focus();}
});
document.querySelectorAll('[data-question]').forEach(b=>b.addEventListener('click',()=>{$('question').value=b.dataset.question;$('question').dispatchEvent(new Event('input'));$('question').focus();}));
$('clear').addEventListener('click',async()=>{
  if(!confirm('Xóa lịch sử và ngữ cảnh chat? Ticket đã gửi vẫn được giữ.'))return;
  try {const data=await api('/session/messages',{method:'DELETE'});messages=[];$('messages').replaceChildren();$('program').value='';renderProgramSelection();updateSuggestions();addMessage('assistant',{response:data.message,kind:'clarification'},false);}
  catch(error){$('chat-error').textContent=error.message;}
});
function openHandover(question=null,answer=null) {
  const last=[...messages].reverse().find(m=>m.role==='user');
  $('summary').value=typeof question==='string'?`Câu hỏi: ${question}\n\nCâu trả lời cần kiểm tra: ${(answer||'').slice(0,900)}`:(last?.response || $('question').value);
  $('consent').checked=false;$('handover-error').textContent='';requestKey=crypto.randomUUID();$('handover-dialog').showModal();$('summary').focus();
}
$('handover-open').onclick=openHandover;
document.querySelectorAll('[data-close]').forEach(b=>b.onclick=()=>{const target=$(b.dataset.close);if(target===programDialog)programPicker.setAttribute('aria-expanded','false');target.close();if(target===programDialog)programPicker.focus();});
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
let compareCodes=['','',''],compareActive=-1,compareQuery='';
function updateCompareState(){
  const count=compareCodes.filter(Boolean).length;
  $('compare-selection-hint').textContent=count<2?`Đã chọn ${count}/2 ngành bắt buộc`:`Đã chọn ${count} ngành${count===2?' · Có thể thêm ngành thứ 3':''}`;
  $('compare-submit').disabled=count<2;
}
function renderCompareResults(index,list,countLabel){
  const query=searchKey(compareQuery.trim()),used=compareCodes.filter((code,slot)=>slot!==index&&code);
  let matches;
  if(query){
    matches=programs.filter(item=>!used.includes(item.code)&&searchKey(`${item.code} ${item.name}`).includes(query));
    countLabel.textContent=matches.length>6?`${matches.length} kết quả · Hiển thị 6`:`${matches.length} kết quả`;
  }else{
    const selected=programs.find(item=>item.code===compareCodes[index]&&!used.includes(item.code));
    const suggested=['IT1','IT2','ITE10'].map(code=>programs.find(item=>item.code===code)).filter(item=>item&&!used.includes(item.code)&&item.code!==selected?.code);
    matches=[...(selected?[selected]:[]),...suggested].slice(0,4);
    countLabel.textContent='Gợi ý phổ biến';
  }
  list.replaceChildren();
  if(!matches.length){list.append(node('p','compare-empty','Không tìm thấy ngành phù hợp. Thử mã hoặc tên ngành khác.'));return;}
  matches.slice(0,6).forEach(item=>{
    const option=node('button','compare-program-option');option.type='button';option.setAttribute('role','option');option.setAttribute('aria-selected',String(item.code===compareCodes[index]));
    const copy=node('span','compare-program-copy');copy.append(node('b','',item.code),node('span','',item.name));option.append(copy,node('span','compare-program-mark',item.code===compareCodes[index]?'Đang chọn':'Chọn'));
    option.onclick=()=>{
      compareCodes[index]=item.code;compareQuery='';
      compareActive=index===0&&!compareCodes[1]?1:-1;
      renderComparePickers();updateCompareState();
      document.getElementById(compareActive>=0?`compare-search-${compareActive}`:`compare-pick-${index}`)?.focus();
    };
    list.append(option);
  });
}
function renderComparePickers(){
  const box=$('compare-selects');box.replaceChildren();
  for(let i=0;i<3;i++){
    const card=node('section','compare-picker'+(i===2?' compare-picker-optional':''));card.setAttribute('aria-label',`Chương trình ${i+1}${i===2?' tùy chọn':''}`);
    const heading=node('div','compare-picker-heading');heading.append(node('span','compare-slot-number',String(i+1).padStart(2,'0')),node('span','compare-slot-label',i===2?'Chương trình 3 · Tùy chọn':`Chương trình ${i+1}`));card.append(heading);
    if(i===2&&!compareCodes[i]&&compareActive!==i){
      card.classList.add('compare-picker-add');const add=node('button','compare-add-button');add.type='button';add.setAttribute('aria-label','Thêm chương trình thứ 3 để so sánh');add.append(node('span','compare-add-symbol','+'),node('span','compare-add-copy','Thêm chương trình thứ 3'),node('small','','Không bắt buộc'));add.onclick=()=>openComparePicker(2);card.append(add);box.append(card);continue;
    }
    const selected=programs.find(item=>item.code===compareCodes[i]);
    const trigger=node('button','compare-picker-trigger');trigger.type='button';trigger.id=`compare-pick-${i}`;trigger.setAttribute('aria-haspopup','listbox');trigger.setAttribute('aria-expanded',String(compareActive===i));trigger.setAttribute('aria-controls',`compare-options-${i}`);trigger.setAttribute('aria-label',selected?`Thay đổi chương trình ${i+1}: ${selected.code} ${selected.name}`:`Chọn chương trình ${i+1}`);
    const value=node('span','compare-picker-value');value.append(node('b','',selected?selected.code:'Chọn ngành'),node('small','',selected?selected.name:'Tìm theo mã hoặc tên ngành'));
    const chevron=node('span','compare-picker-chevron','⌄');chevron.setAttribute('aria-hidden','true');trigger.append(value,chevron);trigger.onclick=()=>openComparePicker(i);card.append(trigger);
    if(i===2&&selected){const remove=node('button','compare-remove','Bỏ ngành thứ 3');remove.type='button';remove.onclick=()=>{compareCodes[2]='';compareActive=-1;compareQuery='';renderComparePickers();updateCompareState();};card.append(remove);}
    if(compareActive===i){
      const searchLabel=node('label','sr-only',`Tìm chương trình ${i+1}`);searchLabel.htmlFor=`compare-search-${i}`;
      const search=node('input','compare-search');search.id=`compare-search-${i}`;search.type='search';search.autocomplete='off';search.placeholder='Tìm theo mã hoặc tên ngành';search.setAttribute('aria-label',`Tìm chương trình ${i+1} theo mã hoặc tên ngành`);search.value=compareQuery;
      const count=node('span','compare-results-count');const results=node('div','compare-results');results.id=`compare-options-${i}`;results.setAttribute('role','listbox');results.setAttribute('aria-label',`Kết quả chương trình ${i+1}`);
      renderCompareResults(i,results,count);search.addEventListener('input',()=>{compareQuery=search.value;renderCompareResults(i,results,count);});
      search.addEventListener('keydown',event=>{if(event.key==='Enter'){event.preventDefault();results.querySelector('.compare-program-option')?.click();}});
      const picker=node('div','compare-picker-search');picker.append(searchLabel,search,count,results);card.append(picker);
    }
    box.append(card);
  }
}
function openComparePicker(index){compareActive=index;compareQuery='';renderComparePickers();document.getElementById(`compare-search-${index}`)?.focus();}
$('compare-selects').addEventListener('keydown',event=>{if(event.key==='Escape'&&compareActive>=0){event.preventDefault();const index=compareActive;compareActive=-1;compareQuery='';renderComparePickers();document.getElementById(`compare-pick-${index}`)?.focus();}});
$('compare-dialog').addEventListener('keydown',event=>{if(event.key==='Escape'&&compareActive>=0){event.preventDefault();const index=compareActive;compareActive=-1;compareQuery='';renderComparePickers();document.getElementById(`compare-pick-${index}`)?.focus();}});
$('compare-open').onclick=()=>{
  compareCodes=['','',''];const selected=$('program').value;if(selected)compareCodes[0]=selected;
  compareActive=selected?1:0;compareQuery='';$('compare-error').textContent='';$('comparison-result').replaceChildren();
  renderComparePickers();updateCompareState();$('compare-dialog').showModal();
  document.getElementById(`compare-search-${compareActive}`)?.focus();
};
$('compare-form').onsubmit=async e=>{
  e.preventDefault();$('compare-error').textContent='';$('comparison-result').replaceChildren();const button=$('compare-submit');
  const codes=compareCodes.filter(Boolean);if(codes.length<2){$('compare-error').textContent='Chọn ít nhất 2 chương trình để so sánh.';return;}button.disabled=true;
  try{const data=await api('/programs/compare',{method:'POST',body:JSON.stringify({codes})});
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
