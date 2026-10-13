// Shared "Đánh giá AI" view: admins review ratings, officers read them.
(function(){
  const RATINGS={helpful:'Hữu ích',incorrect:'Chưa đúng'};
  const REASONS={wrong_info:'Sai thông tin',missing_info:'Thiếu thông tin',off_topic:'Không đúng câu hỏi',other:'Khác',unspecified:'Không ghi lý do'};
  const STATUSES={new:'Mới',reviewed:'Đã xem',resolved:'Đã xử lý'};
  const PAGE_SIZE=15;
  function node(tag,cls,text){const n=document.createElement(tag);if(cls)n.className=cls;if(text!==undefined&&text!==null)n.textContent=text;return n;}
  function when(ts){return ts?new Date(ts*1000).toLocaleString('vi-VN'):'—';}
  function select(id,label,options,value){
    const wrap=document.createDocumentFragment();const l=node('label','',label);l.htmlFor=id;
    const s=node('select');s.id=id;options.forEach(([v,t])=>s.append(new Option(t,v)));s.value=value;wrap.append(l,s);return [wrap,s];
  }

  function mount(root,{api,editable,basePath,onError,onChange}){
    let page=1,selectedId=null,items=[],requestId=0;
    const metrics=node('div','metrics feedback-metrics');metrics.setAttribute('aria-label','Thống kê đánh giá câu trả lời');
    const filters=node('div','admin-filters feedback-filters');
    const [ratingWrap,ratingFilter]=select(basePath.replace(/\W/g,'')+'-fb-rating','Đánh giá',[['incorrect','Chưa đúng'],['helpful','Hữu ích'],['','Tất cả']],'incorrect');
    const [statusWrap,statusFilter]=select(basePath.replace(/\W/g,'')+'-fb-status','Xử lý',[['','Tất cả'],['new','Mới'],['reviewed','Đã xem'],['resolved','Đã xử lý']],'');
    filters.append(ratingWrap,statusWrap);
    const body=node('div','desk-body feedback-body');
    const list=node('section','desk-list');const scroll=node('div','table-scroll');
    const table=node('table','admin-table feedback-table');table.append(node('caption','','Danh sách đánh giá câu trả lời AI'));
    const head=node('thead');const hr=node('tr');['Thời gian','Câu hỏi','Đánh giá','Lý do','Xử lý'].forEach(h=>hr.append(node('th','',h)));head.append(hr);
    const rows=node('tbody');table.append(head,rows);scroll.append(table);
    const pager=node('div','pager');const prev=node('button','small-action','← Trước');prev.type='button';const info=node('span','hint');const next=node('button','small-action','Sau →');next.type='button';pager.append(prev,info,next);
    list.append(scroll,pager);
    const detail=node('section','ticket-detail feedback-detail');
    body.append(list,detail);root.replaceChildren(metrics,filters,body);
    renderEmpty();

    function renderEmpty(){
      const empty=node('div','empty-detail');empty.append(node('span','empty-detail-icon','⌁'),node('h2','','Chưa chọn đánh giá'),node('p','','Chọn một đánh giá để xem câu hỏi, câu trả lời của AI, nguồn đã trích và góp ý của thí sinh.'));
      detail.replaceChildren(empty);
    }
    function card(label,value,hint){const box=node('article','metric kpi-card');box.append(node('span','metric-label',label),node('b','metric-value',value));if(hint)box.append(node('small','hint',hint));return box;}
    function renderMetrics(sum){
      const rated=sum.total||0;const rate=rated?Math.round(1000*(sum.helpful||0)/rated)/10+'%':'Chưa đủ dữ liệu';
      const reasons=Object.entries(sum.reasons||{}).sort((a,b)=>b[1]-a[1]).map(([k,v])=>`${REASONS[k]||k}: ${v}`).join(' · ');
      metrics.replaceChildren(
        card('Tổng số đánh giá',String(rated)),
        card('Tỉ lệ hữu ích',rate,`${sum.helpful||0} hữu ích / ${sum.incorrect||0} chưa đúng`),
        card('Chưa đúng · chưa xử lý',String((sum.statuses?.new||0)+(sum.statuses?.reviewed||0)),`${sum.statuses?.new||0} mới · ${sum.statuses?.reviewed||0} đã xem · ${sum.statuses?.resolved||0} đã xử lý`),
        card('Lý do chưa đúng',reasons?'':'—',reasons||'Chưa có góp ý'),
      );
    }
    async function load(){
      const params=new URLSearchParams({page,page_size:PAGE_SIZE});
      if(ratingFilter.value)params.set('rating',ratingFilter.value);
      if(statusFilter.value)params.set('status',statusFilter.value);
      const id=++requestId;const data=await api(basePath+'?'+params);if(id!==requestId)return;
      items=data.items;renderMetrics(data.summary||{});if(onChange)onChange(data.summary||{});
      rows.replaceChildren();
      if(!items.length){const tr=node('tr');const td=node('td','empty-state','Chưa có đánh giá phù hợp.');td.colSpan=5;tr.append(td);rows.append(tr);}
      items.forEach(f=>{
        const tr=node('tr','clickable'+(selectedId===f.id?' selected':''));tr.tabIndex=0;tr.setAttribute('role','button');tr.setAttribute('aria-label','Mở đánh giá: '+(f.question||'').slice(0,60));
        const cell=(label,value,cls='')=>{const td=node('td',cls,value);td.dataset.label=label;return td;};
        const ratingCell=cell('Đánh giá','');ratingCell.append(node('span','badge fb-'+f.rating,RATINGS[f.rating]||f.rating));
        const statusCell=cell('Xử lý','');if(f.rating==='incorrect')statusCell.append(node('span','badge fb-status-'+f.status,STATUSES[f.status]||f.status));else statusCell.textContent='—';
        tr.append(cell('Thời gian',when(f.created),'nowrap'),cell('Câu hỏi',(f.question||'(không còn câu hỏi)').slice(0,90)),ratingCell,cell('Lý do',f.rating==='incorrect'?(REASONS[f.reason]||REASONS.unspecified):'—'),statusCell);
        const open=()=>{selectedId=f.id;renderDetail(f);rows.querySelectorAll('tr').forEach(r=>r.classList.toggle('selected',r===tr));};
        tr.onclick=open;tr.onkeydown=e=>{if(e.key==='Enter'||e.key===' '){e.preventDefault();open();}};rows.append(tr);
      });
      const pages=Math.max(1,Math.ceil(data.total/PAGE_SIZE));info.textContent=`Trang ${page}/${pages} · ${data.total} đánh giá`;prev.disabled=page<=1;next.disabled=page>=pages;
      const current=items.find(f=>f.id===selectedId);
      if(current&&!isEditing())renderDetail(current);else if(!current&&selectedId===null)renderEmpty();
    }
    function isEditing(){
      const a=document.activeElement;
      if(a&&detail.contains(a)&&(a.tagName==='TEXTAREA'||a.tagName==='SELECT'))return true;
      return detail.querySelector('textarea')?.dataset.dirty==='1';
    }
    function renderDetail(f){
      const header=node('header','detail-header');const title=node('div');
      const meta=node('p','detail-meta');meta.append(node('span','',when(f.created)),node('span','',f.program?`Chương trình: ${f.program}`:'Phạm vi: toàn trường'),node('span','',f.mode==='llm'?'AI tổng hợp':'Tra cứu tài liệu'));
      title.append(node('h2','',RATINGS[f.rating]||f.rating),meta);header.append(title);
      if(f.rating==='incorrect')header.append(node('span','badge fb-status-'+f.status,STATUSES[f.status]||f.status));
      const box=node('div','detail-scroll');
      const convo=node('div','convo');
      const msg=(kind,who,avatar,text)=>{const m=node('article','convo-msg from-'+kind);const b=node('div','convo-body');b.append(node('span','convo-who',who),node('div','convo-bubble',text));const a=node('span','convo-avatar',avatar);
        if(kind==='ai'){a.textContent='';const img=document.createElement('img');img.className='brand-logo';img.src='/assets/hust-logo.png';img.alt='';a.append(img);}m.append(a,b);return m;};
      convo.append(msg('candidate','Câu hỏi của thí sinh','TS',f.question||'(Không lưu được câu hỏi)'),msg('ai','Trợ lý AI đã trả lời','',f.answer||'(Không có nội dung)'));
      box.append(convo);
      if(f.sources?.length){
        box.append(node('h3','detail-subtitle',`Nguồn đã trích (${f.sources.length})`));
        f.sources.forEach(s=>{const c=node('details','source-card');c.append(node('summary','',`${s.title||'Nguồn'}${s.page?` · PDF trang ${s.page}`:''}`));if(s.quote||s.text)c.append(node('p','',s.quote||s.text));box.append(c);});
      }
      if(f.rating==='incorrect'){
        box.append(node('h3','detail-subtitle','Góp ý của thí sinh'));
        const facts=node('dl','facts');facts.append(node('dt','','Lý do'),node('dd','',REASONS[f.reason]||REASONS.unspecified),node('dt','','Ghi chú'),node('dd','',f.note||'—'));
        if(f.reviewed_by)facts.append(node('dt','','Người xử lý'),node('dd','',`${f.reviewed_by} · ${when(f.reviewed_at)}`));
        if(!editable&&f.admin_note)facts.append(node('dt','','Ghi chú quản trị'),node('dd','',f.admin_note));
        box.append(facts);
      }
      detail.replaceChildren(header,box);
      if(!editable||f.rating!=='incorrect')return;
      const footer=node('footer','detail-composer');const form=node('div','ticket-actions feedback-review');
      const fields=node('div','reassign-fields');
      const pick=node('div');const sl=node('label','','Trạng thái xử lý');sl.htmlFor='fb-review-status';const st=node('select');st.id='fb-review-status';
      Object.entries(STATUSES).forEach(([v,t])=>st.append(new Option(t,v)));st.value=f.status;pick.append(sl,st);
      const why=node('div');const nl=node('label','','Ghi chú nội bộ');nl.htmlFor='fb-review-note';const note=node('textarea');note.id='fb-review-note';note.rows=2;note.maxLength=1000;note.value=f.admin_note||'';note.placeholder='Ví dụ: đã bổ sung trang 12 vào tài liệu';
      note.oninput=()=>{note.dataset.dirty='1';};why.append(nl,note);fields.append(pick,why);
      const err=node('p','error-text');err.setAttribute('role','alert');
      const save=node('button','primary','Lưu xử lý →');save.type='button';
      save.onclick=async()=>{err.textContent='';save.disabled=true;
        try{const updated=await api(basePath+'/'+f.id,{method:'PATCH',body:JSON.stringify({status:st.value,admin_note:note.value})});note.dataset.dirty='';Object.assign(f,updated);await load();renderDetail(f);}
        catch(e){err.textContent=e.message;save.disabled=false;}};
      const row=node('div','action-row');row.append(save);form.append(fields,row,err);footer.append(form);detail.append(footer);
    }
    ratingFilter.onchange=statusFilter.onchange=()=>{page=1;selectedId=null;renderEmpty();load().catch(onError);};
    prev.onclick=()=>{page--;load().catch(onError);};next.onclick=()=>{page++;load().catch(onError);};
    return {load,isEditing};
  }
  window.FeedbackView={mount};
})();
