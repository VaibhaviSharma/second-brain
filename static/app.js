/**
 * app.js — Second Brain web UI (single-page app)
 *
 * Vanilla JS, no framework. Hash-router (#dashboard, #browse, #tags, #types,
 * #category) drives which view is rendered. All data comes from the Flask REST
 * API at /api/*. State is kept in the global `S` object.
 */
'use strict';
/* ── constants ── */
const TC={note:'#58a6ff',link:'#79c0ff',skill:'#ffa657',job:'#56d364',idea:'#d2a8ff',resource:'#8b949e'};
const TI={note:'📝',link:'🔗',skill:'⚡',job:'💼',idea:'💡',resource:'📚'};
const PC=['','#f85149','#ffa657','#e3b341','#3fb950','#8b949e'];
const tc=t=>TC[t]||'#8b949e';

/* ── category config ── */
const CAT_META={
  link:    {label:'To Read',    icon:'📖',color:'#79c0ff'},
  job:     {label:'Jobs',       icon:'💼',color:'#56d364'},
  skill:   {label:'Skills',     icon:'🎯',color:'#ffa657'},
  idea:    {label:'Ideas',      icon:'💡',color:'#d2a8ff'},
  note:    {label:'Notes',      icon:'📝',color:'#8b949e'},
  resource:{label:'Inspiration',icon:'✨',color:'#e3b341'},
};
const CAT_ORDER=['link','job','skill','idea','note','resource'];

function tbadge(t){const c=tc(t);return `<span class="tbadge" style="background:${c}1a;color:${c};border:1px solid ${c}44">${x(t)}</span>`}
function sbadge(s){return `<span class="sb2 s-${s}">${s}</span>`}
function pdots(p){const c=PC[p]||'var(--txm)';return `<span class="pd" style="color:${c}" title="Priority ${p}">${'●'.repeat(p)}${'○'.repeat(5-p)}</span>`}
function tagsH(tags){
  if(!tags||!tags.trim()) return '';
  return tags.split(',').filter(t=>t.trim())
    .map(t=>`<a class="tag" href="#browse?tag=${enc(t.trim())}" onclick="event.stopPropagation()">#${x(t.trim())}</a>`).join(' ');
}
function x(s){return String(s||'').replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;')}
function enc(s){return encodeURIComponent(s)}
function fd(iso){return iso?iso.slice(0,10):''}

/* ── state ── */
const S={view:'dashboard',entries:[],total:0,expanded:null,editing:null,
  filters:{q:'',type:'',tag:'',status:'active',sort:'created_at',order:'desc',page:0,limit:25}};

/* ── api ── */
async function api(m,path,data){
  const o={method:m,headers:{'Content-Type':'application/json'}};
  if(data!==undefined) o.body=JSON.stringify(data);
  const r=await fetch('/api'+path,o);
  if(!r.ok){const e=await r.json().catch(()=>({error:r.statusText}));throw new Error(e.error||r.statusText)}
  if(r.status===204||m==='DELETE') return null;
  return r.json();
}

/* ── toast ── */
function toast(msg,t='ok'){
  const el=document.createElement('div');
  el.className=`toast t${t}`;el.textContent=msg;
  document.getElementById('toasts').appendChild(el);
  setTimeout(()=>el.remove(),3000);
}

/* ── router ── */
function navigate(view,params={}){
  const qs=Object.keys(params).length?'?'+new URLSearchParams(params):'';
  window.location.hash='#'+view+qs;
}
function router(){
  const hash=window.location.hash||'#dashboard';
  const[view,qs]=hash.slice(1).split('?');
  const p=Object.fromEntries(new URLSearchParams(qs||''));
  document.querySelectorAll('.nl').forEach(a=>a.classList.toggle('active',a.dataset.view===view));
  document.getElementById('sb').classList.remove('open');
  switch(view){
    case 'category': _renderCategory(p.type||'');break;
    case 'browse':
      if(p.tag)    S.filters.tag=p.tag;
      if(p.type)   S.filters.type=p.type;
      if(p.status) S.filters.status=p.status;
      if(p.q)      S.filters.q=p.q;
      renderBrowse();break;
    case 'tags':  renderTags();break;
    case 'types': renderTypes();break;
    default:      renderDashboard();break;
  }
}
function setHTML(h){document.getElementById('app').innerHTML=h}

/* ── entry card ── */
function ecard(e,expanded,editing){
  if(editing) return `
  <div class="card ex" id="e${e.id}"><form onsubmit="saveEdit(event,${e.id})">
    <div class="fr">
      <div class="fg"><label class="fl">Title *</label><input class="fc" name="title" value="${x(e.title)}" required></div>
      <div class="fg"><label class="fl">Type</label><input class="fc" name="type" value="${x(e.type)}" list="tdl">
        <datalist id="tdl"><option value="note"><option value="link"><option value="skill">
          <option value="job"><option value="idea"><option value="resource"></datalist></div>
    </div>
    <div class="fg"><label class="fl">Content</label><textarea class="fc" name="content">${x(e.content)}</textarea></div>
    <div class="fr">
      <div class="fg"><label class="fl">URL</label><input class="fc" name="url" type="url" value="${x(e.url)}" placeholder="https://…"></div>
      <div class="fg"><label class="fl">Tags</label><input class="fc" name="tags" value="${x(e.tags)}" placeholder="a,b,c"></div>
    </div>
    <div class="fr">
      <div class="fg"><label class="fl">Priority 1–5</label><input class="fc" name="priority" type="number" min="1" max="5" value="${e.priority}"></div>
      <div class="fg"><label class="fl">Status</label><select class="fc" name="status">
        <option ${e.status==='active'?'selected':''}>active</option>
        <option ${e.status==='archived'?'selected':''}>archived</option>
        <option ${e.status==='done'?'selected':''}>done</option>
      </select></div>
    </div>
    <div style="display:flex;gap:7px;margin-top:2px">
      <button type="submit" class="btn btn-p btn-sm">Save</button>
      <button type="button" class="btn btn-sm" onclick="cancelEdit(${e.id})">Cancel</button>
    </div>
  </form></div>`;

  const cprev=e.content?`<div class="econt">${x(expanded?e.content:e.content.slice(0,150)+(e.content.length>150?'…':''))}</div>`:'';
  const xtra=expanded?`
    ${e.url?`<div class="eurl"><a href="${x(e.url)}" target="_blank" rel="noopener">🔗 ${x(e.url)}</a></div>`:''}
    <div class="etrow">${tagsH(e.tags)}</div>
    <div class="edt" style="margin-top:7px">Created ${fd(e.created_at)} · Updated ${fd(e.updated_at)}</div>
    <div class="eact">
      <button class="btn btn-sm" onclick="startEdit(${e.id})">✏ Edit</button>
      ${e.status!=='done'?    `<button class="btn btn-sm" style="color:var(--gn);border-color:var(--gn)" onclick="setSt(${e.id},'done')">✓ Done</button>`:''}
      ${e.status!=='archived'?`<button class="btn btn-sm" onclick="setSt(${e.id},'archived')">⊘ Archive</button>`:''}
      ${e.status!=='active'?  `<button class="btn btn-sm" onclick="setSt(${e.id},'active')">↺ Restore</button>`:''}
      <button class="btn btn-sm btn-d" onclick="delE(${e.id})">✕ Delete</button>
    </div>`:'';
  const tinline=!expanded&&e.tags?`<span style="font-size:11px;color:var(--txm)">${e.tags.split(',').filter(t=>t.trim()).map(t=>'#'+t.trim()).join(' ')}</span>`:'';

  return `
  <div class="card${expanded?' ex':''}" id="e${e.id}">
    <div class="eh" onclick="toggleEx(${e.id})">
      <div style="flex:1;min-width:0">
        <div style="display:flex;align-items:center;gap:7px;flex-wrap:wrap">${tbadge(e.type)}<span class="et">${x(e.title)}</span></div>
        <div class="em">${pdots(e.priority)}${sbadge(e.status)}<span class="edt">${fd(e.created_at)}</span>${tinline}</div>
      </div>
      <span class="exarr">${expanded?'▲':'▽'}</span>
    </div>${cprev}${xtra}
  </div>`;
}

/* ── expand / edit ── */
function toggleEx(id){if(S.editing===id)return;S.expanded=S.expanded===id?null:id;reList()}
function startEdit(id){S.editing=id;S.expanded=id;reList()}
function cancelEdit(id){S.editing=null;reList()}
function reList(){
  const el=document.getElementById('el');
  if(el) el.innerHTML=S.entries.map(e=>ecard(e,S.expanded===e.id,S.editing===e.id)).join('');
}

/* ── crud ── */
async function saveEdit(ev,id){
  ev.preventDefault();
  const d=Object.fromEntries(new FormData(ev.target));d.priority=parseInt(d.priority)||3;
  try{
    const u=await api('PUT',`/entries/${id}`,d);
    const i=S.entries.findIndex(e=>e.id===id);if(i!==-1)S.entries[i]=u;
    S.editing=null;S.expanded=id;reList();toast('Saved ✓');
  }catch(e){toast(e.message,'err')}
}
async function setSt(id,status){
  try{
    const u=await api('PUT',`/entries/${id}`,{status});
    const i=S.entries.findIndex(e=>e.id===id);
    if(i!==-1){
      if(S.filters.status&&S.filters.status!==status){S.entries.splice(i,1);S.total--;}
      else S.entries[i]=u;
    }
    reList();toast('Marked '+status);updCnt();
  }catch(e){toast(e.message,'err')}
}
async function delE(id){
  const e=S.entries.find(e=>e.id===id);
  if(!confirm(`Delete "${e?.title}"?`)) return;
  try{
    await api('DELETE',`/entries/${id}`);
    S.entries=S.entries.filter(e=>e.id!==id);S.total--;
    if(S.expanded===id) S.expanded=null;
    reList();toast('Deleted');updCnt();
  }catch(e){toast(e.message,'err')}
}
function updCnt(){
  const el=document.getElementById('ecnt');
  if(!el) return;
  const f=S.filters,from=f.page*f.limit+1,to=Math.min((f.page+1)*f.limit,S.total);
  el.textContent=S.total>0?`${from}–${to} of ${S.total}`:'0 entries';
}

/* ── quick-add / modal ── */
async function submitQA(ev){
  ev.preventDefault();
  const d=Object.fromEntries(new FormData(ev.target));d.priority=parseInt(d.priority)||3;
  if(!d.title.trim()){toast('Title required','err');return}
  try{
    const e=await api('POST','/entries',d);
    toast(`Saved #${e.id} ✓`);ev.target.reset();
    ev.target.querySelector('[name=priority]').value=3;
    if(S.view==='dashboard') renderDashboard();
  }catch(e){toast(e.message,'err')}
}

function openModal(){
  document.getElementById('mt').textContent='Add Entry';
  document.getElementById('mb').innerHTML=`
  <form onsubmit="submitModal(event)">
    <div class="fr">
      <div class="fg"><label class="fl">Title *</label><input class="fc" name="title" required autofocus></div>
      <div class="fg"><label class="fl">Type</label><input class="fc" name="type" value="note" list="m-tdl">
        <datalist id="m-tdl"><option value="note"><option value="link"><option value="skill">
          <option value="job"><option value="idea"><option value="resource"></datalist></div>
    </div>
    <div class="fg"><label class="fl">Content</label><textarea class="fc" name="content" placeholder="Details…"></textarea></div>
    <div class="fr">
      <div class="fg"><label class="fl">URL</label><input class="fc" name="url" type="url" placeholder="https://…"></div>
      <div class="fg"><label class="fl">Tags</label><input class="fc" name="tags" placeholder="tag1,tag2"></div>
    </div>
    <div class="fr">
      <div class="fg"><label class="fl">Priority (1–5)</label><input class="fc" name="priority" type="number" min="1" max="5" value="3"></div>
      <div class="fg"><label class="fl">Status</label><select class="fc" name="status">
        <option>active</option><option>archived</option><option>done</option></select></div>
    </div>
    <div style="display:flex;gap:7px;justify-content:flex-end;margin-top:6px">
      <button type="button" class="btn btn-sm" onclick="closeModal()">Cancel</button>
      <button type="submit" class="btn btn-p btn-sm">Add Entry</button>
    </div>
  </form>`;
  document.getElementById('ov').classList.remove('hi');
  setTimeout(()=>document.querySelector('#mb input[name=title]')?.focus(),50);
}
async function submitModal(ev){
  ev.preventDefault();
  const d=Object.fromEntries(new FormData(ev.target));d.priority=parseInt(d.priority)||3;
  try{
    const e=await api('POST','/entries',d);
    toast(`Saved #${e.id} ✓`);closeModal();
    if(S.view==='dashboard') renderDashboard();
    else if(S.view==='browse') fetchEntries();
  }catch(e){toast(e.message,'err')}
}
function closeModal(){document.getElementById('ov').classList.add('hi');document.getElementById('mb').innerHTML=''}
function ovClick(ev){if(ev.target===document.getElementById('ov'))closeModal()}

/* ── dashboard ── */
async function renderDashboard(){
  S.view='dashboard';S.expanded=null;S.editing=null;
  S.filters={q:'',type:'',tag:'',status:'active',sort:'created_at',order:'desc',page:0,limit:25};
  setHTML('<div class="loading">Loading…</div>');
  try{
    const[stats,recent,inboxData]=await Promise.all([
      api('GET','/stats'),
      api('GET','/entries?limit=10&sort=created_at&order=desc'),
      api('GET','/inbox/count').catch(()=>({count:0}))
    ]);
    S.entries=recent.entries;
    const bt=stats.by_type||{};

    const knownCards=CAT_ORDER.map(type=>{
      const m=CAT_META[type];
      const cnt=bt[type]||0;
      return `<div class="catcard" style="--cc:${m.color}" onclick="navigate('category',{type:'${type}'})">
        <div class="caticon">${m.icon}</div>
        <div class="catname">${m.label}</div>
        <div class="catcount">${cnt}</div>
        <div class="catsub">entr${cnt===1?'y':'ies'}</div>
      </div>`;
    }).join('');
    const extraCards=Object.entries(bt)
      .filter(([t])=>!CAT_ORDER.includes(t))
      .map(([type,cnt])=>`<div class="catcard" style="--cc:#8b949e" onclick="navigate('category',{type:'${enc(type)}'})">
        <div class="caticon">◈</div>
        <div class="catname">${x(type)}</div>
        <div class="catcount">${cnt}</div>
        <div class="catsub">entr${cnt===1?'y':'ies'}</div>
      </div>`).join('');

    const rHTML=recent.entries.length
      ?recent.entries.map(e=>ecard(e,false,false)).join('')
      :'<div class="empty"><div class="eicon">📭</div>No entries yet — add your first one above!</div>';

    setHTML(`
      ${inboxData.count>0?`<div class="inbox-ban">
        <span>📥 <strong>${inboxData.count}</strong> item${inboxData.count===1?'':'s'} waiting in inbox</span>
        <button class="btn btn-sm btn-p" onclick="importInbox()">Import now</button>
      </div>`:''}
      <div class="srch-bar">
        <input class="fc" placeholder="🔍 Search everything…" oninput="dashSearch(this.value)">
        <button class="btn btn-p" onclick="openModal()">+ Add</button>
      </div>
      <div class="qabox"><div class="qah">Quick Add</div>
        <form onsubmit="submitQA(event)">
          <div class="fr">
            <div class="fg"><input class="fc" name="title" placeholder="Title *" required autocomplete="off"></div>
            <div class="fg"><input class="fc" name="type" value="note" list="qa-dl">
              <datalist id="qa-dl"><option value="note"><option value="link"><option value="skill">
                <option value="job"><option value="idea"><option value="resource"></datalist></div>
          </div>
          <div class="fg"><textarea class="fc" name="content" placeholder="Content (optional)" style="min-height:52px"></textarea></div>
          <div class="fr">
            <div class="fg"><input class="fc" name="url" type="url" placeholder="URL (optional)"></div>
            <div class="fg"><input class="fc" name="tags" placeholder="tag1,tag2"></div>
          </div>
          <div style="display:flex;align-items:center;gap:8px">
            <label class="fl" style="margin:0;white-space:nowrap">Priority:</label>
            <input class="fc" name="priority" type="number" min="1" max="5" value="3" style="width:55px">
            <button type="submit" class="btn btn-p" style="margin-left:auto">+ Add</button>
          </div>
        </form>
      </div>
      <button class="rand-btn" onclick="showRandom()">🎲 Pick something for me</button>
      <div class="catgrid">${knownCards}${extraCards}</div>
      <div class="sh"><div class="st">Recently Added</div><a href="#browse" class="btn btn-sm">View all →</a></div>
      <div id="el" class="elist">${rHTML}</div>
    `);
  }catch(e){setHTML(`<div class="empty">Error: ${x(e.message)}</div>`)}
}

/* ── category view ── */
async function _renderCategory(type){
  if(!type){navigate('dashboard');return}
  S.view='category';S.expanded=null;S.editing=null;
  S.filters={q:'',type,tag:'',status:'active',sort:'priority',order:'asc',page:0,limit:25};
  const m=CAT_META[type]||{label:type,icon:'◈',color:'#8b949e'};
  setHTML(`
    <div class="cat-hdr">
      <button class="btn btn-sm" onclick="navigate('dashboard')">← Back</button>
      <div style="flex:1;display:flex;align-items:center;gap:8px">
        <span style="font-size:22px">${m.icon}</span>
        <span style="font-size:17px;font-weight:700;color:${m.color}">${x(m.label)}</span>
        <span id="ecnt" class="sub"></span>
      </div>
      <button class="btn btn-p btn-sm" onclick="openModal()">+ Add</button>
    </div>
    <div id="el" class="elist"><div class="loading">Loading…</div></div>
    <div id="pag" class="pag"></div>
  `);
  await fetchEntries();
}

/* ── random pick ── */
async function showRandom(){
  try{
    const e=await api('GET','/random');
    const m=CAT_META[e.type]||{label:e.type,icon:'◈'};
    document.getElementById('mt').textContent='🎲 Surprise Pick';
    document.getElementById('mb').innerHTML=`
      <div>
        <div style="display:flex;gap:7px;align-items:center;flex-wrap:wrap;margin-bottom:12px">
          ${tbadge(e.type)}${sbadge(e.status)}${pdots(e.priority)}
          <span class="edt">Created ${fd(e.created_at)}</span>
        </div>
        <div style="font-size:16px;font-weight:600;color:var(--txs);margin-bottom:10px">${x(e.title)}</div>
        ${e.content?`<div style="font-size:13px;color:var(--tx);white-space:pre-wrap;line-height:1.6;border-top:1px solid var(--bd);padding-top:10px;margin-bottom:10px">${x(e.content)}</div>`:''}
        ${e.url?`<div style="font-size:12px;margin-bottom:10px"><a href="${x(e.url)}" target="_blank" rel="noopener" style="color:var(--ac)">🔗 ${x(e.url)}</a></div>`:''}
        ${e.tags?`<div style="margin-bottom:12px">${tagsH(e.tags)}</div>`:''}
        <div style="display:flex;gap:6px;flex-wrap:wrap;border-top:1px solid var(--bd);padding-top:12px">
          ${e.status!=='done'?`<button class="btn btn-sm" style="color:var(--gn);border-color:var(--gn)" onclick="randAct(${e.id},'done')">✓ Done</button>`:''}
          ${e.status!=='archived'?`<button class="btn btn-sm" onclick="randAct(${e.id},'archived')">⊘ Archive</button>`:''}
          <button class="btn btn-sm" onclick="closeModal();navigate('category',{type:'${enc(e.type)}'})">
            Open in ${x(m.label)}</button>
          <button class="btn btn-sm" onclick="showRandom()" style="margin-left:auto">🎲 Another</button>
        </div>
      </div>`;
    document.getElementById('ov').classList.remove('hi');
  }catch(err){
    toast(err.message.includes('no active')?'No active entries found!':err.message,'err');
  }
}
async function randAct(id,status){
  try{await api('PUT',`/entries/${id}`,{status});toast('Marked '+status);closeModal()}
  catch(e){toast(e.message,'err')}
}

/* ── dashboard search (navigates to browse) ── */
let _dqs;
function dashSearch(q){
  clearTimeout(_dqs);
  if(!q.trim()) return;
  _dqs=setTimeout(()=>{S.filters.q=q;navigate('browse');},350);
}

/* ── inbox import ── */
async function importInbox(){
  try{
    const r=await api('POST','/inbox/import');
    if(r.imported===0){toast('Inbox was empty','err');return}
    toast(`✓ Imported ${r.imported} item${r.imported===1?'':'s'}`);
    renderDashboard();
  }catch(e){toast(e.message,'err')}
}

/* ── browse ── */
async function renderBrowse(){
  S.view='browse';S.expanded=null;S.editing=null;
  const f=S.filters;
  setHTML(`
    <div class="sh"><div class="st">Browse</div>
      <div style="display:flex;gap:7px;align-items:center">
        <span id="ecnt" class="sub"></span>
        <button class="btn btn-p btn-sm" onclick="openModal()">+ Add</button>
      </div>
    </div>
    <div class="fb">
      <input class="fc fsrch" id="fq" placeholder="🔍 Search…" value="${x(f.q)}" oninput="dsearch(this.value)">
      <select class="fc" id="ftype" onchange="apF('type',this.value)"><option value="">All types</option></select>
      <select class="fc" id="fstatus" onchange="apF('status',this.value)">
        <option value="">All statuses</option>
        <option value="active"   ${f.status==='active'?'selected':''}>Active</option>
        <option value="done"     ${f.status==='done'?'selected':''}>Done</option>
        <option value="archived" ${f.status==='archived'?'selected':''}>Archived</option>
      </select>
      <select class="fc" id="ftag" onchange="apF('tag',this.value)"><option value="">All tags</option></select>
      <select class="fc" id="fsort" onchange="apSort(this.value)">
        <option value="created_at" ${f.sort==='created_at'?'selected':''}>Date ↓</option>
        <option value="priority"   ${f.sort==='priority'?'selected':''}>Priority ↑</option>
        <option value="updated_at" ${f.sort==='updated_at'?'selected':''}>Updated ↓</option>
        <option value="title"      ${f.sort==='title'?'selected':''}>Title A–Z</option>
      </select>
      <button class="btn btn-sm" onclick="clearF()">✕ Clear</button>
    </div>
    <div id="el" class="elist"><div class="loading">Loading…</div></div>
    <div id="pag" class="pag"></div>
  `);
  const[types,tags]=await Promise.all([api('GET','/types').catch(()=>[]),api('GET','/tags').catch(()=>[])]);
  const ts=document.getElementById('ftype');
  if(ts) types.forEach(t=>{const o=new Option(`${t.type} (${t.count})`,t.type,false,f.type===t.type);ts.appendChild(o)});
  const tg=document.getElementById('ftag');
  if(tg) tags.slice(0,60).forEach(t=>{const o=new Option(`#${t.tag} (${t.count})`,t.tag,false,f.tag===t.tag);tg.appendChild(o)});
  await fetchEntries();
}
async function fetchEntries(){
  const f=S.filters;
  const p=new URLSearchParams({q:f.q,type:f.type,tag:f.tag,status:f.status,
    sort:f.sort,order:f.order,limit:f.limit,offset:f.page*f.limit});
  try{
    const data=await api('GET',`/entries?${p}`);
    S.entries=data.entries;S.total=data.total;
    const el=document.getElementById('el'),pg=document.getElementById('pag');
    if(el) el.innerHTML=S.entries.length
      ?S.entries.map(e=>ecard(e,S.expanded===e.id,S.editing===e.id)).join('')
      :'<div class="empty"><div class="eicon">🔍</div>No entries match these filters.</div>';
    updCnt();
    if(pg){
      const tot=Math.ceil(S.total/f.limit);
      pg.innerHTML=tot>1?`
        <button class="btn btn-sm" onclick="changePg(-1)" ${f.page===0?'disabled':''}>← Prev</button>
        <span class="sub">Page ${f.page+1} of ${tot}</span>
        <button class="btn btn-sm" onclick="changePg(1)"  ${f.page>=tot-1?'disabled':''}>Next →</button>
      `:'';
    }
  }catch(e){const el=document.getElementById('el');if(el)el.innerHTML=`<div class="empty">Error: ${x(e.message)}</div>`}
}
function apF(k,v){S.filters[k]=v;S.filters.page=0;S.expanded=null;S.editing=null;fetchEntries()}
function apSort(v){S.filters.sort=v;S.filters.order=v==='title'?'asc':'desc';S.filters.page=0;fetchEntries()}
function clearF(){S.filters={q:'',type:'',tag:'',status:'active',sort:'created_at',order:'desc',page:0,limit:25};renderBrowse()}
function changePg(d){S.filters.page=Math.max(0,S.filters.page+d);S.expanded=null;S.editing=null;fetchEntries()}
let _st;function dsearch(q){clearTimeout(_st);_st=setTimeout(()=>{S.filters.q=q;S.filters.page=0;fetchEntries()},280)}

/* ── tags ── */
async function renderTags(){
  S.view='tags';setHTML('<div class="loading">Loading…</div>');
  try{
    const tags=await api('GET','/tags');
    if(!tags.length){setHTML('<div class="empty"><div class="eicon">#</div>No tags yet.</div>');return}
    const mx=tags[0].count;
    const pills=tags.map(t=>{
      const sz=13+Math.round((t.count/mx)*10);
      return `<span class="tpill" onclick="navigate('browse',{tag:'${enc(t.tag)}'})" style="font-size:${sz}px">
        #${x(t.tag)}<span class="tcnt">${t.count}</span></span>`;
    }).join('');
    setHTML(`<div class="sh"><div class="st">Tags</div><span class="sub">${tags.length} tags</span></div>
      <div class="tgrid">${pills}</div>`);
  }catch(e){setHTML(`<div class="empty">Error: ${x(e.message)}</div>`)}
}

/* ── types ── */
async function renderTypes(){
  S.view='types';setHTML('<div class="loading">Loading…</div>');
  try{
    const types=await api('GET','/types');
    if(!types.length){setHTML('<div class="empty"><div class="eicon">⊙</div>No types yet.</div>');return}
    const cards=types.map(t=>{
      const col=tc(t.type),icon=TI[t.type]||'◈';
      return `<div class="typecard" onclick="navigate('browse',{type:'${x(t.type)}'})" style="border-color:${col}44">
        <div class="tyi">${icon}</div>
        <div class="tyn" style="color:${col}">${x(t.type)}</div>
        <div class="tyc">${t.count} entr${t.count===1?'y':'ies'}</div>
      </div>`;
    }).join('');
    setHTML(`<div class="sh"><div class="st">Types</div><span class="sub">${types.length} types</span></div>
      <div class="typegrid">${cards}</div>`);
  }catch(e){setHTML(`<div class="empty">Error: ${x(e.message)}</div>`)}
}

/* ── theme / sidebar ── */
function toggleTheme(){
  const h=document.documentElement,dark=h.dataset.theme==='dark';
  h.dataset.theme=dark?'light':'dark';
  localStorage.setItem('brain-theme',h.dataset.theme);
  document.getElementById('thbtn').textContent=dark?'🌙':'◑';
}
function toggleSB(){document.getElementById('sb').classList.toggle('open')}

/* ── init ── */
function init(){
  const saved=localStorage.getItem('brain-theme')||'dark';
  document.documentElement.dataset.theme=saved;
  document.getElementById('thbtn').textContent=saved==='dark'?'◑':'🌙';
  document.getElementById('thbtn').addEventListener('click',toggleTheme);
  window.addEventListener('hashchange',router);
  document.addEventListener('click',ev=>{
    const sb=document.getElementById('sb');
    if(sb.classList.contains('open')&&!sb.contains(ev.target))sb.classList.remove('open');
  });
  router();
}
document.addEventListener('DOMContentLoaded',init);
