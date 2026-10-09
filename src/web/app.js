const $ = id => document.getElementById(id);
const accountLink=document.createElement('a');accountLink.className='staff-link';accountLink.href='/account';accountLink.textContent='Đăng nhập';const accountNav=document.querySelector('.topbar nav');accountNav?.insertBefore(accountLink,accountNav.querySelector('.staff-login-link'));
const privacyNote=document.querySelector('.privacy');if(privacyNote)privacyNote.textContent='Bạn có thể dùng ẩn danh hoặc đăng nhập để lưu lịch sử và theo dõi yêu cầu.';
const stateNames = {waiting:'Đang chờ', in_progress:'Đang xử lý', resolved:'Đã giải quyết',cancelled:'Đã hủy',rejected:'Đã từ chối'};
let messages = [], programs = [], requestKey = '', busy = false, currentStudent = null, guideData = null, guideCompleted = new Set(), guideStorage = null, handoverPreview = {question:'', ai_answer:'', sources:[]};
let guidanceAreas = null, guidanceOptionsPromise = null, guidanceController = null, guidanceRequestId = 0, guidanceStep = 1;
const guideStorageKey = 'hust-guide-checklist-v2';
const questionDraftKey = 'hust-question-draft-v1';
function updateAccountNav(student){
  if(!student){
    if(!accountLink.isConnected){const nav=document.querySelector('.topbar nav');nav?.insertBefore(accountLink,nav.querySelector('.staff-login-link'));}
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
function fold(value){return String(value||'').normalize('NFD').replace(/[\u0300-\u036f]/g,'').toLowerCase().replace(/\s+/g,' ').trim();}
function displayProgramName(program){return String(program?.name||'').replace(/^CNTT:\s*/i,'').trim() || program?.code || '';}
function programLabel(code){const program=programs.find(item=>item.code===code);return program?`${program.code} · ${displayProgramName(program)}`:code;}
function programGroup(program){
  const name=fold(program.name);
  if(/quoc te|tien tien|global|elitech/.test(name))return 'Chương trình tiên tiến / quốc tế';
  if(program.major_code)return `Ngành ${program.major_code}`;
  return 'Chương trình khác';
}
function renderProgramOptions(){
  const select=$('program');const selected=select.value;select.replaceChildren();
  const empty=node('option','','Chưa chọn chương trình');empty.value='';select.append(empty);
  const groups=new Map();programs.forEach(program=>{const group=programGroup(program);if(!groups.has(group))groups.set(group,[]);groups.get(group).push(program);});
  groups.forEach((items,label)=>{
    const target=document.createElement('optgroup');target.label=label;
    items.forEach(program=>{const option=node('option','',programLabel(program.code));option.value=program.code;target.append(option);});
    select.append(target);
  });
  const datalist=$('program-options');datalist.replaceChildren();
  programs.forEach(program=>{const option=document.createElement('option');option.value=programLabel(program.code);option.label=program.name;datalist.append(option);});
  if(programs.some(program=>program.code===selected))select.value=selected;
}
function renderProgramScope(){
  const code=$('program').value;const chip=$('program-scope');
  if(!code){chip.hidden=true;$('program-scope-label').textContent='';return;}
  chip.hidden=false;$('program-scope-label').textContent=`Đang hỏi về ${programLabel(code)}`;
}
function setProgram(code, announce=false){
  const value=programs.some(program=>program.code===code)?code:'';
  $('program').value=value;
  $('program-search').value=value?programLabel(value):'';
  if(announce&&value)$('program-search-status').textContent=`Đã chọn ${programLabel(value)}.`;
  if(!value&&!code)$('program-search-status').textContent='';
  renderProgramScope();updateSuggestions();renderScope();
}
function resolveProgramSearch(value){
  const query=fold(value);if(!query)return null;
  const exact=programs.find(program=>[program.code,program.name,displayProgramName(program),programLabel(program.code)].some(candidate=>fold(candidate)===query));
  if(exact)return exact;
  const codePrefix=programs.filter(program=>query===fold(program.code) || fold(programLabel(program.code)).startsWith(query));
  return codePrefix.length===1?codePrefix[0]:null;
}
function handleProgramSearch(closeSuggestions=false){
  const input=$('program-search');const value=input.value.trim();
  if(!value){setProgram('');return;}
  const match=resolveProgramSearch(value);
  if(match){setProgram(match.code,true);if(closeSuggestions)input.blur();return;}
  $('program-search-status').textContent='Chưa tìm thấy duy nhất. Hãy chọn một mã hoặc tên trong danh sách gợi ý.';
}
function fillQuestion(question){
  $('question').value=question;$('question').dispatchEvent(new Event('input',{bubbles:true}));
  $('question-status').textContent='Đã điền câu hỏi — nhấn Gửi để tra cứu';$('question').focus();
}
function redactHandoverText(value){
  return String(value||'').replace(/(mật khẩu|password)\s*[:=]\s*[^\s,;]+/gi,'$1: [đã ẩn mật khẩu]').replace(/[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}/g,'[đã ẩn email]').replace(/(?<!\w)(?:\+84|0)?\d[\d .-]{7,}\d(?!\w)/g,'[đã ẩn số định danh/liên hệ]');
}
function quickQuestion(button){
  const template=button.dataset.programQuestion;const code=$('program').value;
  return template&&code?template.replace('{code}',code):button.dataset.question;
}
function updateSuggestions(){
  const code=$('program').value;const box=$('follow-up');box.replaceChildren();
  const choices=code?[[`Phương thức ${code}`,`Phương thức xét tuyển ${code} là gì?`],[`Học phí ${code}`,`Học phí ${code} là bao nhiêu?`],[`Ngoại ngữ ${code}`,`Điều kiện ngoại ngữ ${code} là gì?`]]:[['Số ngành','HUST có bao nhiêu ngành?'],['Đăng ký ĐGTD','Cách đăng ký thi đánh giá tư duy?']];
  const seen=new Set();choices.forEach(([title,question])=>{if(seen.has(question))return;seen.add(question);const b=node('button','small-action',title);b.type='button';b.onclick=()=>fillQuestion(question);box.append(b);});
}
function scopeLabel(data={}){
  if(data.scope==='program'&&data.scope_program)return `Phạm vi trả lời: ${programLabel(data.scope_program)}.`;
  if(data.scope==='ambiguous')return 'Phạm vi chưa rõ: hãy chọn hoặc ghi rõ chương trình.';
  if(data.scope==='general')return 'Phạm vi trả lời: toàn trường HUST 2026.';
  const selected=$('program').value;
  return selected?`Ngữ cảnh câu tiếp theo: ${programLabel(selected)}. Câu hỏi toàn trường vẫn được trả lời theo phạm vi toàn trường.`:'Phạm vi trả lời: toàn trường HUST 2026.';
}
function renderScope(data){
  $('scope-status').textContent=scopeLabel(data);
  const scopePill=$('scope-pill-label');
  if(scopePill){
    const label=data?.scope==='program'&&data.scope_program
      ? programLabel(data.scope_program)
      : data?.scope==='ambiguous'?'Cần làm rõ':data?.scope==='general'?'Toàn trường':$('program').value?programLabel($('program').value):'Toàn trường';
    scopePill.textContent=label;
  }
  renderProgramScope();
}
async function api(path, options = {}) {
  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), 23000);
  try {
    const response = await fetch('/api/v1' + path, {...options, credentials:'include', signal:controller.signal, headers:{'Content-Type':'application/json', ...(options.headers || {})}});
    const data = await response.json();
    if (!response.ok) { const error = new Error(typeof data.detail === 'string' ? data.detail : 'Nội dung chưa hợp lệ. Vui lòng kiểm tra rồi thử lại.'); error.status = response.status; throw error; }
    return data;
  } catch (error) {
    if (error.name === 'AbortError') throw new Error('Yêu cầu chưa phản hồi kịp. Hãy thử lại; yêu cầu handover dùng cùng mã sẽ không bị tạo trùng.');
    throw error;
  } finally { clearTimeout(timeout); }
}
function node(tag, className, text) { const n=document.createElement(tag); if(className)n.className=className; if(text)n.textContent=text; return n; }
function link(label, url) { const n=node('a','',label); n.href=url; n.target='_blank'; n.rel='noopener'; return n; }
function appendStructuredAnswer(box,data){
  const sections=data.answer_sections;
  if(!sections){box.append(node('div','body',data.response));return;}
  const structured=node('div','answer-structured');
  if(sections.short_answer){structured.append(node('h3','answer-section-title','Tóm tắt'),node('p','answer-short',sections.short_answer));}
  if((sections.conditions||[]).length){structured.append(node('h3','answer-section-title','Điều kiện / ngoại lệ'));sections.conditions.forEach(item=>structured.append(node('p','answer-condition',item)));}
  if(sections.source_note)structured.append(node('p','answer-source-note',sections.source_note));
  if((sections.next_steps||[]).length){structured.append(node('h3','answer-section-title','Bước tiếp theo'));const list=node('ul','answer-next-steps');sections.next_steps.forEach(item=>list.append(node('li','',item)));structured.append(list);}
  box.append(structured);
}
function addMessage(role, data, save=true) {
  $('welcome')?.remove();
  const box=node('article','message '+role);
  box.append(node('div','speaker',role==='user'?'BẠN':'TRỢ LÝ X'));
  if(role==='assistant')appendStructuredAnswer(box,data);else box.append(node('div','body',data.response));
  if(role==='assistant'&&(data.sources||[]).length){
    const firstSource=data.sources[0];
    const firstHref=firstSource.local_url||firstSource.url;
    if(firstHref){
      const citation=link(citationLabel(firstSource),firstHref);
      citation.className='message-citation';box.append(citation);
    }
    box.append(node('h3','answer-section-title source-heading','Chi tiết nguồn'));
  }
  (data.sources || []).forEach((source,i)=>{
    const card=node('details','source-card');
    const version=source.version?` · bản ${source.version}`:'';
    card.append(node('summary','',`[${i+1}] ${source.title||'Tài liệu HUST'}${sourceLocation(source)} · kỳ ${source.year||2026}${version}`));
    card.append(node('div','quote',source.excerpt||''));
    if(source.local_url)card.append(link('Mở PDF trong ứng dụng ↗',source.local_url));
    if(source.url)card.append(link('Nguồn chính thức ↗',source.url));
    if(source.document_status)card.append(node('p','hint',source.document_status));
    box.append(card);
  });
  if(role==='assistant') {
    const labels={answered:'Có nguồn',fallback:'Cần cán bộ kiểm tra',clarification:'Cần làm rõ',error:'Chưa xử lý được'};
    box.append(node('div','meta',`${data.reason==='out_of_scope'?'Ngoài phạm vi tuyển sinh':(labels[data.kind] || 'Trợ lý X')}${data.mode ? ' · '+(data.mode==='llm'?'AI tổng hợp':'Tra cứu tài liệu') : ''}${data.cached?' · Đã lưu đệm':''}${data.scope ? ' · '+scopeLabel(data).replace(/^Phạm vi trả lời: /,'').replace(/\.$/,'') : ''}`));
    const originalQuestion=[...messages].reverse().find(m=>m.role==='user')?.response || '';
    if(data.request_id){
      const actions=node('div','follow-up');const status=node('span','hint');status.setAttribute('role','status');
      const buttons=[];[['helpful','Hữu ích'],['incorrect','Chưa đúng']].forEach(([rating,title])=>{
        const b=node('button','small-action',title);b.type='button';b.setAttribute('aria-pressed',String(data.feedback===rating));buttons.push(b);
        b.onclick=async()=>{buttons.forEach(x=>x.disabled=true);try{await api('/answers/'+data.request_id+'/feedback',{method:'POST',body:JSON.stringify({rating})});data.feedback=rating;buttons.forEach(x=>x.setAttribute('aria-pressed',String(x===b)));status.textContent=rating==='incorrect'?'Đã ghi nhận. Bạn có thể gửi câu hỏi cho cán bộ.':'Đã ghi nhận đánh giá.';}catch(e){status.textContent=e.message;}finally{buttons.forEach(x=>x.disabled=false);}};actions.append(b);
      });actions.append(status);box.append(actions);
    }
    if(data.request_id&&data.reason!=='out_of_scope') {const b=node('button','small-action','Chuyển câu hỏi cho cán bộ');b.type='button';b.onclick=()=>openHandover(originalQuestion,data.response,data.sources||[]);box.append(b);}
  }
  $('messages').append(box);
  $('messages').scrollTop=$('messages').scrollHeight;
  if(save)messages.push({role,...data});
}
function sourceLocation(source){
  const page=Number.isInteger(source.page)&&source.page>0?source.page:null;
  if(page){const end=Number.isInteger(source.end_page)&&source.end_page>page?`–${source.end_page}`:'';return ` · PDF trang ${page}${end}`;}
  return source.source_type==='html'?' · Trang web chính thức':'';
}
function citationLabel(source){
  return `Nguồn · ${source.title||'Tài liệu HUST'}${sourceLocation(source)} ↗`;
}
async function init() {
  try {
    const [status, list, session] = await Promise.all([api('/status'),api('/programs'),api('/session')]);
    programs=list;
    currentStudent=session.student || null;
    $('program-count').textContent=`${programs.length} chương trình · Gợi ý theo nhóm ngành`;
    renderProgramOptions();
    setProgram(session.program || '');
    updateAccountNav(session.student);
    session.messages.forEach(m=>addMessage(m.role,m));
    const source=status.source||{};
    if(source.pages)$('source-pages').textContent=`${source.pages} trang`;
    $('source-status').textContent=status.status==='ready'?`${source.document_count||1} nguồn · ${source.indexable_pdf_count||1} PDF có thể tra cứu · ${status.programs} chương trình · kỳ 2026 · bộ dữ liệu ${source.version||'chưa rõ'}`:'Nguồn chưa sẵn sàng. Có thể chuyển cán bộ.';
    const official=$('source-official');if(official&&source.url){official.href=source.url;official.hidden=false;}
    $('mode-label').textContent=status.mode==='llm'?'AI tổng hợp có kiểm tra trích dẫn.':'Đang dùng chế độ tra cứu tài liệu.';
    $('ticket-count').textContent=session.tickets.length;
    restoreQuestionDraft();
  } catch(error) { $('chat-error').textContent='Không kết nối được ứng dụng: '+error.message; }
}
$('question').addEventListener('input',()=>{$('char-count').textContent=$('question').value.length+' / 2000';$('question-status').textContent='';saveQuestionDraft();});
$('question').addEventListener('keydown',e=>{if(e.key==='Enter'&&!e.shiftKey){e.preventDefault();$('chat-form').requestSubmit();}});
$('chat-form').addEventListener('submit',async e=>{
  e.preventDefault();const question=$('question').value.trim();if(!question||busy)return;
  busy=true;$('send').disabled=true;$('clear').disabled=true;$('chat-error').textContent='';
  addMessage('user',{response:question});
  const loading=node('div','message assistant','Đang tra cứu tài liệu…');loading.id='loading';$('messages').append(loading);loading.scrollIntoView({block:'nearest'});
  try {
    const data=await api('/chat',{method:'POST',body:JSON.stringify({message:question,program:$('program').value})});
    loading.remove();addMessage('assistant',data);setProgram(data.program || '');renderScope(data);$('question').value='';$('char-count').textContent='0 / 2000';$('question-status').textContent='';clearQuestionDraft();
  } catch(error){loading.remove();$('chat-error').textContent=error.message+' Nội dung vẫn ở ô nhập để thử lại.';}
  finally{busy=false;$('send').disabled=false;$('clear').disabled=false;$('question').focus();}
});
document.querySelectorAll('[data-question]').forEach(b=>b.addEventListener('click',()=>fillQuestion(quickQuestion(b))));
$('program-search').addEventListener('input',()=>handleProgramSearch());
$('program-search').addEventListener('change',()=>handleProgramSearch(true));
$('program-search').addEventListener('keydown',e=>{if(e.key==='Enter'){e.preventDefault();handleProgramSearch(true);}});
$('program').addEventListener('change',()=>{setProgram($('program').value);});
$('program-clear').addEventListener('click',()=>{setProgram('');$('program-search').focus();});
const programTools=$('program-tools');
const programToolsToggle=$('program-tools-open');
const programToolsClose=$('program-tools-close');
function setProgramToolsOpen(open, restoreFocus=true){
  if(!programTools||!programToolsToggle)return;
  const mobile=window.matchMedia('(max-width:900px)').matches;
  if(!mobile){programTools.classList.remove('mobile-open');document.body.classList.remove('sidebar-open');programTools.removeAttribute('aria-hidden');programToolsToggle.setAttribute('aria-expanded','false');return;}
  programTools.classList.toggle('mobile-open',open);
  document.body.classList.toggle('sidebar-open',open);
  programTools.setAttribute('aria-hidden',String(!open));
  programToolsToggle.setAttribute('aria-expanded',String(open));
  if(open){
    const focusSearch=()=>{if(programTools.classList.contains('mobile-open'))$('program-search')?.focus();};
    window.setTimeout(focusSearch,220);
  }
  else if(restoreFocus)programToolsToggle.focus();
}
programToolsToggle?.addEventListener('click',()=>setProgramToolsOpen(true));
programToolsClose?.addEventListener('click',()=>setProgramToolsOpen(false));
$('scope-open')?.addEventListener('click',()=>{
  if(window.matchMedia('(max-width:900px)').matches)setProgramToolsOpen(true);
  else $('program-search')?.focus();
});
document.addEventListener('keydown',event=>{if(event.key==='Escape'&&programTools?.classList.contains('mobile-open'))setProgramToolsOpen(false);});
window.addEventListener('resize',()=>setProgramToolsOpen(false,false));
setProgramToolsOpen(false,false);
[['handover-dialog','Chuyển câu hỏi cho cán bộ tuyển sinh'],['track-dialog','Theo dõi yêu cầu hỗ trợ'],['guide-dialog','Checklist đăng ký'],['compare-dialog','So sánh chương trình']].forEach(([id,label])=>$(id)?.setAttribute('aria-label',label));
$('comparison-result')?.setAttribute('aria-live','polite');
$('clear').addEventListener('click',async()=>{
  if(!confirm('Xóa lịch sử và ngữ cảnh chat? Ticket đã gửi vẫn được giữ.'))return;
  try {const data=await api('/session/messages',{method:'DELETE'});messages=[];$('messages').replaceChildren();setProgram('');$('question-status').textContent='';addMessage('assistant',{response:data.message,kind:'clarification'},false);}
  catch(error){$('chat-error').textContent=error.message;}
});
function renderHandoverSources(sources){
  const box=$('handover-sources-preview');box.replaceChildren();
  if(!sources.length){box.append(node('p','hint','Không có nguồn liên quan trong câu trả lời AI.'));return;}
  sources.forEach((source,index)=>{const item=node('div','preview-source');item.append(node('span','',`${index+1}. ${source.title||'Tài liệu nguồn'}${sourceLocation(source)}`));if(source.local_url)item.append(link('Mở PDF ↗',source.local_url));if(source.url)item.append(link('Nguồn chính thức ↗',source.url));box.append(item);});
}
function openHandover(question=null,answer=null,sources=null) {
  const lastQuestion=[...messages].reverse().find(m=>m.role==='user');
  const lastAnswer=[...messages].reverse().find(m=>m.role==='assistant');
  const rawSources=Array.isArray(sources)?sources:(lastAnswer?.sources||[]);
  handoverPreview={question:redactHandoverText(typeof question==='string'?question:(lastQuestion?.response||$('question').value.trim())),ai_answer:redactHandoverText(typeof answer==='string'?answer:(lastAnswer?.response||'')),sources:rawSources.map(source=>({...source, title:redactHandoverText(source.title), excerpt:redactHandoverText(source.excerpt), document_status:redactHandoverText(source.document_status)}))};
  $('handover-question-preview').textContent=handoverPreview.question||'Chưa có câu hỏi.';
  $('handover-answer-preview').textContent=handoverPreview.ai_answer||'Chưa có câu trả lời AI.';
  renderHandoverSources(handoverPreview.sources);
  $('summary').value='';$('consent').checked=false;$('handover-error').textContent='';requestKey=crypto.randomUUID();$('handover-dialog').showModal();$('consent').focus();
}
$('handover-open').onclick=openHandover;
document.querySelectorAll('[data-close]').forEach(b=>b.onclick=()=>$(b.dataset.close).close());
$('handover-form').addEventListener('submit',async e=>{
  e.preventDefault();$('handover-send').disabled=true;$('handover-error').textContent='';
  try {
    const ticket=await api('/handover',{method:'POST',body:JSON.stringify({summary:$('summary').value,question:handoverPreview.question,ai_answer:handoverPreview.ai_answer,sources:handoverPreview.sources,consent:$('consent').checked,request_key:requestKey,reason:'candidate_request'})});
    $('handover-dialog').close();$('ticket-success').hidden=false;$('ticket-success').textContent=`Đã tạo ticket ${ticket.id} · ${stateNames[ticket.status]||ticket.status} · Cập nhật gần nhất ${new Date(Number(ticket.updated)*1000).toLocaleString('vi-VN')}`;$('track-dialog').showModal();await loadTickets();
  }catch(error){$('handover-error').textContent=error.message;}finally{$('handover-send').disabled=false;}
});
async function loadTickets(){
  try {const list=await api('/tickets');$('ticket-count').textContent=list.length;$('tickets').replaceChildren();
    const seen=readLocal(seenKey,{});const newReplies=list.filter(t=>t.reply&&seen[t.id]!==t.updated);const badge=$('reply-unread');badge.hidden=!newReplies.length;badge.textContent=newReplies.length+' phản hồi mới';const notice=$('ticket-notice');if(newReplies.length){notice.hidden=false;notice.textContent=`Cán bộ đã trả lời ${newReplies.length} ticket. Hãy xem phần “Phản hồi của cán bộ” bên dưới.`;if($('track-dialog').open)markRepliesSeen(list);}
    if(!list.length)$('tickets').append(node('p','empty-state','Chưa có yêu cầu. Bạn có thể chuyển câu hỏi từ màn hình chat.'));
    list.forEach(t=>{const card=node('article','ticket-card');const head=node('div','ticket-head');head.append(node('b','',t.id),node('span','badge '+t.status,stateNames[t.status]||'Không rõ'));card.append(head,node('p','',t.question||t.summary),node('small','hint',`Cập nhật gần nhất: ${new Date(Number(t.updated||t.created)*1000).toLocaleString('vi-VN')}`));if(t.ai_answer){const preview=node('details','ticket-preview');preview.append(node('summary','','Nội dung đã chuyển'),node('p','',t.ai_answer));if(Array.isArray(t.sources)&&t.sources.length)preview.append(node('small','hint',`${t.sources.length} nguồn liên quan`));card.append(preview);}if(['waiting','in_progress'].includes(t.status)){const cancel=node('button','secondary danger','Hủy yêu cầu');const error=node('p','error-text');error.setAttribute('role','alert');cancel.onclick=async()=>{if(!confirm('Hủy yêu cầu '+t.id+'? Cán bộ sẽ không tiếp tục xử lý yêu cầu này.'))return;cancel.disabled=true;try{await api('/tickets/'+t.id+'/cancel',{method:'POST'});await loadTickets();}catch(e){error.textContent=e.message;cancel.disabled=false;}};card.append(cancel,error);}if(t.reply)card.append(node('div','reply-box',`Phản hồi của cán bộ: ${t.reply}`));$('tickets').append(card);});
  }catch(error){$('tickets').replaceChildren(node('p','error-text',error.message));}
}
$('track-open').onclick=()=>{$('track-dialog').showModal();loadTickets();};$('refresh-tickets').onclick=loadTickets;
setInterval(()=>{if($('track-dialog').open)loadTickets();},10000);
function storageForGuide() {
  try {
    const storage = window.localStorage;
    const probe = '__guide_storage_probe__';
    storage.setItem(probe, '1');
    storage.removeItem(probe);
    return {storage, label:'localStorage trên thiết bị này'};
  } catch {}
  try {
    return {storage:window.sessionStorage, label:'sessionStorage trong tab này'};
  } catch {}
  return {storage:null, label:'bộ nhớ tạm của trang này'};
}
function readGuideLocal(version) {
  guideStorage=guideStorage||storageForGuide();
  let data={guide_version:version,completed:[]};
  try { data=JSON.parse(guideStorage.storage?.getItem(guideStorageKey)||'null')||data; } catch {}
  if(data.guide_version!==version||!Array.isArray(data.completed))return {guide_version:version,completed:[]};
  return {guide_version:version,completed:[...new Set(data.completed.map(String))]};
}
function writeGuideLocal(version, completed) {
  guideStorage=guideStorage||storageForGuide();
  const data={guide_version:version,completed:[...new Set(completed)]};
  try { guideStorage.storage?.setItem(guideStorageKey,JSON.stringify(data)); } catch {}
}
function showGuideSessionNotice(message='') {
  const notice=$('guide-session-notice');
  notice.hidden=!message;
  notice.replaceChildren();
  if(!message)return;
  notice.append(node('span','',message+' '));
  const login=link('Đăng nhập lại ↗','/account');
  notice.append(login);
}
function renderGuideProgress() {
  if(!guideData)return;
  const total=guideData.steps.length;const done=guideData.steps.filter(step=>guideCompleted.has(step.id)).length;
  $('guide-progress').textContent=`${done}/${total} bước`;
}
function renderGuideStorage(student=false) {
  guideStorage=guideStorage||storageForGuide();
  $('guide-storage-note').textContent=student
    ? 'Đang lưu trên tài khoản và giữ một bản local trên thiết bị để tránh mất tiến độ khi phiên đăng nhập hết hạn.'
    : `Đang lưu trên ${guideStorage.label}. Đăng nhập để đồng bộ checklist giữa các thiết bị.`;
}
function renderGuide(guide) {
  guideData=guide;
  $('guide-note').textContent=guide.note;
  $('guide-meta').textContent=`Ngày kiểm tra: ${guide.checked_at||'chưa rõ'} · Phiên bản tài liệu: ${guide.document_version||'chưa rõ'} · ${guide.document_title||'Tài liệu tuyển sinh'} · ${guide.document_status||'Chưa xác định trạng thái nguồn'}`;
  $('guide-steps').replaceChildren();
  guide.steps.forEach(step=>{
    const card=node('article','ticket-card guide-step');
    const label=node('label','checkbox-label');
    const check=document.createElement('input');check.type='checkbox';check.id=`guide-step-${step.id}`;check.checked=guideCompleted.has(step.id);check.setAttribute('aria-label',`Đánh dấu bước: ${step.title}`);
    check.onchange=async()=>{
      if(check.checked)guideCompleted.add(step.id);else guideCompleted.delete(step.id);
      writeGuideLocal(guide.guide_version,guideCompleted);renderGuideProgress();
      if(!currentStudent)return;
      try {
        await api('/guide/checklist',{method:'PUT',body:JSON.stringify({guide_version:guide.guide_version,completed:[...guideCompleted]})});
        showGuideSessionNotice('');renderGuideStorage(true);
      } catch(error) {
        if(error.status===401||error.status===403){currentStudent=null;showGuideSessionNotice('Phiên đăng nhập đã hết hạn. Tiến độ checklist vẫn được giữ local; hãy đăng nhập lại để đồng bộ.');renderGuideStorage(false);}
        else showGuideSessionNotice('Chưa đồng bộ được tiến độ lên tài khoản; bản local vẫn được giữ.');
      }
    };
    label.htmlFor=check.id;label.append(check,node('span','',step.title));
    const source=step.source||guide.source||{};
    const sourceBox=node('div','guide-source');
    sourceBox.append(node('span','',`Nguồn: ${source.document_title||guide.document_title||'Tài liệu tuyển sinh'} · PDF trang ${source.page||'chưa rõ'} · bản ${source.version||guide.document_version||'chưa rõ'}`));
    const pdfUrl=source.local_url||`/api/v1/source/pdf#page=${source.page||1}`;
    sourceBox.append(link(`Mở PDF trang ${source.page||'chưa rõ'} ↗`,pdfUrl));
    if(step.url&&step.url!==pdfUrl)sourceBox.append(link('Mở cổng đăng ký ↗',step.url));
    card.append(label,node('p','',step.text),sourceBox);
    $('guide-steps').append(card);
  });
  renderGuideProgress();renderGuideStorage(Boolean(currentStudent));
}
async function syncGuideProgress(guide) {
  const local=readGuideLocal(guide.guide_version);guideCompleted=new Set(local.completed);renderGuide(guide);
  if(!currentStudent)return;
  try {
    const remote=await api(`/guide/checklist?guide_version=${encodeURIComponent(guide.guide_version)}`);
    const merged=[...new Set([...local.completed,...(remote.completed||[])])];
    guideCompleted=new Set(merged);writeGuideLocal(guide.guide_version,merged);renderGuide(guide);
    if(merged.length!==(remote.completed||[]).length)await api('/guide/checklist',{method:'PUT',body:JSON.stringify({guide_version:guide.guide_version,completed:merged})});
    renderGuideStorage(true);showGuideSessionNotice('');
  } catch(error) {
    if(error.status===401||error.status===403){currentStudent=null;showGuideSessionNotice('Phiên đăng nhập đã hết hạn. Tiến độ checklist vẫn được giữ local; hãy đăng nhập lại để đồng bộ.');renderGuideStorage(false);}
    else showGuideSessionNotice('Chưa đồng bộ được tiến độ lên tài khoản; bản local vẫn được giữ.');
  }
}
async function loadGuide() {
  if(guideData){$('guide-dialog').showModal();renderGuide(guideData);return;}
  $('guide-dialog').showModal();$('guide-steps').replaceChildren(node('p','hint','Đang tải checklist…'));
  try { const guide=await api('/guide'); await syncGuideProgress(guide); }
  catch(error) { $('guide-steps').replaceChildren(node('p','error-text',error.message)); }
}
$('guide-open').onclick=loadGuide;
$('guide-reset').onclick=async()=>{
  if(!guideData||!confirm('Đặt lại tiến độ checklist trên thiết bị này? Nếu đã đăng nhập, tiến độ trong tài khoản cũng sẽ được xóa.'))return;
  guideCompleted=new Set();writeGuideLocal(guideData.guide_version,[]);renderGuide(guideData);showGuideSessionNotice('');
  if(!currentStudent)return;
  try { await api('/guide/checklist',{method:'PUT',body:JSON.stringify({guide_version:guideData.guide_version,completed:[]})});renderGuideStorage(true); }
  catch(error) { if(error.status===401||error.status===403){currentStudent=null;showGuideSessionNotice('Phiên đăng nhập đã hết hạn. Tiến độ local đã được đặt lại; hãy đăng nhập lại để đồng bộ.');renderGuideStorage(false);}else showGuideSessionNotice('Đã đặt lại trên thiết bị nhưng chưa đồng bộ được tài khoản.'); }
};
function restoreQuestionDraft() {
  try { const draft=localStorage.getItem(questionDraftKey)||sessionStorage.getItem(questionDraftKey)||''; if(!$('question').value&&draft){$('question').value=draft;$('char-count').textContent=draft.length+' / 2000';} } catch {}
}
function saveQuestionDraft() { try { const value=$('question').value; if(value)localStorage.setItem(questionDraftKey,value); else localStorage.removeItem(questionDraftKey); } catch {} }
function clearQuestionDraft() { try { localStorage.removeItem(questionDraftKey);sessionStorage.removeItem(questionDraftKey); } catch {} }
init();
const comparisonFields=[
  ['quota','Chỉ tiêu'],
  ['methods','Phương thức / tổ hợp'],
  ['fee','Học phí dự kiến'],
  ['language','Ngoại ngữ đầu vào'],
  ['note','Ghi chú chương trình'],
];
function comparisonSelects(){return [0,1,2].map(i=>$('compare-'+i)).filter(Boolean);}
function clearComparisonFieldError(select){select.classList.remove('compare-invalid');select.removeAttribute('aria-invalid');}
function setComparisonError(message, select=null){
  $('compare-error').textContent=message;
  if(select){select.classList.add('compare-invalid');select.setAttribute('aria-invalid','true');select.focus();}
}
function comparisonCodes(){return comparisonSelects().map(select=>select.value.trim()).filter(Boolean);}
function validateComparisonSelection(){
  const selects=comparisonSelects();selects.forEach(clearComparisonFieldError);const codes=selects.map(select=>select.value.trim());
  const selected=codes.filter(Boolean);
  if(selected.length<2){
    const firstEmpty=selects.find(select=>!select.value) || selects[0];
    setComparisonError('Vui lòng chọn ít nhất 2 chương trình để so sánh.',firstEmpty);return null;
  }
  const known=new Set(programs.map(program=>program.code));
  const invalidIndex=codes.findIndex(code=>code&&!known.has(code));
  if(invalidIndex>=0){setComparisonError('Mã chương trình không hợp lệ. Hãy chọn lại từ danh sách.',selects[invalidIndex]);return null;}
  const seen=new Map();
  for(let i=0;i<codes.length;i++){
    if(!codes[i])continue;
    if(seen.has(codes[i])){
      setComparisonError('Không được chọn trùng chương trình.',selects[i]);selects[seen.get(codes[i])].classList.add('compare-invalid');selects[seen.get(codes[i])].setAttribute('aria-invalid','true');return null;
    }
    seen.set(codes[i],i);
  }
  return selected;
}
function clearComparisonResult(){
  $('comparison-result').replaceChildren();$('comparison-result').classList.remove('comparison-stale');$('compare-stale').hidden=true;
}
function markComparisonStale(){
  const result=$('comparison-result');if(!result.children.length)return;
  result.classList.add('comparison-stale');$('compare-stale').hidden=false;
}
function comparisonSources(program,field){
  const sources=[];const add=source=>{if(source&&!sources.some(item=>item.id===source.id))sources.push(source);};
  if(field==='language'){add(program.sources.language);add(program.sources.program);}else add(program.sources[field==='quota'||field==='methods'||field==='note'?'program':field]);
  return sources;
}
const comparisonFieldStates=new Set(['available','no_specific_requirement','missing']);
function comparisonFieldState(program,field){
  const explicit=program.field_status?.[field]?.status;
  if(comparisonFieldStates.has(explicit))return explicit;
  const value=String(program[field]||'').trim();
  if(!value||!comparisonSources(program,field).length)return 'missing';
  return /^(chưa (đủ|ghép)|cần cán bộ kiểm tra|chưa có dữ liệu)/i.test(value)?'missing':'available';
}
function comparisonValue(program,field){
  const value=String(program[field]||'').trim();
  if(value)return value;
  return comparisonFieldState(program,field)==='no_specific_requirement'?'Nguồn không nêu yêu cầu riêng.':'Chưa có dữ liệu';
}
function comparisonSummaryValue(program,field){
  return comparisonFieldState(program,field)==='no_specific_requirement'?'Nguồn không nêu yêu cầu riêng theo tài liệu.':comparisonValue(program,field);
}
function appendComparisonCitations(container, entries){
  const sources=[];entries.forEach(entry=>comparisonSources(entry.program,entry.field).forEach(source=>{if(!sources.some(item=>item.id===source.id))sources.push(source);}));
  if(!sources.length)return;
  const citations=node('span','comparison-citations','Nguồn: ');
  sources.forEach((source,index)=>{if(index)citations.append(document.createTextNode(' · '));const entry=entries.find(item=>comparisonSources(item.program,item.field).some(candidate=>candidate.id===source.id));citations.append(link(`${entry?.program.code||''} · PDF trang ${source.page}${source.end_page!==source.page?'–'+source.end_page:''}`,source.local_url));});
  container.append(citations);
}
function isComparisonMissing(program,field){
  return comparisonFieldState(program,field)==='missing';
}
function appendComparisonClaim(list,text,entries){
  const item=node('li','comparison-claim');item.append(node('span','',text));appendComparisonCitations(item,entries);list.append(item);
}
function buildComparisonAssistant(data){
  const section=node('section','comparison-assistant');section.append(node('h3','', 'Trợ lý tổng hợp'),node('p','hint','Tổng hợp tự động từ đúng dữ liệu đã trả về trong bảng/API; không xếp hạng chương trình và không dự đoán khả năng đỗ.'));
  const common=node('div','comparison-summary-block');common.append(node('h4','', 'Điểm giống nhau'));const commonList=node('ul','comparison-summary-list');
  comparisonFields.forEach(([field,label])=>{const values=data.programs.map(program=>comparisonSummaryValue(program,field));if(values.length&&values.every(value=>value===values[0])&&data.programs.every(program=>!isComparisonMissing(program,field)))appendComparisonClaim(commonList,`${label}: ${values[0]}`,data.programs.map(program=>({program,field})));});
  if(!commonList.children.length)commonList.append(node('li','', 'Không có giá trị giống nhau đủ rõ trong dữ liệu hiện tại.'));common.append(commonList);section.append(common);
  const different=node('div','comparison-summary-block');different.append(node('h4','', 'Khác nhau'));const differentList=node('ul','comparison-summary-list');
  comparisonFields.forEach(([field,label])=>{const values=data.programs.map(program=>comparisonSummaryValue(program,field));if(new Set(values).size<2)return;const item=node('li','comparison-difference');item.append(node('b','',label));const details=node('ul','comparison-value-list');data.programs.forEach(program=>{const value=node('li','',`${program.code}: ${comparisonSummaryValue(program,field)}`);appendComparisonCitations(value,[{program,field}]);details.append(value);});item.append(details);differentList.append(item);});
  if(!differentList.children.length)differentList.append(node('li','', 'Các trường dữ liệu hiện có giống nhau theo phản hồi API.'));different.append(differentList);section.append(different);
  const missing=node('div','comparison-summary-block');missing.append(node('h4','', 'Dữ liệu còn thiếu'));const missingList=node('ul','comparison-summary-list');
  data.programs.forEach(program=>comparisonFields.forEach(([field,label])=>{if(isComparisonMissing(program,field))missingList.append(node('li','',`${program.code} · ${label}: chưa đủ dữ liệu có nguồn để kết luận.`));}));
  if(!missingList.children.length)missingList.append(node('li','', 'Không phát hiện trường dữ liệu thiếu trong phản hồi API.'));missing.append(missingList);section.append(missing);
  const note=node('p','comparison-safety-note','Lưu ý: phần này chỉ mô tả điểm dữ liệu giống/khác được trả về, không kết luận chương trình nào tốt nhất, không cam kết trúng tuyển và không thay thế xác nhận của cán bộ tuyển sinh.');section.append(note);
  return section;
}
function appendComparisonRawData(container,data){
  const raw=node('div','comparison-raw-data');raw.hidden=true;raw.append(node('h4','', 'Dữ liệu gốc từ API'));
  data.programs.forEach(program=>{const details=node('details','comparison-raw-item');details.append(node('summary','',`${program.code} · ${program.name}`));const list=node('ul','comparison-summary-list');comparisonFields.forEach(([field,label])=>{const item=node('li','',`${label}: ${comparisonValue(program,field)} · trạng thái ${comparisonFieldState(program,field)}`);appendComparisonCitations(item,[{program,field}]);list.append(item);});details.append(list);raw.append(details);});container.append(raw);return raw;
}
function appendComparisonMobileDetails(container,data){
  const details=node('div','comparison-mobile-details');data.programs.forEach(program=>{const item=node('details','comparison-mobile-item');item.append(node('summary','',`${program.code} · ${program.name}`));comparisonFields.forEach(([field,label])=>{const row=node('div','comparison-mobile-row');row.append(node('b','',label),node('span','',comparisonValue(program,field)));appendComparisonCitations(row,[{program,field}]);item.append(row);});details.append(item);});container.append(details);
}
function renderComparison(data){
  const result=$('comparison-result');result.replaceChildren();result.classList.remove('comparison-stale');$('compare-stale').hidden=true;
  const wrap=node('div','comparison-scroll');const table=node('table','comparison-table');const caption=node('caption','','Thông tin chương trình tuyển sinh 2026');table.append(caption);
  const header=node('tr');header.append(node('th','','Thông tin'));data.programs.forEach(program=>header.append(node('th','',`${program.code} · ${program.name}`)));table.append(header);
  comparisonFields.forEach(([field,label])=>{const row=node('tr');row.append(node('th','',label));data.programs.forEach(program=>{const cell=node('td','',comparisonValue(program,field));comparisonSources(program,field).forEach((source,index)=>cell.append(document.createElement('br'),link(`${index?'Nguồn bổ sung':'Nguồn'} · PDF trang ${source.page}`,source.local_url)));row.append(cell);});table.append(row);});wrap.append(table);result.append(wrap);appendComparisonMobileDetails(result,data);result.append(buildComparisonAssistant(data));
  const actions=node('div','comparison-actions');const change=node('button','secondary','Đổi tiêu chí');change.type='button';change.onclick=()=>{markComparisonStale();comparisonSelects()[0]?.focus();};const rawButton=node('button','secondary','Xem dữ liệu gốc');rawButton.type='button';const raw=appendComparisonRawData(result,data);rawButton.onclick=()=>{raw.hidden=!raw.hidden;rawButton.textContent=raw.hidden?'Xem dữ liệu gốc':'Ẩn dữ liệu gốc';if(!raw.hidden)raw.scrollIntoView({block:'nearest'});};const handover=node('button','secondary','Chuyển câu hỏi cho cán bộ');handover.type='button';handover.onclick=()=>openHandover(`Cần cán bộ kiểm tra so sánh chương trình: ${data.programs.map(program=>program.code).join(', ')}`, 'Bảng/API đã hiển thị nhưng cần cán bộ xác nhận các khác biệt và dữ liệu còn thiếu.');actions.append(change,rawButton,handover);result.append(actions);
}
function resetComparisonSelection(){comparisonSelects().forEach(select=>{select.value='';clearComparisonFieldError(select);});$('compare-error').textContent='';clearComparisonResult();$('compare-0')?.focus();}
function guidanceStatus(message, retry=false){
  const status=$('guidance-option-status');status.hidden=false;status.replaceChildren(document.createTextNode(message));
  if(retry){const button=node('button','guidance-retry','Thử tải lại');button.type='button';button.onclick=()=>{guidanceOptionsPromise=null;ensureGuidanceOptions();};status.append(document.createTextNode(' '),button);}
}
function renderGuidanceAreas(){
  for(const [name,id] of [['strengths','guidance-strength-options'],['interests','guidance-interest-options'],['improvements','guidance-improvement-options']]){
    const container=$(id);container.replaceChildren();
    guidanceAreas.forEach(area=>{
      const label=node('label','guidance-choice');const input=document.createElement('input');input.type='checkbox';input.name=name;input.value=area.id;input.id=`guidance-${name}-${area.id}`;
      input.addEventListener('change',()=>{
        const selected=container.querySelectorAll('input:checked');
        if(input.checked&&selected.length>4){input.checked=false;$('guidance-error').textContent='Mỗi nhóm bạn có thể chọn tối đa 4 lĩnh vực.';return;}
        $('guidance-error').textContent='';
      });
      label.htmlFor=input.id;label.append(input,node('span','',area.label));container.append(label);
    });
  }
}
async function ensureGuidanceOptions(){
  const dialog=$('program-guidance-dialog');
  if(guidanceAreas){renderGuidanceAreas();$('guidance-option-status').hidden=true;$('program-guidance-form').hidden=false;renderGuidanceStep(1);return;}
  guidanceStatus('Đang tải lĩnh vực từ danh mục chương trình…');
  if(!guidanceOptionsPromise){
    guidanceOptionsPromise=(async()=>{
      const response=await fetch('/api/v1/programs/recommend/options',{credentials:'same-origin',headers:{Accept:'application/json'}});
      let data={};try{data=await response.json();}catch{/* The error below gives a stable user-facing message. */}
      if(!response.ok||!Array.isArray(data.areas))throw new Error('Không tải được danh mục chương trình.');
      return data;
    })();
  }
  try{
    const data=await guidanceOptionsPromise;guidanceAreas=data.areas;
    if(dialog.open){renderGuidanceAreas();$('guidance-option-status').hidden=true;$('program-guidance-form').hidden=false;renderGuidanceStep(1);}
  }catch{
    if(dialog.open)guidanceStatus('Chưa tải được danh mục. Kiểm tra kết nối rồi thử lại.',true);
  }finally{guidanceOptionsPromise=null;}
}
function renderGuidanceStep(step,focus=true){
  guidanceStep=step;document.querySelectorAll('[data-guidance-step]').forEach(section=>{section.hidden=Number(section.dataset.guidanceStep)!==step;});
  $('guidance-step-label').textContent=`Bước ${step}/3`;
  $('guidance-step-name').textContent=['','Thế mạnh','Sở thích','Điều muốn bồi dưỡng'][step];
  $('guidance-progress-fill').style.width=`${step/3*100}%`;
  const progress=document.querySelector('.guidance-progress');progress.setAttribute('aria-valuenow',String(step));progress.setAttribute('aria-valuetext',`Bước ${step} trong 3: ${$('guidance-step-name').textContent}`);
  $('guidance-back').disabled=step===1;$('guidance-next').hidden=step===3;$('guidance-submit').hidden=step!==3;
  $('guidance-error').textContent='';
  if(focus)document.querySelector(`[data-guidance-step="${step}"] legend`)?.focus({preventScroll:true});
}
function guidanceValues(name){return [...document.querySelectorAll(`#program-guidance-form input[name="${name}"]:checked`)].map(input=>input.value);}
function clearGuidanceProfile(){
  guidanceRequestId++;guidanceController?.abort();guidanceController=null;
  const form=$('program-guidance-form');form.reset();form.hidden=!guidanceAreas;
  $('guidance-submit').disabled=false;$('guidance-submit').removeAttribute('aria-busy');
  $('guidance-results').hidden=true;$('guidance-result-list').replaceChildren();$('guidance-result-message').textContent='';$('guidance-result-notice').textContent='';$('guidance-error').textContent='';
  $('guidance-option-status').hidden=Boolean(guidanceAreas);$('guidance-option-status').replaceChildren();
  renderGuidanceStep(1,false);
}
function renderGuidanceCard(suggestion){
  const card=node('article','guidance-result-card');const heading=node('div','guidance-card-heading');
  const title=node('h4','',`${suggestion.code} · ${suggestion.name}`);const badge=node('span','guidance-fit-label',suggestion.badge);heading.append(title,badge);card.append(heading);
  const reasons=node('ul','guidance-reasons');(suggestion.reasons||[]).forEach(reason=>reasons.append(node('li','',reason)));if(reasons.children.length)card.append(reasons);
  const matched=[...(suggestion.matched_strengths||[]).map(value=>`Thế mạnh: ${value}`),...(suggestion.matched_interests||[]).map(value=>`Sở thích: ${value}`)];
  if(matched.length)card.append(node('p','guidance-match-detail',matched.join(' · ')));
  if((suggestion.considerations||[]).length){const notes=node('ul','guidance-considerations');suggestion.considerations.forEach(value=>notes.append(node('li','',value)));card.append(notes);}
  const source=suggestion.source||{};const citation=node('div','guidance-citation');
  const page=Number.isInteger(source.page)&&source.page>0?source.page:null;const endPage=page&&Number.isInteger(source.end_page)&&source.end_page>=page?source.end_page:page;
  const label=`Nguồn · PDF trang ${page||'—'}${endPage&&endPage!==page?`–${endPage}`:''}`;
  const href=typeof source.local_url==='string'&&source.local_url.startsWith('/api/v1/source/pdf')?source.local_url:null;
  if(href)citation.append(link(label,href));else citation.append(node('span','',label));
  if(source.title)citation.append(node('span','guidance-source-title',source.title));card.append(citation);
  const actions=node('div','guidance-card-actions');const compare=node('button','secondary','So sánh chương trình');compare.type='button';compare.onclick=()=>{
    const code=suggestion.code;$('program-guidance-dialog').close();setProgram(code,true);$('compare-open').click();
  };
  const ask=node('button','guidance-ask','Hỏi trợ lý về chương trình');ask.type='button';ask.onclick=()=>{
    const code=suggestion.code;$('program-guidance-dialog').close();setProgram(code,true);fillQuestion(`Thông tin tuyển sinh trong tài liệu về chương trình ${code} là gì?`);
  };
  actions.append(compare,ask);card.append(actions);return card;
}
function renderGuidanceResults(data){
  const list=$('guidance-result-list');list.replaceChildren();const allowed=new Set(programs.map(program=>program.code));
  const suggestions=(data.suggestions||[]).filter(item=>typeof item.code==='string'&&(!allowed.size||allowed.has(item.code))).slice(0,3);
  $('guidance-result-message').textContent=data.message||'Đây là các gợi ý tham khảo dựa trên thông tin bạn đã chọn.';
  suggestions.forEach(item=>list.append(renderGuidanceCard(item)));
  $('guidance-result-notice').textContent=data.notice||'Hãy kiểm tra tài liệu tuyển sinh trước khi cân nhắc lựa chọn.';
  $('program-guidance-form').hidden=true;$('guidance-results').hidden=false;$('guidance-option-status').hidden=true;$('guidance-results').focus({preventScroll:true});
}
async function submitGuidance(event){
  event.preventDefault();$('guidance-error').textContent='';
  const payload={
    strengths:guidanceValues('strengths'),interests:guidanceValues('interests'),improvements:guidanceValues('improvements'),
    strengths_note:$('guidance-strengths-note').value,interests_note:$('guidance-interests-note').value,
    career_direction:$('guidance-career-direction').value,improvements_note:$('guidance-improvements-note').value,priorities:$('guidance-priorities').value,
  };
  const positiveInput=[...payload.strengths,...payload.interests,payload.strengths_note,payload.interests_note,payload.career_direction,payload.priorities].some(value=>String(value).trim());
  if(!positiveInput){renderGuidanceStep(1);$('guidance-error').textContent='Hãy chọn hoặc mô tả ít nhất một thế mạnh, sở thích hay hướng bạn muốn tìm hiểu.';return;}
  guidanceController?.abort();const controller=new AbortController();guidanceController=controller;const requestId=++guidanceRequestId;
  const timeout=setTimeout(()=>controller.abort(),20000);const button=$('guidance-submit');button.disabled=true;button.setAttribute('aria-busy','true');
  guidanceStatus('Đang đối chiếu câu trả lời với danh mục tuyển sinh…');
  try{
    const response=await fetch('/api/v1/programs/recommend',{method:'POST',credentials:'same-origin',signal:controller.signal,headers:{'Content-Type':'application/json',Accept:'application/json'},body:JSON.stringify(payload)});
    let data={};try{data=await response.json();}catch{/* Use the stable message for invalid server responses. */}
    if(!response.ok)throw new Error(typeof data.detail==='string'?data.detail:'Chưa tạo được gợi ý. Vui lòng thử lại.');
    if(requestId===guidanceRequestId&&$('program-guidance-dialog').open)renderGuidanceResults(data);
  }catch(error){
    if(requestId===guidanceRequestId&&$('program-guidance-dialog').open){$('guidance-option-status').hidden=true;$('guidance-error').textContent=error.name==='AbortError'?'Yêu cầu mất quá nhiều thời gian. Hãy thử lại khi kết nối ổn định.':error.message||'Chưa tạo được gợi ý. Vui lòng thử lại.';}
  }finally{
    clearTimeout(timeout);if(requestId===guidanceRequestId){guidanceController=null;button.disabled=false;button.removeAttribute('aria-busy');if($('program-guidance-dialog').open)$('guidance-option-status').hidden=true;}
  }
}
$('recommend-open').onclick=()=>{
  clearGuidanceProfile();$('program-guidance-dialog').showModal();
  if(guidanceAreas){renderGuidanceAreas();$('program-guidance-form').hidden=false;$('guidance-option-status').hidden=true;renderGuidanceStep(1);}
  else ensureGuidanceOptions();
};
$('program-guidance-dialog').addEventListener('close',clearGuidanceProfile);
$('program-guidance-form').addEventListener('submit',submitGuidance);
$('guidance-next').onclick=()=>renderGuidanceStep(Math.min(3,guidanceStep+1));
$('guidance-back').onclick=()=>renderGuidanceStep(Math.max(1,guidanceStep-1));
$('guidance-adjust').onclick=()=>{$('guidance-results').hidden=true;$('program-guidance-form').hidden=false;renderGuidanceStep(1);};
$('guidance-restart').onclick=()=>clearGuidanceProfile();
$('compare-open').onclick=()=>{
  const box=$('compare-selects');box.replaceChildren();$('compare-error').textContent='';clearComparisonResult();
  for(let i=0;i<3;i++){const label=node('label','',`Chương trình ${i+1}${i===2?' (tùy chọn)':''}`);const select=node('select');select.id='compare-'+i;select.setAttribute('aria-label',`Chương trình ${i+1}${i===2?' tùy chọn':''}`);label.htmlFor=select.id;const empty=node('option','','Chọn chương trình');empty.value='';select.append(empty);programs.forEach(program=>{const option=node('option','',program.code+' · '+program.name);option.value=program.code;select.append(option);});if(i===0)select.value=$('program').value;select.addEventListener('change',()=>{clearComparisonFieldError(select);$('compare-error').textContent='';markComparisonStale();});box.append(label,select);}
  $('compare-dialog').showModal();
};
$('compare-reset').onclick=resetComparisonSelection;
$('compare-form').onsubmit=async e=>{
  e.preventDefault();$('compare-error').textContent='';const codes=validateComparisonSelection();if(!codes)return;
  clearComparisonResult();const button=$('compare-submit');button.disabled=true;
  try{const data=await api('/programs/compare',{method:'POST',body:JSON.stringify({codes})});renderComparison(data);
  }catch(error){$('compare-error').textContent=error.message;}finally{button.disabled=false;}
};

const seenKey="hust-replies-seen-v1";
function readLocal(key,fallback){try{return JSON.parse(localStorage.getItem(key))||fallback;}catch{return fallback;}}
try{localStorage.removeItem("hust-plan-2026-v1");}catch{}
async function checkReplies(){
  if(document.hidden)return;
  try{const tickets=await api('/tickets');$('ticket-count').textContent=tickets.length;const seen=readLocal(seenKey,{});let count=0;
    tickets.forEach(t=>{if(t.reply&&seen[t.id]!==t.updated)count++;});const badge=$('reply-unread');badge.hidden=count===0;badge.textContent=count+' phản hồi mới';
    const notice=$('ticket-notice');if(notice&&count){notice.hidden=false;notice.textContent=`Cán bộ đã trả lời ${count} ticket. Mở “Yêu cầu của tôi” để xem.`;}
  }catch{/* A temporary connection failure keeps the last successful notification. */}
}
function markRepliesSeen(tickets){
  const seen={};tickets.forEach(t=>{if(t.reply)seen[t.id]=t.updated;});try{localStorage.setItem(seenKey,JSON.stringify(seen));$('reply-unread').hidden=true;}catch{/* Do not mark read if storage is unavailable. */}
}
setTimeout(checkReplies,1500);setInterval(checkReplies,15000);document.addEventListener('visibilitychange',()=>{if(!document.hidden)checkReplies();});
