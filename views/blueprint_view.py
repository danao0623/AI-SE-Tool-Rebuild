from nicegui import ui, app
from flow_controllers.blueprint_api_flow import router as blueprint_router


# 只 include 一次 router
if not getattr(app, "_blueprint_router_included", False):
    app.include_router(blueprint_router)
    app._blueprint_router_included = True

def _get_current_project_id_or_redirect() -> int:
    current_project = app.storage.user.get("current_project") or {}
    pid = current_project.get("id")

    if pid is not None:
      try:
        return int(pid)
      except Exception:
        pass 

@ui.page("/blueprint")
def blueprint_page():
    project_id = _get_current_project_id_or_redirect()

    ui.add_head_html(r"""
    <script src="https://cdn.jsdelivr.net/npm/interactjs/dist/interact.min.js"></script>
    <script src="https://cdn.jsdelivr.net/npm/html2canvas@1.4.1/dist/html2canvas.min.js"></script>                 
    <style>
      html, body, #q-app{ height:100%; width:100%; margin:0 !important; padding:0 !important; }
      .q-page, .q-layout-padding, .q-pa-md{ padding:0 !important; }
      body{ overflow:hidden; }

      .bp-designer{
        height: 100%;
        min-height: 100%;
        background: #f8fafc;
        border: 1px solid #e5e7eb;
        border-radius: 14px;
        padding: 12px;
        box-sizing: border-box;
        overflow: hidden;
      }

      .bp-grid{
        display: grid;
        grid-template-columns: minmax(220px, 22%) minmax(520px, 1fr) minmax(320px, 30%);
        gap: 12px;
        height: 100%;
        min-height: 0;
      }

      .bp-panel{
        border: 1px solid #e5e7eb;
        background: #ffffff;
        border-radius: 14px;
        padding: 12px;
        box-sizing: border-box;
        overflow: auto;
        min-height: 0;
        color: #111827;
      }

      .bp-title{ font-weight: 800; margin-bottom: 10px; color:#111827; }
      .bp-hint{ font-size: 12px; color:#6b7280; line-height: 1.4; margin-bottom: 10px; }

      .bp-palette{
        display: grid;
        grid-template-columns: 1fr;
        gap: 10px;
      }

      .bp-item{
        user-select: none;
        cursor: grab;
        border-radius: 12px;
        border: 1px solid #e5e7eb;
        background: #f9fafb;
        padding: 10px 12px;
        font-size: 13px;
        color:#111827;
        display:flex;
        align-items:center;
        justify-content: space-between;
        gap: 10px;
      }

      .bp-item-left{
        display:flex;
        align-items:center;
        gap: 8px;
        min-width: 0;
      }
      .bp-item-name{
        font-weight: 800;
        overflow:hidden;
        text-overflow: ellipsis;
        white-space: nowrap;
      }
      .bp-item-desc{
        font-size: 12px;
        opacity: .72;
        margin-left: 2px;
        white-space: nowrap;
      }

      .bp-item[data-type="Button"]   { background:#eff6ff; border-color:#3b82f6; }
      .bp-item[data-type="Input"]    { background:#f0fdf4; border-color:#22c55e; }
      .bp-item[data-type="Table"]    { background:#fff7ed; border-color:#f97316; }
      .bp-item[data-type="Card"]     { background:#fdf4ff; border-color:#a855f7; }
      .bp-item[data-type="Dropdown"] { background:#fefce8; border-color:#eab308; }
      .bp-item[data-type="Label"] {
        background:#f1f5f9;
        border: 1px dashed #64748b;
        color:#334155;
      }

      /* 新增元件：顏色 */
      .bp-item[data-type="Image"]    { background:#f0f9ff; border-color:#0ea5e9; }
      .bp-item[data-type="Checkbox"] { background:#fdf2f8; border-color:#ec4899; }
      .bp-item[data-type="Radio"]    { background:#f5f3ff; border-color:#8b5cf6; }
      .bp-item[data-type="Tabs"]     { background:#f8fafc; border-color:#64748b; }

      .bp-tag{
        font-size: 11px;
        padding: 2px 8px;
        border-radius: 999px;
        border: 1px solid #e5e7eb;
        background: #ffffff;
        color: #111827;
        flex: 0 0 auto;
      }
      .bp-tag.Button   { border-color:#3b82f6; color:#1d4ed8; }
      .bp-tag.Input    { border-color:#22c55e; color:#15803d; }
      .bp-tag.Table    { border-color:#f97316; color:#c2410c; }
      .bp-tag.Card     { border-color:#a855f7; color:#7e22ce; }
      .bp-tag.Dropdown { border-color:#eab308; color:#a16207; }
      .bp-tag.Label    { border-color:#64748b; color:#475569; }
      .bp-tag.Image    { border-color:#0ea5e9; color:#0369a1; }
      .bp-tag.Checkbox { border-color:#ec4899; color:#be185d; }
      .bp-tag.Radio    { border-color:#8b5cf6; color:#6d28d9; }
      .bp-tag.Tabs     { border-color:#64748b; color:#334155; }

      .bp-mid{
        display: grid;
        grid-template-rows: auto auto 1fr;
        gap: 10px;
        min-height: 0;
      }

      .bp-screenbar{
        display:flex;
        align-items:center;
        gap: 10px;
        border: 1px solid #e5e7eb;
        background:#ffffff;
        padding: 10px 12px;
        border-radius: 14px;
      }
      .bp-screenbar-label{
        font-size: 12px;
        color:#475569;
        font-weight: 800;
        white-space: nowrap;
      }
      .bp-screen-select{
        width: 100%;
        border-radius: 12px;
        border: 1px solid #e5e7eb;
        background: #ffffff;
        padding: 8px 10px;
        font-size: 13px;
        color:#111827;
        outline: none;
      }
      .bp-screen-select:focus{ border-color:#3b82f6; }

      .bp-toolbar{
        display: flex;
        gap: 10px;
        flex-wrap: wrap;
      }

      .bp-btn{
        border: 1px solid #e5e7eb;
        background: #ffffff;
        color: #111827;
        padding: 8px 10px;
        border-radius: 12px;
        cursor: pointer;
        font-size: 13px;
      }
      .bp-btn:hover{ background:#f9fafb; }

      .bp-canvas{
        position: relative;
        border-radius: 16px;
        border: 1px dashed #cbd5e1;
        background: #ffffff;
        overflow: hidden;
        height: 100%;
        min-height: 0;
      }

      .bp-drop-hint{
        position: absolute; inset: 0;
        display: grid; place-items: center;
        pointer-events: none;
        color: #94a3b8;
        font-size: 13px;
      }

      .bp-comp{
        position: absolute;
        border-radius: 12px;
        border: none !important;
        background: transparent !important;
        box-shadow: none !important;
        padding: 0 !important;
        box-sizing: border-box;
      }
      .bp-comp:hover{ outline: none !important; }
      .bp-comp.selected{
        outline: 2px solid #3b82f6 !important;
        outline-offset: 2px;
      }

      .bp-proxy-only{
        height: 100%;
        display: grid;
        align-items: center;
      }
      .bp-proxy-only .bp-proxy-body{ margin-top: 0; }
      .bp-proxy-only .bp-proxy-input,
      .bp-proxy-only .bp-proxy-select{ width: 100%; }

      .bp-row{
        display: grid;
        grid-template-columns: 88px 1fr;
        gap: 10px;
        align-items: center;
        margin: 8px 0;
        font-size: 13px;
        color:#374151;
      }

      .bp-row input, .bp-row select{
        width: 100%;
        border-radius: 10px;
        border: 1px solid #e5e7eb;
        background: #ffffff;
        color: #111827;
        padding: 8px 10px;
        outline: none;
        box-sizing: border-box;
        font-size: 13px;
      }

      .bp-subtitle{
        font-weight: 800;
        margin: 14px 0 8px 0;
        color:#111827;
        font-size: 13px;
      }

      .bp-comp-list{
        border: 1px solid #e5e7eb;
        border-radius: 12px;
        padding: 8px;
        max-height: 360px;
        overflow: auto;
        font-size: 12px;
        background: #ffffff;
      }

      .bp-comp-item{
        padding: 8px 10px;
        border-radius: 10px;
        cursor: pointer;
        display: grid;
        grid-template-columns: auto 1fr;
        gap: 8px;
      }

      .bp-comp-item:hover{ background: #f1f5f9; }
      .bp-comp-item.active{ background: #dbeafe; }

      .bp-dot{
        width: 10px;
        height: 10px;
        border-radius: 999px;
        border: 1px solid #e5e7eb;
        background: #cbd5e1;
        margin-top: 4px;
      }

      .bp-comp-item.type-Button   .bp-dot{ background:#3b82f6; border-color:#2563eb; }
      .bp-comp-item.type-Input    .bp-dot{ background:#22c55e; border-color:#16a34a; }
      .bp-comp-item.type-Table    .bp-dot{ background:#f97316; border-color:#ea580c; }
      .bp-comp-item.type-Card     .bp-dot{ background:#a855f7; border-color:#9333ea; }
      .bp-comp-item.type-Dropdown .bp-dot{ background:#eab308; border-color:#ca8a04; }
      .bp-comp-item.type-Label    .bp-dot{ background:#64748b; border-color:#475569; }
      .bp-comp-item.type-Image    .bp-dot{ background:#0ea5e9; border-color:#0284c7; }
      .bp-comp-item.type-Checkbox .bp-dot{ background:#ec4899; border-color:#db2777; }
      .bp-comp-item.type-Radio    .bp-dot{ background:#8b5cf6; border-color:#7c3aed; }
      .bp-comp-item.type-Tabs     .bp-dot{ background:#64748b; border-color:#475569; }

      .bp-comp-main{
        display:flex;
        flex-direction: column;
        gap: 4px;
        min-width: 0;
      }
      .bp-comp-line1{
        display:flex;
        gap: 8px;
        align-items: baseline;
        min-width: 0;
      }
      .bp-pill{
        font-size: 11px;
        padding: 1px 8px;
        border-radius: 999px;
        border: 1px solid #e5e7eb;
        background:#ffffff;
        color:#111827;
        flex: 0 0 auto;
      }
      .bp-comp-name{
        font-weight: 800;
        overflow: hidden;
        text-overflow: ellipsis;
        white-space: nowrap;
      }
      .bp-comp-line2{
        display:flex;
        flex-wrap: wrap;
        gap: 6px;
        color:#334155;
      }
      .bp-kv{
        border: 1px solid #e5e7eb;
        background:#f8fafc;
        border-radius: 10px;
        padding: 2px 8px;
        max-width: 100%;
        overflow:hidden;
        text-overflow: ellipsis;
        white-space: nowrap;
      }

      .bp-proxy-body{ margin-top: 8px; display: grid; gap: 8px; }

      .bp-proxy-input, .bp-proxy-select{
        width: 100%;
        border-radius: 10px;
        border: 1px solid #e5e7eb;
        padding: 8px 10px;
        font-size: 13px;
        background: #ffffff;
        color: #111827;
        outline: none;
        box-sizing: border-box;
      }
      .bp-proxy-input:disabled, .bp-proxy-select:disabled{
        background: #f9fafb;
        color: #6b7280;
      }

      .bp-proxy-btn{
        width: fit-content;
        border-radius: 10px;
        border: 1px solid #e5e7eb;
        background: #ffffff;
        padding: 8px 12px;
        font-size: 13px;
        cursor: default;
        color: #111827;
      }
      .bp-proxy-btn:disabled{ background: #f9fafb; color: #6b7280; }

      .bp-proxy-card{
        border: 1px solid #e5e7eb;
        background: #f9fafb;
        border-radius: 12px;
        padding: 10px 12px;
      }
      .bp-proxy-card-title{ font-weight: 800; font-size: 13px; color: #111827; margin-bottom: 6px; }
      .bp-proxy-card-text{ font-size: 12px; color: #6b7280; line-height: 1.4; }

      .bp-proxy-table{
        width: 100%;
        border-collapse: collapse;
        border-radius: 12px;
        overflow: hidden;
        border: 1px solid #e5e7eb;
        background: #ffffff;
      }
      .bp-proxy-table th, .bp-proxy-table td{
        border-bottom: 1px solid #e5e7eb;
        padding: 6px 8px;
        font-size: 12px;
        color: #111827;
        text-align: left;
        white-space: nowrap;
      }
      .bp-proxy-table th{ background: #f8fafc; color: #334155; font-weight: 800; }
      .bp-proxy-table tr:last-child td{ border-bottom: none; }

      .bp-proxy-label{
          font-size: var(--bp-font, 14px);
          font-weight: 700;
          color: #334155;
          line-height: 1.2;
          word-break: break-word;  }

      .bp-extra{
        border: 1px solid #e5e7eb;
        border-radius: 12px;
        padding: 10px;
        background: #ffffff;
      }

      @media (max-width: 1400px){
        .bp-grid{ grid-template-columns: 280px 1fr 360px; }
      }
      @media (max-width: 1200px){
        .bp-grid{
          grid-template-columns: 1fr;
          grid-template-rows: auto 60vh auto;
        }
      }
    </style>
    """)

    ui.add_body_html(f"""
    <script>
      window.__PROJECT_ID__ = {project_id};
    </script>
    """)

    ui.add_body_html(r"""
    <script>
    (function(){
      if (window.__BP_DESIGNER_INITED__) return;
      window.__BP_DESIGNER_INITED__ = true;

      const PROJECT_ID = window.__PROJECT_ID__ || 1;

      const state = {
        project: String(PROJECT_ID),
        screens: [],
        currentScreenId: null,
        selectedId: null,
        entities: [],
      };

      const typeDefaults = {
        Button:   { label: '按鈕', text: 'Button' },
        Input:    { label: '輸入欄位', placeholder: '請輸入...' },
        Table:    { label: '表格', columns: 'colA,colB,colC' },
        Card:     { label: '卡片', title: 'Card Title' },
        Dropdown: { label: '下拉選單', options: 'A,B,C' },
        Label:    { label: '文字' },
        Image:    { label: '圖片', src: 'https://via.placeholder.com/300x180' },
        Checkbox: { label: '核取方塊', text: 'Option' },
        Radio:    { label: '單選', options: 'A,B,C' },
        Tabs:     { label: '頁籤', tabs: 'Tab1,Tab2,Tab3' },
      };

      function uid(){ return 'c_' + Math.random().toString(16).slice(2,8) + '_' + Date.now().toString(16).slice(-4); }
      function $(id){ return document.getElementById(id); }
      function escapeHtml(s){
        return (s ?? '').toString()
          .replaceAll('&','&amp;')
          .replaceAll('<','&lt;')
          .replaceAll('>','&gt;')
          .replaceAll('"','&quot;')
          .replaceAll("'","&#39;");
      }
      function parseCSV(s){ return (s || '').split(',').map(x=>x.trim()).filter(Boolean); }
      function joinCSV(arr){ return (arr || []).map(x=>x.trim()).filter(Boolean).join(','); }
      function ensureProps(comp){ comp.props = comp.props || {}; return comp.props; }

      function getScreen(){
        return state.screens.find(s => s.id === state.currentScreenId) || state.screens[0];
      }
      function getComponents(){ return (getScreen() ? getScreen().components : []); }
      function findComp(id){ return getComponents().find(x => x.id === id); }

      function sanitizeName(s){
        const raw = (s ?? '').toString().trim();
        if(!raw) return '';
        let t = raw.replaceAll(/[^A-Za-z0-9_]/g, '_');
        if(/^[0-9]/.test(t)) t = '_' + t;
        return t;
      }
      function isNameUnique(name, selfId){
        const n = (name ?? '').toString().trim();
        if(!n) return false;
        return !getComponents().some(c => c.id !== selfId && (c.name || '') === n);
      }

      function getEntityByName(name){
        if(!name) return null;
        return state.entities.find(e => e.name === name) || null;
      }

      function setSelectOptions(selectEl, options, currentValue){
        if(!selectEl) return;
        selectEl.innerHTML = '';
        const optEmpty = document.createElement('option');
        optEmpty.value = '';
        optEmpty.textContent = '— 請選擇 —';
        selectEl.appendChild(optEmpty);

        (options || []).forEach(v => {
          const opt = document.createElement('option');
          opt.value = v;
          opt.textContent = v;
          if(v === currentValue) opt.selected = true;
          selectEl.appendChild(opt);
        });
      }

      function renderEntityDropdowns(comp){
        const selTable = $('bp_ins_table');
        const selField = $('bp_ins_fields');
        if(!selTable || !selField) return;

        const entityNames = (state.entities || []).map(e => e.name);
        const currentTable = comp ? (comp.data_table || '') : (selTable.value || '');
        setSelectOptions(selTable, entityNames, currentTable);

        const tableName = comp ? (comp.data_table || '') : (selTable.value || '');
        const ent = getEntityByName(tableName);
        const fields = ent ? (ent.fields || []) : [];

        const currentField = comp ? (comp.data_fields || '') : (selField.value || '');
        setSelectOptions(selField, fields, currentField);
      }

      function buildProxyBody(comp){
        const t = comp.type;
        const p = comp.props || {};

        if(t === 'Input'){
          const ph = escapeHtml(p.placeholder || '請輸入...');
          return `<div class="bp-proxy-body"><input class="bp-proxy-input" disabled placeholder="${ph}"></div>`;
        }
        if(t === 'Button'){
          const text = escapeHtml(p.text || 'Button');
          return `<div class="bp-proxy-body"><button class="bp-proxy-btn" disabled>${text}</button></div>`;
        }
        if(t === 'Dropdown'){
          const opts = (p.options || 'A,B,C').split(',').map(x => x.trim()).filter(Boolean);
          const optionsHtml = opts.slice(0, 6).map(o => `<option>${escapeHtml(o)}</option>`).join('');
          return `<div class="bp-proxy-body"><select class="bp-proxy-select" disabled>${optionsHtml || '<option>A</option>'}</select></div>`;
        }
        if(t === 'Table'){
          const cols = (p.columns || 'colA,colB,colC').split(',').map(x => x.trim()).filter(Boolean);
          const head = cols.slice(0, 4).map(c => `<th>${escapeHtml(c)}</th>`).join('');
          const row = cols.slice(0, 4).map(() => `<td>...</td>`).join('');
          return `
            <div class="bp-proxy-body">
              <table class="bp-proxy-table">
                <thead><tr>${head || '<th>colA</th><th>colB</th>'}</tr></thead>
                <tbody>
                  <tr>${row || '<td>...</td><td>...</td>'}</tr>
                  <tr>${row || '<td>...</td><td>...</td>'}</tr>
                </tbody>
              </table>
            </div>
          `;
        }
        if(t === 'Card'){
          const title = escapeHtml(p.title || 'Card Title');
          return `
            <div class="bp-proxy-body">
              <div class="bp-proxy-card">
                <div class="bp-proxy-card-title">${title}</div>
                <div class="bp-proxy-card-text">這是一個容器（示意）。</div>
              </div>
            </div>
          `;
        }
        if(t === 'Label'){
          const label = escapeHtml((comp.props && comp.props.label) ? comp.props.label : '文字');
          return `<div class="bp-proxy-body"><div class="bp-proxy-label">${label || '文字'}</div></div>`;
        }
        if(t === 'Image'){
          const src = escapeHtml(p.src || 'https://via.placeholder.com/300x180');
          return `<div class="bp-proxy-body"><img src="${src}" style="width:100%;height:100%;object-fit:contain;border-radius:8px;display:block;" /></div>`;
        }
        if(t === 'Checkbox'){
          const text = escapeHtml(p.text || 'Option');
          return `<div class="bp-proxy-body"><label style="display:flex;gap:8px;align-items:center;"><input type="checkbox" disabled /><span>${text}</span></label></div>`;
        }
        if(t === 'Radio'){
          const opts = (p.options || 'A,B,C').split(',').map(x=>x.trim()).filter(Boolean);
          return `<div class="bp-proxy-body" style="gap:6px;">${
            opts.map(o=>`<label style="display:flex;gap:8px;align-items:center;"><input type="radio" disabled /><span>${escapeHtml(o)}</span></label>`).join('')
          }</div>`;
        }
        if(t === 'Tabs'){
          const tabs = (p.tabs || 'Tab1,Tab2').split(',').map(x=>x.trim()).filter(Boolean);
          return `
            <div class="bp-proxy-body">
              <div style="display:flex;gap:6px;border-bottom:1px solid #e5e7eb;">
                ${tabs.map(tt=>`<div style="padding:6px 10px;font-weight:700;color:#374151;">${escapeHtml(tt)}</div>`).join('')}
              </div>
              <div style="padding:8px;color:#6b7280;font-size:12px;">Tab Content（示意）</div>
            </div>
          `;
        }
        return `<div class="bp-proxy-body"></div>`;
      }

      function clearSelection(){
        state.selectedId = null;
        document.querySelectorAll('.bp-comp').forEach(el => el.classList.remove('selected'));
        renderInspector();
        renderComponentList();
      }
      function selectComp(id){
        state.selectedId = id;
        document.querySelectorAll('.bp-comp').forEach(el => el.classList.toggle('selected', el.dataset.id === id));
        renderInspector();
        renderComponentList();
      }

      function attachInteract(el){
        if(!window.interact) return;

        interact(el).draggable({
          listeners: {
            move (event) {
              const t = event.target;
              const x = (parseFloat(t.getAttribute('data-x')) || 0) + event.dx;
              const y = (parseFloat(t.getAttribute('data-y')) || 0) + event.dy;
              t.style.transform = `translate(${x}px, ${y}px)`;
              t.setAttribute('data-x', x);
              t.setAttribute('data-y', y);
            },
            end (event) {
              const t = event.target;
              const c = findComp(t.dataset.id); if(!c) return;
              const tx = parseFloat(t.getAttribute('data-x')) || 0;
              const ty = parseFloat(t.getAttribute('data-y')) || 0;

              c.layout.x = Math.round((parseFloat(t.style.left)||0) + tx);
              c.layout.y = Math.round((parseFloat(t.style.top)||0)  + ty);

              t.style.left = c.layout.x + 'px';
              t.style.top  = c.layout.y + 'px';
              t.style.transform = 'translate(0px,0px)';
              t.setAttribute('data-x', 0); t.setAttribute('data-y', 0);
            }
          }
        });

        interact(el).resizable({
          edges: { left: true, right: true, bottom: true, top: true },
          listeners: {
            move (event) {
              const t = event.target;
              let x = (parseFloat(t.getAttribute('data-x')) || 0);
              let y = (parseFloat(t.getAttribute('data-y')) || 0);

              t.style.width  = event.rect.width + 'px';
              t.style.height = event.rect.height + 'px';

              const c = findComp(t.dataset.id);
              if (c && c.type === 'Label') {
                const w = event.rect.width || 0;
                const h = event.rect.height || 0;
                const fs = Math.max(10, Math.min(72, Math.round(Math.min(w, h) * 0.35)));
                t.style.setProperty('--bp-font', fs + 'px');
              }

              x += event.deltaRect.left;
              y += event.deltaRect.top;

              t.style.transform = `translate(${x}px, ${y}px)`;
              t.setAttribute('data-x', x);
              t.setAttribute('data-y', y);
            },
            end (event) {
              const t = event.target;
              const c = findComp(t.dataset.id); if(!c) return;
              if (c.type === 'Label') {
                const computed = getComputedStyle(t).getPropertyValue('--bp-font').trim();
                if (computed) {
                  c.props = c.props || {};
                  c.props.fontSize = computed;
                }
              }
              const tx = parseFloat(t.getAttribute('data-x')) || 0;
              const ty = parseFloat(t.getAttribute('data-y')) || 0;

              c.layout.w = Math.round(parseFloat(t.style.width)  || 0);
              c.layout.h = Math.round(parseFloat(t.style.height) || 0);
              c.layout.x = Math.round((parseFloat(t.style.left)||0) + tx);
              c.layout.y = Math.round((parseFloat(t.style.top)||0)  + ty);

              t.style.left = c.layout.x + 'px';
              t.style.top  = c.layout.y + 'px';
              t.style.transform = 'translate(0px,0px)';
              t.setAttribute('data-x', 0); t.setAttribute('data-y', 0);
            }
          }
        });
      }

      function createComponent(type, x, y){
        const id = uid();
        const d = typeDefaults[type] || { label: type };

        const comp = {
          id,
          type,
          name: '',
          function: '',
          data_table: '',
          data_fields: '',
          props: { ...d },
          layout: { x: Math.max(0, x), y: Math.max(0, y), w: 260, h: 120 },
        };

        if(type === 'Label'){ comp.layout.w = 220; comp.layout.h = 90; }
        if(type === 'Image'){ comp.layout.w = 320; comp.layout.h = 200; }

        getComponents().push(comp);
        renderCanvas();
        selectComp(id);
      }

      function rerenderSelectedProxy(){
        const c = state.selectedId ? findComp(state.selectedId) : null;
        if(!c) return;
        const el = document.querySelector(`.bp-comp[data-id="${c.id}"]`);
        if(!el) return;
        el.innerHTML = `<div class="bp-proxy-only">${buildProxyBody(c)}</div>`;
      }

      function updateSelectedField(key, value){
        const c = state.selectedId ? findComp(state.selectedId) : null;
        if(!c) return;

        if(key === 'name'){
          const fixed = sanitizeName(value);
          c.name = fixed;
          const warn = $('bp_ins_name_warn');
          if(warn){
            if(!fixed){ warn.textContent = 'Name 不可空'; warn.style.display='block'; }
            else if(!isNameUnique(fixed, c.id)){ warn.textContent='Name 重複（請改成唯一）'; warn.style.display='block'; }
            else{ warn.textContent=''; warn.style.display='none'; }
          }
          renderComponentList();
          return;
        }

        if(key === 'label'){
          c.props = c.props || {};
          c.props.label = value;
          rerenderSelectedProxy();
          renderComponentList();
          return;
        }
        if(key === 'function'){ c.function = value; renderComponentList(); return; }
        if(key === 'data_table'){ c.data_table = value || '';c.data_fields = ''; renderInspector(); renderComponentList(); return; }
        if(key === 'data_fields'){ c.data_fields = value || ''; renderComponentList(); return; }

        c.props = c.props || {};
        c.props[key] = value;
        rerenderSelectedProxy();
        renderComponentList();

        const skipInspector = (
          (c.type === 'Checkbox' && key === 'text') ||
          ((c.type === 'Radio' || c.type === 'Dropdown') && key === 'options') ||
          (c.type === 'Tabs' && key === 'tabs') ||
          (c.type === 'Table' && key === 'columns')
        );
        if(!skipInspector){
          renderInspector();
        }
      }

      function deleteSelected(){
        const id = state.selectedId;
        if(!id) return;
        const s = getScreen();
        s.components = s.components.filter(x => x.id !== id);
        state.selectedId = null;
        renderCanvas(); renderInspector(); renderComponentList();
      }

      function renderScreenSelect(){
        const sel = $('bp_screen_select');
        if(!sel) return;

        sel.innerHTML = '';
        (state.screens || []).forEach(s => {
          const opt = document.createElement('option');
          opt.value = s.id;
          const suffix = s.count ? `〔${s.count}〕` : '';
          opt.textContent = `${s.name}${suffix}`;
          if(s.id === state.currentScreenId) opt.selected = true;
          sel.appendChild(opt);
        });

        sel.onchange = async (e) => {
          await switchScreen(e.target.value);
        };
      }
                     
      async function captureCanvasJpgBase64(){
        const el = document.getElementById('bp_canvas');      
        if(!el || !window.html2canvas) return '';

        const canvas = await html2canvas(el, {                                                
          backgroundColor: '#ffffff',
          scale: 2,
          useCORS: true,
        });
                     
        return canvas.toDataURL('image/jpeg', 0.8);
      }
      async function saveCurrentScreenToApi(){
        const screen = state.screens.find(s => s.id === state.currentScreenId);
        if(!screen) return;

        const payload = {
          project: state.project,
          group_key: screen.group_key,
           screen: {
            id: screen.id,
            name: screen.name,
            group_key: screen.group_key,
            components: screen.components,
          },
        };

        const jpgDataUrl = await captureCanvasJpgBase64();
                                  
        const res = await fetch('/api/blueprint/save', {
          method: 'POST',
          headers: {'Content-Type':'application/json'},
          body: JSON.stringify({
            project_id: Number(PROJECT_ID),
            group_key: screen.group_key,
            payload,
            canvas_jpg_base64: jpgDataUrl,
          }),
        });
        if(!res.ok) throw new Error(await res.text());
      
        const out = await res.json();            
        return out; // {ok, project_id, group_key, canonical_boundary_id, ref}             
      }

      async function manualSave(){               
        try{
          const out = await saveCurrentScreenToApi();
          alert(`✅ 已儲存：group=${out.group_key}`);
        }catch(e){
          console.error('save failed:', e);
          alert('儲存失敗，請看 console');
        }
      }

      window.bp = {
        clearSelection,
        deleteSelected,
        updateSelectedField,
        save: manualSave,           
        state
      };                                                                                                                      
      async function loadBlueprintForCurrentScreen(){
        const screen = state.screens.find(s => s.id === state.currentScreenId);
        if(!screen) return;

        const res = await fetch(`/api/blueprint/load?project_id=${encodeURIComponent(PROJECT_ID)}&group_key=${encodeURIComponent(screen.group_key)}`);
        if(!res.ok) throw new Error(await res.text());
        
        const data = await res.json();
        const payload = data.payload || {};
        const s = payload.screen || null;             

        if(s && typeof s === 'object'){
          screen.components = Array.isArray(s.components) ? s.components : [];       
          if (s.name) screen.name = s.name;
        } else {
          state.selectedId = [];    
        }      
                     
        state.selectedId = null;
      }                                                                           
      async function switchScreen(id){
        if(id === state.currentScreenId) return;

        state.currentScreenId = id;
        state.selectedId = null;

        const screen = state.screens.find(s => s.id === state.currentScreenId);
                       
        try{
             await loadBlueprintForCurrentScreen(); 
        }catch(e){
          console.error('load blueprint failed:', e);
          alert('載入畫面 blueprint 失敗，請看 console');      
        }
                     
        try{
          if (screen) await loadEntitiesFromApi(screen.group_key);            
        }catch(e){
          console.error('load entities failed:', e);
          alert('載入 Entity/Attributes 失敗，請看 console');
         }
                     
        renderScreenSelect();
        renderCanvas();
        renderInspector();
        renderComponentList();
      }

      async function loadBoundariesFromApi(){
        const res = await fetch(`/api/blueprint/boundary_groups?project_id=${encodeURIComponent(PROJECT_ID)}`);
        if(!res.ok) throw new Error(await res.text());
        const groups = await res.json();    

        state.screens = groups.map(g => ({
          id: `g_${g.group_key}`,
          name: g.name,
          group_key: g.group_key,
          count: g.count ,
          components: [],
        }));

        if(state.screens.length){
          state.currentScreenId = state.screens[0].id;
          await loadBlueprintForCurrentScreen();
                     
          const s = state.screens.find(x => x.id === state.currentScreenId);
          if (s) await loadEntitiesFromApi(s.group_key);           
        }else{
          state.currentScreenId = null;
        }

        renderScreenSelect();
      }

      async function loadEntitiesFromApi(groupKey){
        const res = await fetch(`/api/blueprint/entities?project_id=${encodeURIComponent(PROJECT_ID)}&group_key=${encodeURIComponent(groupKey)}`);
        if(!res.ok) throw new Error(await res.text());
        const rows = await res.json(); // [{id,name,fields:[...]}]

        state.entities = (rows || []).map(r => ({
          name: r.name,           
          fields: Array.isArray(r.fields) ? r.fields : [],
        }));
      }

      function renderCanvas(){
        const canvas = $('bp_canvas');
        if(!canvas) return;
        canvas.innerHTML = '<div class="bp-drop-hint">把 View 元件拖到這裡（Canvas）</div>';

        getComponents().forEach(comp => {
          const el = document.createElement('div');
          el.className = 'bp-comp';
          el.dataset.id = comp.id;

          el.style.left = (comp.layout?.x ?? 0) + 'px';
          el.style.top  = (comp.layout?.y ?? 0) + 'px';
          el.style.width  = (comp.layout?.w ?? 260) + 'px';
          el.style.height = (comp.layout?.h ?? 120) + 'px';

          if (comp.type === 'Label') {
            const fs = (comp.props && comp.props.fontSize) ? comp.props.fontSize : '';
            if (fs) el.style.setProperty('--bp-font', fs);
            else el.style.removeProperty('--bp-font');
          }

          el.innerHTML = `<div class="bp-proxy-only">${buildProxyBody(comp)}</div>`;
          el.addEventListener('mousedown', (e)=>{ e.stopPropagation(); selectComp(comp.id); });

          canvas.appendChild(el);
          attachInteract(el);
        });
      }

      function renderComponentList(){
        const wrap = $('bp_comp_list');
        if(!wrap) return;

        wrap.innerHTML = '';
        const comps = getComponents();

        if(comps.length === 0){
          const empty = document.createElement('div');
          empty.style.opacity = '.6';
          empty.style.padding = '10px';
          empty.textContent = '目前尚未放置任何元件';
          wrap.appendChild(empty);
          return;
        }

        comps.forEach((c, idx) => {
          const item = document.createElement('div');
          item.className = 'bp-comp-item type-' + c.type + (c.id === state.selectedId ? ' active' : '');
          item.onclick = () => selectComp(c.id);

          const name = c.name ? c.name : '(未命名)';
          const bindData = (c.data_table || c.data_fields)
            ? `${c.data_table || ''}${(c.data_table && c.data_fields) ? '.' : ''}${c.data_fields || ''}`
            : '';
          const func = c.function || '';

          item.innerHTML = `
            <div class="bp-dot"></div>
            <div class="bp-comp-main">
              <div class="bp-comp-line1">
                <span class="bp-pill">${idx+1}</span>
                <span class="bp-comp-name">${escapeHtml(c.type)} · ${escapeHtml(name)}</span>
              </div>
              <div class="bp-comp-line2">
                ${bindData ? `<span class="bp-kv">資料：${escapeHtml(bindData)}</span>` : ``}
                ${func ? `<span class="bp-kv">功能：${escapeHtml(func)}</span>` : ``}
              </div>
            </div>
          `;
          wrap.appendChild(item);
        });
      }

      function renderExtraInspector(comp){
        const wrap = $('bp_ins_extra');
        if(!wrap) return;
        wrap.innerHTML = '';

        if(!comp){
          wrap.innerHTML = `<div style="opacity:.6;font-size:12px;">先在畫布點選一個元件，才會顯示設定。</div>`;
          return;
        }

        const p = ensureProps(comp);

        // ========== Checkbox：編輯顯示文字 ==========
        if(comp.type === 'Checkbox'){
          const text = p.text || 'Option';
          wrap.innerHTML = `
            <div style="font-weight:800;margin-bottom:6px;">Checkbox</div>
            <div style="font-size:12px;opacity:.7;margin-bottom:8px;">可編輯選擇名稱（顯示文字）</div>
            <input id="bp_ex_checkbox_text" class="bp-small-input" placeholder="例：同意條款" value="${escapeHtml(text)}">
          `;
          $('bp_ex_checkbox_text').addEventListener('input', e=>{
            updateSelectedField('text', e.target.value);
          });
          return;
        }

        // ========== Radio / Dropdown：選項（可新增/刪除/改名）==========
        if(comp.type === 'Radio' || comp.type === 'Dropdown'){
          const key = 'options';
          let items = parseCSV(p[key] || 'A,B,C');

          wrap.innerHTML = `
            <div style="font-weight:800;margin-bottom:6px;">${escapeHtml(comp.type)} 選項</div>
            <div style="font-size:12px;opacity:.7;">新增 / 刪除 / 改名選項</div>

            <div class="bp-inline">
              <input id="bp_ex_add_item" class="bp-small-input" style="flex:1;min-width:160px;" placeholder="新增一個項目，例如：VIP">
              <button id="bp_ex_add_btn" class="bp-mini-btn">新增</button>
            </div>

            <div id="bp_ex_list" style="margin-top:10px;display:grid;gap:8px;"></div>
          `;

          const sync = ()=>{
            // 去除空字、trim
            items = (items || []).map(x => (x || '').trim()).filter(Boolean);
            updateSelectedField(key, joinCSV(items));
          };

          const renderList = ()=>{
            const list = $('bp_ex_list');
            if(!list) return;

            if(!items.length){
              list.innerHTML = `<div style="opacity:.6;font-size:12px;">目前沒有選項</div>`;
              return;
            }

            list.innerHTML = items.map((v, idx)=>`
              <div style="display:grid;grid-template-columns: 1fr auto;gap:8px;align-items:center;">
                <input class="bp-small-input" data-idx="${idx}" value="${escapeHtml(v)}">
                <button class="bp-mini-btn" data-del="${idx}">刪除</button>
              </div>
            `).join('');

            // rename
            list.querySelectorAll('input[data-idx]').forEach(inp=>{
              inp.addEventListener('input', (e)=>{
                const i = Number(e.target.getAttribute('data-idx'));
                items[i] = e.target.value;
                sync(); // 不重繪 inspector（updateSelectedField 會處理）
              });
            });

            // delete
            list.querySelectorAll('button[data-del]').forEach(btn=>{
              btn.onclick = ()=>{
                const i = Number(btn.getAttribute('data-del'));
                items.splice(i, 1);
                sync();
                renderList();
              };
            });
          };

          $('bp_ex_add_btn').onclick = ()=>{
            const add = ($('bp_ex_add_item').value || '').trim();
            if(!add) return;
            items.push(add);
            $('bp_ex_add_item').value = '';
            sync();
            renderList();
          };

          renderList();
          return;
        }

        // ========== Tabs：頁籤（可新增/刪除/改名）==========
        if(comp.type === 'Tabs'){
          const key = 'tabs';
          let items = parseCSV(p[key] || 'Tab1,Tab2,Tab3');

          wrap.innerHTML = `
            <div style="font-weight:800;margin-bottom:6px;">Tabs 頁籤</div>
            <div style="font-size:12px;opacity:.7;">新增 / 刪除 / 改名頁籤</div>

            <div class="bp-inline">
              <input id="bp_ex_add_item" class="bp-small-input" style="flex:1;min-width:160px;" placeholder="新增一個頁籤，例如：基本資料">
              <button id="bp_ex_add_btn" class="bp-mini-btn">新增</button>
            </div>

            <div id="bp_ex_list" style="margin-top:10px;display:grid;gap:8px;"></div>
          `;

          const sync = ()=>{
            items = (items || []).map(x => (x || '').trim()).filter(Boolean);
            updateSelectedField(key, joinCSV(items));
          };

          const renderList = ()=>{
            const list = $('bp_ex_list');
            if(!list) return;

            if(!items.length){
              list.innerHTML = `<div style="opacity:.6;font-size:12px;">目前沒有頁籤</div>`;
              return;
            }

            list.innerHTML = items.map((v, idx)=>`
              <div style="display:grid;grid-template-columns: 1fr auto;gap:8px;align-items:center;">
                <input class="bp-small-input" data-idx="${idx}" value="${escapeHtml(v)}">
                <button class="bp-mini-btn" data-del="${idx}">刪除</button>
              </div>
            `).join('');

            list.querySelectorAll('input[data-idx]').forEach(inp=>{
              inp.addEventListener('input', (e)=>{
                const i = Number(e.target.getAttribute('data-idx'));
                items[i] = e.target.value;
                sync();
              });
            });

            list.querySelectorAll('button[data-del]').forEach(btn=>{
              btn.onclick = ()=>{
                const i = Number(btn.getAttribute('data-del'));
                items.splice(i, 1);
                sync();
                renderList();
              };
            });
          };

          $('bp_ex_add_btn').onclick = ()=>{
            const add = ($('bp_ex_add_item').value || '').trim();
            if(!add) return;
            items.push(add);
            $('bp_ex_add_item').value = '';
            sync();
            renderList();
          };

          renderList();
          return;
        }

        // ========== Table：欄位（可新增/刪除/改名）==========
        if(comp.type === 'Table'){
          const key = 'columns';
          let cols = parseCSV(p[key] || 'colA,colB,colC');

          const ent = getEntityByName(comp.data_table);
          const fields = ent ? (ent.fields || []) : [];

          wrap.innerHTML = `
            <div style="font-weight:800;margin-bottom:6px;">Table 欄位</div>
            <div style="font-size:12px;opacity:.7;">新增 / 刪除 / 改名欄位（會同步更新 columns）</div>

            ${fields.length ? `
            <div class="bp-inline" style="margin-top:8px;">
              <select id="bp_ex_field_pick" class="bp-small-input" style="flex:1;min-width:160px;">
                <option value="">— 從資料表欄位加入 —</option>
                ${fields.map(f=>`<option value="${escapeHtml(f)}">${escapeHtml(f)}</option>`).join('')}
              </select>
              <button id="bp_ex_field_add" class="bp-mini-btn">加入</button>
            </div>
            ` : ''}

            <div class="bp-inline" style="margin-top:8px;">
              <input id="bp_ex_add_col" class="bp-small-input" style="flex:1;min-width:160px;" placeholder="新增一個欄位，例如：TotalDue">
              <button id="bp_ex_add_btn" class="bp-mini-btn">新增</button>
            </div>

            <div id="bp_ex_list" style="margin-top:10px;display:grid;gap:8px;"></div>

            <div style="margin-top:10px;font-size:12px;opacity:.7;">columns（逗號分隔，系統欄位）</div>
            <input id="bp_ex_cols_raw" class="bp-small-input" value="${escapeHtml(joinCSV(cols))}">
          `;

          const sync = ()=>{
            cols = (cols || []).map(x => (x || '').trim()).filter(Boolean);
            // raw 同步
            const raw = $('bp_ex_cols_raw');
            if(raw) raw.value = joinCSV(cols);
            updateSelectedField(key, joinCSV(cols));
          };

          const renderList = ()=>{
            const list = $('bp_ex_list');
            if(!list) return;

            if(!cols.length){
              list.innerHTML = `<div style="opacity:.6;font-size:12px;">目前沒有欄位</div>`;
              return;
            }

            list.innerHTML = cols.map((v, idx)=>`
              <div style="display:grid;grid-template-columns: 1fr auto;gap:8px;align-items:center;">
                <input class="bp-small-input" data-idx="${idx}" value="${escapeHtml(v)}">
                <button class="bp-mini-btn" data-del="${idx}">刪除</button>
              </div>
            `).join('');

            list.querySelectorAll('input[data-idx]').forEach(inp=>{
              inp.addEventListener('input', (e)=>{
                const i = Number(e.target.getAttribute('data-idx'));
                cols[i] = e.target.value;
                sync();
              });
            });

            list.querySelectorAll('button[data-del]').forEach(btn=>{
              btn.onclick = ()=>{
                const i = Number(btn.getAttribute('data-del'));
                cols.splice(i, 1);
                sync();
                renderList();
              };
            });
          };

          // from fields
          const fieldAddBtn = $('bp_ex_field_add');
          if(fieldAddBtn){
            fieldAddBtn.onclick = ()=>{
              const v = ($('bp_ex_field_pick').value || '').trim();
              if(!v) return;
              cols.push(v);
              $('bp_ex_field_pick').value = '';
              sync();
              renderList();
            };
          }

          $('bp_ex_add_btn').onclick = ()=>{
            const add = ($('bp_ex_add_col').value || '').trim();
            if(!add) return;
            cols.push(add);
            $('bp_ex_add_col').value = '';
            sync();
            renderList();
          };

          $('bp_ex_cols_raw').addEventListener('input', (e)=>{
            cols = parseCSV(e.target.value);
            sync();
            renderList();
          });

          renderList();
          return;
        }

        wrap.innerHTML = `<div style="opacity:.6;font-size:12px;">此元件目前沒有專屬設定。</div>`;
      }

      function renderInspector(){
        const comp = state.selectedId ? findComp(state.selectedId) : null;

        $('bp_ins_type').value = comp ? comp.type : '';
        $('bp_ins_id').value = comp ? comp.id : '';
        $('bp_ins_name').value = comp ? (comp.name || '') : '';
        $('bp_ins_label').value = comp ? ((comp.props && comp.props.label) ? comp.props.label : '') : '';
        $('bp_ins_func').value = comp ? (comp.function || '') : '';

        const disabled = !comp;
        $('bp_ins_table').disabled = disabled;
        $('bp_ins_fields').disabled = disabled;      
                         
        renderEntityDropdowns(comp);

        const warn = $('bp_ins_name_warn');
        if(warn){
          if(!comp){ warn.textContent=''; warn.style.display='none'; }
          else if(!comp.name){ warn.textContent='Name 不可空（建議先命名）'; warn.style.display='block'; }
          else if(!isNameUnique(comp.name, comp.id)){ warn.textContent='Name 重複（請改成唯一）'; warn.style.display='block'; }
          else{ warn.textContent=''; warn.style.display='none'; }
        }

        renderExtraInspector(comp);
      }

      function bindCanvasDnDOnce(){
        const canvas = $('bp_canvas');
        if(!canvas) return;
        if (canvas.dataset.boundDnd === '1') return;
        canvas.dataset.boundDnd = '1';

        let dropLock = false;
        let lastDropAt = 0;

        canvas.addEventListener('dragover', (e) => { e.preventDefault(); e.stopPropagation(); });
        canvas.addEventListener('drop', (e) => {
          e.preventDefault(); e.stopPropagation();
          if (e.stopImmediatePropagation) e.stopImmediatePropagation();

          const now = Date.now();
          if (now - lastDropAt < 120) return;
          lastDropAt = now;

          if (dropLock) return;
          dropLock = true;

          try {
            const type = e.dataTransfer.getData('text/plain');
            if (!type) return;
            const rect = canvas.getBoundingClientRect();
            const x = Math.round(e.clientX - rect.left - 10);
            const y = Math.round(e.clientY - rect.top - 10);
            createComponent(type, x, y);
          } finally {
            Promise.resolve().then(() => { dropLock = false; });
          }
        });

        canvas.addEventListener('mousedown', () => clearSelection());
      }

      window.addEventListener('DOMContentLoaded', async () => {
        try{
          await loadBoundariesFromApi();
        }catch(e){
          console.error('init failed:', e);
          alert('初始化 Blueprint 失敗：請看 console（通常是 API 404 或 DB 問題）');
        }

        renderCanvas();
        bindCanvasDnDOnce();
        renderInspector();
        renderComponentList();

        $('bp_ins_name').addEventListener('input', (e)=> updateSelectedField('name', e.target.value));
        $('bp_ins_label').addEventListener('input', (e)=> updateSelectedField('label', e.target.value));
        $('bp_ins_func').addEventListener('input', (e)=> updateSelectedField('function', e.target.value));
        $('bp_ins_table').addEventListener('change', (e)=> updateSelectedField('data_table', e.target.value));
        $('bp_ins_fields').addEventListener('change', (e)=> updateSelectedField('data_fields', e.target.value));
      });
    })();
    </script>
    """)

    with ui.column().classes("w-screen h-screen m-0 p-0"):
        with ui.grid(columns=12).classes("w-full h-full m-0 p-0 gap-4"):
            with ui.card().classes("col-span-2 p-5 bg-white rounded-xl shadow-md h-full min-h-0 overflow-hidden flex flex-col"):
                ui.label("🧭 專案流程").classes("text-lg font-bold mb-3 text-gray-800")

                with ui.stepper(value=7).props("vertical").classes("w-full"):
                    ui.step("專案管理").props("name=1 done")
                    ui.step("專案案例管理").props("name=2 done")
                    ui.step("使用案例明細").props("name=3 done")
                    ui.step("三段式事件列表").props("name=4 done")
                    ui.step("專案物件瀏覽").props("name=5 done")
                    ui.step("UML 圖生成").props("name=6 done")
                    ui.step("介面藍圖").props("name=7")
                    ui.step("產生程式碼").props("name=8")

                ui.separator().classes("my-4")
                with ui.column().classes("gap-2"):
                    ui.button("上一頁（UML 圖生成）", on_click=lambda: ui.navigate.to("/mermaid")).props("outline").classes("w-full")
                    ui.button("下一頁（產生程式碼）", on_click=lambda: ui.navigate.to("/code")).classes("w-full")

            with ui.card().classes("col-span-10 w-full h-full min-h-0 overflow-hidden p-0"):
                ui.html(r"""
                <div class="bp-designer">
                  <div class="bp-grid">

                    <div class="bp-panel">
                      <div class="bp-title">View 元件庫</div>
                      <div class="bp-hint">拖曳元件到畫布，點選後在右側補齊：Name／功能／資料表（Entity）／欄位（Attributes）。</div>

                      <div class="bp-palette">
                        <div class="bp-item" data-type="Button" draggable="true"
                             ondragstart="event.dataTransfer.setData('text/plain','Button')">
                          <div class="bp-item-left"><span>🔘</span><span class="bp-item-name">Button</span><span class="bp-item-desc">（互動）</span></div>
                          <span class="bp-tag Button">Action</span>
                        </div>

                        <div class="bp-item" data-type="Input" draggable="true"
                             ondragstart="event.dataTransfer.setData('text/plain','Input')">
                          <div class="bp-item-left"><span>⌨️</span><span class="bp-item-name">Input</span><span class="bp-item-desc">（輸入）</span></div>
                          <span class="bp-tag Input">Field</span>
                        </div>

                        <div class="bp-item" data-type="Table" draggable="true"
                             ondragstart="event.dataTransfer.setData('text/plain','Table')">
                          <div class="bp-item-left"><span>📋</span><span class="bp-item-name">Table</span><span class="bp-item-desc">（資料）</span></div>
                          <span class="bp-tag Table">Data</span>
                        </div>

                        <div class="bp-item" data-type="Card" draggable="true"
                             ondragstart="event.dataTransfer.setData('text/plain','Card')">
                          <div class="bp-item-left"><span>🗂️</span><span class="bp-item-name">Card</span><span class="bp-item-desc">（容器）</span></div>
                          <span class="bp-tag Card">Container</span>
                        </div>

                        <div class="bp-item" data-type="Dropdown" draggable="true"
                             ondragstart="event.dataTransfer.setData('text/plain','Dropdown')">
                          <div class="bp-item-left"><span>⬇️</span><span class="bp-item-name">Dropdown</span><span class="bp-item-desc">（選擇）</span></div>
                          <span class="bp-tag Dropdown">Select</span>
                        </div>

                        <div class="bp-item" data-type="Label" draggable="true"
                             ondragstart="event.dataTransfer.setData('text/plain','Label')">
                          <div class="bp-item-left"><span>🏷️</span><span class="bp-item-name">Label</span><span class="bp-item-desc">（文字）</span></div>
                          <span class="bp-tag Label">Static</span>
                        </div>

                        <div class="bp-item" data-type="Image" draggable="true"
                             ondragstart="event.dataTransfer.setData('text/plain','Image')">
                          <div class="bp-item-left"><span>🖼️</span><span class="bp-item-name">Image</span><span class="bp-item-desc">（圖片）</span></div>
                          <span class="bp-tag Image">Media</span>
                        </div>

                        <div class="bp-item" data-type="Checkbox" draggable="true"
                             ondragstart="event.dataTransfer.setData('text/plain','Checkbox')">
                          <div class="bp-item-left"><span>☑️</span><span class="bp-item-name">Checkbox</span><span class="bp-item-desc">（核取）</span></div>
                          <span class="bp-tag Checkbox">Input</span>
                        </div>

                        <div class="bp-item" data-type="Radio" draggable="true"
                             ondragstart="event.dataTransfer.setData('text/plain','Radio')">
                          <div class="bp-item-left"><span>🔘</span><span class="bp-item-name">Radio</span><span class="bp-item-desc">（單選）</span></div>
                          <span class="bp-tag Radio">Input</span>
                        </div>

                        <div class="bp-item" data-type="Tabs" draggable="true"
                             ondragstart="event.dataTransfer.setData('text/plain','Tabs')">
                          <div class="bp-item-left"><span>📑</span><span class="bp-item-name">Tabs</span><span class="bp-item-desc">（頁籤）</span></div>
                          <span class="bp-tag Tabs">Layout</span>
                        </div>
                      </div>
                    </div>

                    <div class="bp-mid">
                      <div class="bp-screenbar">
                        <div class="bp-screenbar-label">畫面（Boundary）</div>
                        <select id="bp_screen_select" class="bp-screen-select"></select>
                      </div>

                      <div class="bp-toolbar">
                        <button class="bp-btn" onclick="bp.save()">Save</button>
                        <button class="bp-btn" onclick="bp.clearSelection()">Clear Select</button>
                        <button class="bp-btn" onclick="bp.deleteSelected()">Delete Selected</button>
                      </div>

                      <div id="bp_canvas" class="bp-canvas">
                        <div class="bp-drop-hint">把 View 元件拖到這裡（Canvas）</div>
                      </div>
                    </div>

                    <div class="bp-panel">
                      <div class="bp-title">介面藍圖（Inspector）</div>

                      <div class="bp-row"><div style="opacity:.75;">Type</div><input id="bp_ins_type" readonly></div>
                      <div class="bp-row"><div style="opacity:.75;">ID</div><input id="bp_ins_id" readonly></div>

                      <div class="bp-row">
                        <div style="opacity:.75;">Name</div>
                        <div>
                          <input id="bp_ins_name" placeholder="例：usernameInput（唯一）">
                          <div id="bp_ins_name_warn" style="display:none;margin-top:6px;color:#b91c1c;font-size:12px;"></div>
                        </div>
                      </div>

                      <div class="bp-row"><div style="opacity:.75;">Label</div><input id="bp_ins_label" placeholder="畫面顯示文字"></div>
                      <div class="bp-row"><div style="opacity:.75;">功能</div><input id="bp_ins_func" placeholder="例：Login / SearchOrder"></div>

                      <div class="bp-row">
                        <div style="opacity:.75;">資料表</div>
                        <select id="bp_ins_table"></select>
                      </div>
                      <div class="bp-row">
                        <div style="opacity:.75;">欄位</div>
                        <select id="bp_ins_fields"></select>
                      </div>

                      <div class="bp-subtitle">元件專屬設定</div>
                      <div id="bp_ins_extra" class="bp-extra"></div>

                      <div class="bp-subtitle">畫面元件列表（詳細）</div>
                      <div id="bp_comp_list" class="bp-comp-list"></div>
                    </div>

                  </div>
                </div>
                """).classes("w-full h-full")
