import {drawRadar} from './radar.js?v=0.1.3';

// 页面仅保存当前批次；业务资料和画像从 Python 接口获取。
const state = {files: [], candidates: [], filter: 'all', activeId: null, busy: false};
const $ = id => document.getElementById(id);
const emptyDetailMarkup = $('detailPanel').innerHTML;
const escapeHtml = (value = '') => String(value).replace(/[&<>"']/g,
  c => ({'&':'&amp;', '<':'&lt;', '>':'&gt;', '"':'&quot;', "'":'&#39;'}[c]));

function showToast(message) {
  $('toast').textContent = message;
  $('toast').hidden = false;
  clearTimeout(showToast.timer);
  showToast.timer = setTimeout(() => $('toast').hidden = true, 3500);
}

function showStatus(message, error = false) {
  $('statusBox').hidden = false;
  $('statusBox').textContent = message;
  $('statusBox').style.background = error ? '#fff1f1' : '#edf5ff';
  $('statusBox').style.color = error ? '#a2191f' : '#0043ce';
}

async function request(url, options = {}) {
  const response = await fetch(url, {...options, signal: AbortSignal.timeout(30000)});
  const data = await response.json();
  if (!response.ok) throw new Error(data.detail || `请求失败：${response.status}`);
  return data;
}

function addFiles(files) {
  if (state.busy) return;
  for (const file of files) {
    if (file.name.toLowerCase().endsWith('.doc')) {showToast('旧版 .doc 请另存为 .docx 或 PDF'); continue;}
    if (!/\.(docx|pdf)$/i.test(file.name)) {showToast('请上传 Word（.docx）或 PDF 简历'); continue;}
    if (file.size > 10 * 1024 * 1024) {showToast(`${file.name} 超过 10 MB`); continue;}
    if (state.files.reduce((sum,f) => sum + f.size, 0) + file.size > 20 * 1024 * 1024) {showToast('单批总大小不能超过 20 MB，请分批上传'); continue;}
    if (state.files.length >= 20) {showToast('单批最多上传 20 份简历'); break;}
    state.files.push(file);
  }
  renderQueue();
}

function renderQueue() {
  $('fileCount').textContent = state.files.length;
  $('analyzeBtn').disabled = state.busy || !state.files.length;
  $('clearResultsBtn').disabled = state.busy || !state.candidates.length;
  $('fileQueue').innerHTML = state.files.length ? state.files.map((file, i) =>
    `<div class="file-item"><span title="${escapeHtml(file.name)}">${escapeHtml(file.name)}</span><button data-remove="${i}" ${state.busy ? 'disabled' : ''} title="移除">×</button></div>`
  ).join('') : '';
  if (!state.candidates.length) renderTable();
}

$('clearResultsBtn').addEventListener('click', () => {
  if (state.busy || !state.candidates.length) return;
  state.candidates = [];
  state.activeId = null;
  state.filter = 'all';
  $('searchInput').value = '';
  document.querySelectorAll('.tabs button').forEach(b => b.classList.toggle('active', b.dataset.filter === 'all'));
  $('detailPanel').innerHTML = emptyDetailMarkup;
  $('statusBox').hidden = true;
  $('statusBox').textContent = '';
  $('progressBox').hidden = true;
  renderAll();
  renderQueue();
  showToast('已清空本批结果');
});

$('resumeFiles').addEventListener('change', event => {
  addFiles([...event.target.files]); event.target.value = '';
});
$('fileQueue').addEventListener('click', event => {
  if (state.busy || event.target.dataset.remove === undefined) return;
  state.files.splice(Number(event.target.dataset.remove), 1); renderQueue();
});
for (const name of ['dragenter', 'dragover', 'dragleave', 'drop']) {
  $('dropzone').addEventListener(name, event => {
    event.preventDefault();
    $('dropzone').classList.toggle('dragging', name === 'dragenter' || name === 'dragover');
    if (name === 'drop') addFiles([...event.dataTransfer.files]);
  });
}

function filePayload(file) {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => resolve({filename: file.name, content_base64: reader.result.split(',')[1]});
    reader.onerror = () => reject(new Error(`无法读取 ${file.name}`));
    reader.readAsDataURL(file);
  });
}

$('analyzeBtn').addEventListener('click', async () => {
  if (state.busy || !state.files.length) return;
  const batch = [...state.files];
  state.busy = true;
  renderQueue();
  $('progressBox').hidden = false;
  $('progressText').textContent = `正在处理 ${batch.length} 份简历`;
  $('progressValue').textContent = '处理中';
  $('progressBar').style.width = '40%';
  try {
    const data = await request('/api/analyze/batch', {
      method: 'POST', headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({files: await Promise.all(batch.map(filePayload))}),
    });
    // 同一份内容重复上传只更新原记录，不把人数和平均分重复累计。
    const existing = new Map(state.candidates.map(c => [c.thread_id, c]));
    let updated = 0;
    data.candidates.forEach(c => {if (existing.has(c.thread_id)) updated++; existing.set(c.thread_id, c);});
    state.candidates = [...existing.values()];
    const failedIndexes = new Set(data.failures.map(f => f.index));
    state.files = batch.filter((file, index) => failedIndexes.has(index));
    const failures = data.failures.map(f => `${f.filename}：${f.error}`).join('；');
    showStatus(`完成 ${data.candidates.length} 份资料处理${updated ? `，其中更新 ${updated} 份已有记录` : ''}${data.duplicates ? `，合并 ${data.duplicates} 份重复文件` : ''}${failures ? `；${failures}` : ''}`, !!failures);
    // 上传后清除旧筛选，保证新结果可见。
    state.filter = 'all'; $('searchInput').value = '';
    document.querySelectorAll('.tabs button').forEach(b => b.classList.toggle('active', b.dataset.filter === 'all'));
    renderAll();
    if (data.candidates.length) selectCandidate(data.candidates[0].thread_id);
    $('progressBar').style.width = '100%';
    $('progressText').textContent = '本批资料处理完成';
    $('progressValue').textContent = '完成';
  } catch (error) {
    showStatus(`处理失败：${error.message}。文件仍在列表中，可重试。`, true);
    $('progressBar').style.width = '0';
    $('progressValue').textContent = '未完成';
  } finally {
    state.busy = false;
    renderQueue();
    setTimeout(() => {if (!state.busy) $('progressBox').hidden = true;}, 1500);
  }
});

function filteredCandidates() {
  const query = $('searchInput').value.trim().toLowerCase();
  return state.candidates.filter(c => {
    const category = c.is_qualified === true ? 'qualified' : c.is_qualified === false ? 'rejected' : 'review';
    const text = [c.candidate_name, c.candidate_email, c.parsed_features.education, ...c.parsed_features.skills].join(' ').toLowerCase();
    return (state.filter === 'all' || state.filter === category) && (!query || text.includes(query));
  });
}

function renderAll() {
  const candidates = state.candidates;
  const pass = candidates.filter(c => c.is_qualified === true).length;
  const fail = candidates.filter(c => c.is_qualified === false).length;
  const scored = candidates.filter(c => c.profile_score.fit !== null);
  $('totalMetric').textContent = candidates.length;
  $('qualifiedMetric').textContent = pass;
  $('rejectedMetric').textContent = fail;
  $('averageMetric').textContent = scored.length ? `${Math.round(scored.reduce((s,c) => s + c.profile_score.fit, 0) / scored.length * 100)}%` : '--';
  $('allCount').textContent = candidates.length;
  $('passCount').textContent = pass;
  $('failCount').textContent = fail;
  $('reviewCount').textContent = candidates.length - pass - fail;
  renderTable();
}

function renderTable() {
  const items = filteredCandidates();
  $('candidateRows').innerHTML = items.length ? items.map(c => {
    const score = c.profile_score.fit === null ? null : Math.round(c.profile_score.fit * 100);
    const status = c.is_qualified === true ? ['pass','建议面试'] : c.is_qualified === false ? ['reject','暂不匹配'] : ['review','待人工复核'];
    const f = c.parsed_features;
    return `<tr data-id="${c.thread_id}" class="${state.activeId === c.thread_id ? 'active' : ''}">
      <td><input type="checkbox" disabled aria-label="批量通知未启用"></td>
      <td class="candidate-cell"><strong>${escapeHtml(c.candidate_name)}</strong><span>${escapeHtml(c.candidate_email || '邮箱待补充')}</span><span>${escapeHtml(f.candidate_phone || '手机号待补充')}</span></td>
      <td class="profile-cell"><strong>${escapeHtml(f.education || '学历待补充')} · ${escapeHtml(f.years_experience ?? '-')} 年</strong><span>${escapeHtml(f.skills.slice(0, 3).join(' · ') || '技能待补充')}</span></td>
      <td><span class="score">${score === null ? '--' : score + '%'}</span><div class="score-bar"><i style="width:${score ?? 0}%"></i></div></td>
      <td><span class="badge ${status[0]}">${status[1]}</span></td><td><button class="row-action">查看画像</button></td></tr>`;
  }).join('') : state.candidates.length
    ? '<tr><td colspan="6" class="empty-table"><strong>暂无匹配结果</strong><span>请调整筛选条件</span></td></tr>'
    : `<tr><td colspan="6" class="empty-table"><strong>${state.files.length ? '等待处理简历' : '等待导入简历'}</strong></td></tr>`;
}

function selectCandidate(id) {
  state.activeId = id;
  renderTable();
  const c = state.candidates.find(item => item.thread_id === id);
  if (!c) return;
  const f = c.parsed_features;
  $('detailPanel').innerHTML = `<div class="detail-head"><div class="avatar">${escapeHtml(c.candidate_name.slice(0,1))}</div><div><h3>${escapeHtml(c.candidate_name)}</h3><p>${escapeHtml(c.candidate_email || '邮箱待补充')}</p><p>${escapeHtml(f.candidate_phone || '手机号待补充')}</p></div></div>
    <div class="detail-section"><h4>FDE六项能力雷达图</h4><div class="radar-wrap">${c.profile_score.radar ? '<canvas id="radarCanvas" role="img" aria-label="六项能力画像"></canvas>' : '<div class="radar-empty">尚未建立能力画像<br><small>基本资料已提取，能力分数待补充</small></div>'}</div></div>
    <div class="detail-section"><h4>核心技能</h4><div class="skill-list">${f.skills.map(s => `<span>${escapeHtml(s)}</span>`).join('') || '<span>暂无技能标签</span>'}</div></div>
    <div class="detail-section"><h4>画像摘要</h4><p class="summary">${escapeHtml(c.evaluation_report)}</p></div>
    <div class="detail-actions"><button class="btn ghost" disabled title="当前版本未接入通知服务">发送婉拒</button><button class="btn primary" disabled title="当前版本未接入通知服务">发送面试邀请</button></div>`;
  if (c.profile_score.radar) drawRadar($('radarCanvas'), c.profile_score.radar, c.is_qualified);
}

$('candidateRows').addEventListener('click', event => {
  const row = event.target.closest('tr[data-id]'); if (row) selectCandidate(row.dataset.id);
});
document.querySelectorAll('.tabs button').forEach(button => button.addEventListener('click', () => {
  state.filter = button.dataset.filter;
  document.querySelectorAll('.tabs button').forEach(b => b.classList.toggle('active', b === button));
  renderTable();
}));
$('searchInput').addEventListener('input', renderTable);
window.addEventListener('resize', () => {
  const c = state.candidates.find(c => c.thread_id === state.activeId);
  if (c?.profile_score.radar && $('radarCanvas')) drawRadar($('radarCanvas'), c.profile_score.radar, c.is_qualified);
});

async function checkService() {
  $('checkServiceBtn').disabled = true;
  $('serviceStatus').textContent = '数据服务检测中';
  try {
    const data = await request('/api/health');
    $('serviceStatus').textContent = data.message;
    $('serviceStatus').title = data.detail;
    $('serviceDot').style.background = '#42be65';
  } catch (error) {
    $('serviceStatus').textContent = '数据服务连接失败';
    $('serviceStatus').title = error.message;
    $('serviceDot').style.background = '#fa4d56';
  } finally {$('checkServiceBtn').disabled = false;}
}
$('checkServiceBtn').addEventListener('click', checkService);
checkService();
