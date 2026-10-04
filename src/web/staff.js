const $=id=>document.getElementById(id);
const names={waiting:'Đang chờ',in_progress:'Đang xử lý',resolved:'Đã giải quyết',cancelled:'Đã hủy',rejected:'Đã từ chối'};
let allTickets=[], selected=null, username='';
function node(tag,cls,text){const n=document.createElement(tag);if(cls)n.className=cls;if(text)n.textContent=text;return n;}
async function api(path,options={}){
  const r=await fetch('/api/v1'+path,{...options,credentials:'same-origin',headers:{'Content-Type':'application/json'}});
  const data=await r.json();
  if(r.status===401){$('dashboard').hidden=true;$('login-panel').hidden=false;$('logout').hidden=true;}
  if(!r.ok)throw new Error(typeof data.detail==='string'?data.detail:'Nội dung chưa hợp lệ.');
  return data;
}
function showDashboard(){ $('dashboard').hidden=false;$('login-panel').hidden=true;$('logout').hidden=false; }
async function refresh(){
  $('staff-error').textContent='';
  try{const [tickets,m]=await Promise.all([api('/staff/tickets'),api('/staff/metrics')]);allTickets=tickets;renderQueue();
    $('metrics').replaceChildren();
    const cards=[['Lượt hỏi demo',m.total,'Tất cả câu hỏi đã xử lý'],['AI / tra cứu trả lời',m.answer_rate===null?'—':m.answer_rate+'%','Không thay thế kết quả eval'],['Đang chờ cán bộ',m.tickets.waiting||0,'Yêu cầu đã được đồng ý chuyển'],['Accuracy kiểm chứng','Chưa đo','Cần bộ test có nhãn và người duyệt']];
    cards.forEach(([label,value,note])=>{const box=node('div','metric');box.append(node('span','',label),node('b','',String(value)),node('small','',note));$('metrics').append(box);});
    if(selected){selected=allTickets.find(t=>t.id===selected.id);if(selected)renderDetail();}
  }catch(error){$('staff-error').textContent=error.message;}
}
function renderQueue(){
  $('queue').replaceChildren();const status=$('status-filter').value;const query=normalizeSearch($('queue-search').value);
  const list=allTickets.filter(t=>(!status||t.status===status)&&normalizeSearch(t.id+' '+t.summary).includes(query));
  if($('queue-sort').value==='oldest')list.sort((a,b)=>a.created-b.created);
  else list.sort((a,b)=>b.created-a.created);
  $('queue-count').textContent=`${list.length} / ${allTickets.length} yêu cầu`;
  if(!list.length){$('queue').append(node('p','empty-state','Chưa có yêu cầu ở trạng thái này.'));return;}
  list.forEach(t=>{const b=node('button','queue-item'+(selected?.id===t.id?' selected':''));const header=node('div','ticket-head');header.append(node('b','',t.id),node('span','badge '+t.status,names[t.status]));b.append(header,node('p','',t.summary.slice(0,140)),node('small','',new Date(t.created*1000).toLocaleString('vi-VN')));b.onclick=()=>{selected=t;renderQueue();renderDetail();};$('queue').append(b);});
}
function renderDetail(){
  const t=selected;const box=$('detail');box.replaceChildren();box.append(node('span','eyebrow','NỘI DUNG ĐƯỢC ĐỒNG Ý CHIA SẺ'),node('h2','',t.id),node('span','badge '+t.status,names[t.status]),node('div','summary',t.summary),node('p','detail-time','Tạo lúc '+new Date(t.created*1000).toLocaleString('vi-VN')));
  const err=node('p','error-text');err.setAttribute('role','alert');
  if(t.status==='waiting'){const button=node('button','primary','Nhận xử lý →');button.onclick=async()=>{button.disabled=true;try{await api('/staff/tickets/'+t.id+'/claim',{method:'POST'});await refresh();}catch(e){err.textContent=e.message;button.disabled=false;}};box.append(button);}
  if(t.status==='in_progress'&&t.owner===username){const label=node('label','','Phản hồi cho ứng viên');label.htmlFor='reply';const textarea=node('textarea');textarea.id='reply';textarea.maxLength=4000;textarea.placeholder='Phản hồi dựa trên nguồn đã kiểm tra; không hứa trúng tuyển.';const button=node('button','primary','Gửi phản hồi & đóng yêu cầu →');button.onclick=async()=>{if(!textarea.value.trim()){err.textContent='Cần nhập phản hồi.';return;}button.disabled=true;try{await api('/staff/tickets/'+t.id+'/resolve',{method:'POST',body:JSON.stringify({reply:textarea.value})});await refresh();}catch(e){err.textContent=e.message;button.disabled=false;}};box.append(label,textarea,node('p','hint','Phản hồi sẽ hiển thị trong phiên ứng viên. Chỉ đóng sau khi nội dung gửi thành công.'),button);}
  if(t.status==='in_progress'&&t.owner!==username)box.append(node('p','hint','Yêu cầu đang được cán bộ khác xử lý.'));
  if(t.status==='waiting'||(t.status==='in_progress'&&t.owner===username)){
    const label=node('label','','Lý do từ chối');label.htmlFor='reject-reason';const input=node('textarea');input.id='reject-reason';input.maxLength=4000;input.placeholder='Nội dung không thuộc phạm vi tư vấn tuyển sinh.';
    const templates=node('div','follow-up');['Nội dung không thuộc phạm vi tư vấn tuyển sinh HUST.','Yêu cầu trùng nội dung đã được phản hồi.','Nội dung không phù hợp hoặc có tính chất quấy rối.'].forEach((text,i)=>{const b=node('button','small-action',['Ngoài phạm vi','Trùng yêu cầu','Nội dung không phù hợp'][i]);b.onclick=()=>{input.value=text;input.focus();};templates.append(b);});
    const reject=node('button','secondary danger','Từ chối yêu cầu');
    reject.onclick=async()=>{if(!input.value.trim()){err.textContent='Cần nhập lý do từ chối.';return;}if(!confirm('Từ chối yêu cầu và gửi lý do cho ứng viên?'))return;reject.disabled=true;try{await api('/staff/tickets/'+t.id+'/reject',{method:'POST',body:JSON.stringify({reply:input.value})});await refresh();}catch(e){err.textContent=e.message;reject.disabled=false;}};box.append(label,templates,input,reject);
  }
  if(t.reply)box.append(node('h3','',t.status==='rejected'?'Lý do từ chối':'Phản hồi đã gửi'),node('div','reply-box',t.reply));box.append(err);
}
$('login-form').addEventListener('submit',async e=>{e.preventDefault();$('login-error').textContent='';const button=e.submitter;button.disabled=true;try{const user=await api('/staff/login',{method:'POST',body:JSON.stringify({username:$('username').value,password:$('password').value})});username=user.username;$('password').value='';showDashboard();await refresh();}catch(error){$('login-error').textContent=error.message;}finally{button.disabled=false;}});
$('logout').onclick=async()=>{try{await api('/staff/logout',{method:'POST'});location.reload();}catch(e){$('staff-error').textContent=e.message;}};
$('refresh').onclick=refresh;$('status-filter').onchange=renderQueue;
function normalizeSearch(text){return text.toLowerCase().replaceAll('đ','d').normalize('NFD').replace(/[\u0300-\u036f]/g,'');}
$('queue-search').oninput=renderQueue;$('queue-sort').onchange=renderQueue;
(async()=>{try{const me=await api('/staff/me');username=me.username;showDashboard();await refresh();}catch{/* Login form remains visible. */}})();
