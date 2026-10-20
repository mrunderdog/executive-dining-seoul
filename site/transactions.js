/* Official council expense ledger. Never infer attendance or recommend a venue. */
(() => {
  'use strict';
  const $ = id => document.getElementById(id);
  const size = 50;
  const nf = new Intl.NumberFormat('ko-KR');
  const state = { rows: [], filtered: [], page: 0 };
  const controls = ['query', 'institution', 'dateFrom', 'dateTo', 'sort'];
  const labels = ['거래일', '공개 기관', '집행 명의 · 참석 미확인', '사용처 / 업소', '금액', '집행 목적', '공식 근거'];

  function cell(tr, cls, label, content, secondary = '') {
    const td = document.createElement('td');
    td.className = cls;
    td.dataset.label = label;
    const main = document.createElement('span');
    main.textContent = content == null ? '—' : String(content);
    td.appendChild(main);
    if (secondary) {
      const sub = document.createElement('span');
      sub.className = 'secondary';
      sub.textContent = String(secondary);
      td.appendChild(sub);
    }
    tr.appendChild(td);
    return td;
  }

  function safeOfficialLink(url, label) {
    if (typeof url !== 'string') return null;
    try {
      const parsed = new URL(url);
      if (!['https:', 'http:'].includes(parsed.protocol) || !parsed.hostname || parsed.username || parsed.password) return null;
      const anchor = document.createElement('a');
      anchor.href = parsed.href;
      anchor.target = '_blank';
      anchor.rel = 'noopener noreferrer';
      anchor.textContent = label;
      return anchor;
    } catch (_) {
      return null;
    }
  }

  function render() {
    const from = state.page * size;
    const entries = state.filtered.slice(from, from + size);
    const fragment = document.createDocumentFragment();
    for (const row of entries) {
      const tr = document.createElement('tr');
      cell(tr, 'date', labels[0], row.used_date);
      cell(tr, 'institution', labels[1], row.institution, row.jurisdiction);
      cell(tr, 'role', labels[2], row.role || '미기재');
      cell(tr, 'merchant', labels[3], row.merchant, row.address);
      cell(tr, 'amount', labels[4], nf.format(row.amount) + '원');
      cell(tr, 'purpose', labels[5], row.purpose || '원문 참조');
      const sources = document.createElement('td');
      sources.className = 'source';
      sources.dataset.label = labels[6];
      const links = document.createElement('div');
      links.className = 'source-links';
      const post = safeOfficialLink(row.source_post_url, '게시물 ↗');
      const file = safeOfficialLink(row.source_attachment_url, '첨부 원문 ↗');
      if (post) links.appendChild(post);
      if (file) links.appendChild(file);
      sources.appendChild(links);
      if (row.source_sheet && row.source_row != null) {
        const provenance = document.createElement('span');
        provenance.className = 'secondary';
        provenance.textContent = `${row.source_sheet} · ${row.source_row}행`;
        sources.appendChild(provenance);
      }
      tr.appendChild(sources);
      fragment.appendChild(tr);
    }
    if (!entries.length) {
      const tr = document.createElement('tr');
      const td = document.createElement('td');
      td.colSpan = 7;
      td.className = 'loading';
      td.textContent = state.rows.length ? '검색 조건에 맞는 검증된 거래가 없습니다.' : '공개할 수 있는 검증 자료가 없습니다.';
      tr.appendChild(td);
      fragment.appendChild(tr);
    }
    $('transactionRows').replaceChildren(fragment);
    $('resultCount').textContent = `조회 ${nf.format(state.filtered.length)}건 / 전체 ${nf.format(state.rows.length)}건`;
    $('pageSummary').textContent = entries.length ? `${nf.format(from + 1)}–${nf.format(from + entries.length)} / ${nf.format(state.filtered.length)}건` : '0건';
    $('previous').disabled = state.page === 0;
    $('next').disabled = from + size >= state.filtered.length;
  }

  function applyFilters() {
    const text = $('query').value.normalize('NFKC').trim().toLocaleLowerCase('ko-KR');
    const institution = $('institution').value;
    const start = $('dateFrom').value;
    const end = $('dateTo').value;
    state.filtered = state.rows.filter(row => {
      if (institution && row.institution !== institution) return false;
      if (start && row.used_date < start) return false;
      if (end && row.used_date > end) return false;
      if (!text) return true;
      return [row.institution, row.jurisdiction, row.role, row.merchant, row.address, row.purpose]
        .some(v => String(v || '').normalize('NFKC').toLocaleLowerCase('ko-KR').includes(text));
    });
    const sort = $('sort').value;
    if (sort === 'amount') state.filtered.sort((a, b) => b.amount - a.amount || b.used_date.localeCompare(a.used_date));
    else if (sort === 'oldest') state.filtered.sort((a, b) => a.used_date.localeCompare(b.used_date) || a.row_id.localeCompare(b.row_id));
    else state.filtered.sort((a, b) => b.used_date.localeCompare(a.used_date) || a.row_id.localeCompare(b.row_id));
    state.page = 0;
    render();
  }

  function showError(message) {
    $('resultCount').textContent = '데이터를 불러오지 못했습니다.';
    const td = document.createElement('td');
    td.className = 'loading';
    td.colSpan = 7;
    td.textContent = message;
    const tr = document.createElement('tr');
    tr.appendChild(td);
    $('transactionRows').replaceChildren(tr);
  }

  async function initialize() {
    controls.forEach(id => $(id).addEventListener(id === 'query' ? 'input' : 'change', applyFilters));
    $('reset').addEventListener('click', () => { controls.forEach(id => { $(id).value = id === 'sort' ? 'latest' : ''; }); applyFilters(); });
    $('previous').addEventListener('click', () => { if (state.page > 0) { state.page--; render(); $('ledger').scrollIntoView({ block: 'start' }); } });
    $('next').addEventListener('click', () => { if ((state.page + 1) * size < state.filtered.length) { state.page++; render(); $('ledger').scrollIntoView({ block: 'start' }); } });

    try {
      const response = await fetch('./verified-transactions.json');
      if (!response.ok) throw new Error('HTTP ' + response.status);
      const data = await response.json();
      if (data.qa_policy !== 'full_source_100_percent_date_amount_official_attachment'
          || !Array.isArray(data.rows) || data.verified_row_count !== data.rows.length
          || !Array.isArray(data.sources)) throw new Error('검증 데이터 형식이 유효하지 않습니다.');
      state.rows = data.rows;
      $('verifiedCount').textContent = nf.format(data.verified_row_count);
      $('institutionCount').textContent = nf.format(data.verified_source_count);
      $('amountTotal').textContent = nf.format(data.verified_total_amount) + '원';
      $('heldCount').textContent = nf.format(data.held_source_count);
      $('refreshedAt').textContent = '조회 파일 생성: ' + new Intl.DateTimeFormat('ko-KR', {
        timeZone: 'Asia/Seoul', year: 'numeric', month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit'
      }).format(new Date(data.generated_at)) + ' (KST)';
      const institutions = [...new Set(data.sources.map(s => s.institution))].sort((a, b) => a.localeCompare(b, 'ko'));
      for (const name of institutions) {
        const option = document.createElement('option');
        option.value = name;
        option.textContent = name;
        $('institution').appendChild(option);
      }
      applyFilters();
    } catch (error) {
      showError('공식 자료를 가져오지 못했습니다. 잠시 후 새로고침해 주세요. (' + error.message + ')');
    }
  }

  initialize();
})();
