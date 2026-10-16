/* data_story.js — independent, source-backed below-map report. Bundled by build_site.py. */
(function renderDataStory(){
  'use strict';
  const STORY=__STORY__;
  const root=document.getElementById('dataStory');
  if(!root)return;
  const $=id=>document.getElementById(id);
  const n=value=>Number.isFinite(Number(value))?Number(value).toLocaleString('ko-KR'):'—';
  const safe=text=>String(text??'').replaceAll('&','&amp;').replaceAll('<','&lt;').replaceAll('>','&gt;').replaceAll('"','&quot;').replaceAll("'","&#39;");
  const groups=Array.isArray(STORY.source_groups)?STORY.source_groups:[];
  $('dataStoryGroups').innerHTML=groups.length?groups.map((group,index)=>
    '<article class="data-story-group"><span class="data-story-group-index">'+String(index+1).padStart(2,'0')+'</span>'+
    '<strong>'+safe(group.label)+'</strong>'+
    '<div><b>'+n(group.published_venues)+'</b><span>곳</span></div>'+
    '<small>해당 출처군에서 공개된 식당</small></article>'
  ).join(''):'<p class="data-story-empty">공개 출처군 데이터를 확인할 수 없습니다.</p>';

  const count=STORY.published||{};
  const phases=[
    ['공개 식당',count.venues,'정규화 · 식당 단위 통합'],
    ['주소 표시',count.with_address,'원자료 또는 검증된 주소 보강'],
    ['지도 좌표',count.mapped,'공개 페이지에 배치 가능한 업소'],
    ['기관 교차',count.cross_institution,'두 기관 이상 공개 사용처 신호']
  ];
  $('dataStoryPipeline').innerHTML=phases.map((phase,index)=>
    '<div class="data-story-stage"><span class="data-story-stage-step">'+String(index+1).padStart(2,'0')+'</span>'+
    '<strong>'+n(phase[1])+'<span>곳</span></strong>'+
    '<b>'+safe(phase[0])+'</b><small>'+safe(phase[2])+'</small></div>'
  ).join('');

  const health=STORY.health||{};
  const parsed=new Date(STORY.generated_at_utc);
  const valid=!Number.isNaN(parsed.getTime());
  $('storyLastBuild').textContent=valid?
    parsed.toLocaleString('ko-KR',{timeZone:'Asia/Seoul',year:'numeric',month:'2-digit',day:'2-digit',hour:'2-digit',minute:'2-digit',hour12:false}):
    '확인 불가';
  $('storySources').textContent=n(groups.length)+'개';
  const qa=health.qa_passed;
  $('storyQa').textContent=qa===true?'통과':qa===false?'실패':'미확인';
  $('storyQa').dataset.state=qa===true?'pass':qa===false?'fail':'unknown';
  $('storyQaSub').textContent=health.qa_warning_count===null || health.qa_warning_count===undefined?
    'QA 보고서 없음':'경고 '+n(health.qa_warning_count)+'건';
  $('storyReview').textContent=health.attention_sources===null || health.attention_sources===undefined?
    '미확인':n(health.attention_sources)+'개';
  // A QA diagnosis is not a source refresh failure; never display it as one.
  $('storyFailures').textContent=health.confirmed_refresh_failures===null || health.confirmed_refresh_failures===undefined?
    '미집계':n(health.confirmed_refresh_failures)+'건';
  $('storyFreshness').textContent='최근 공개 거래기록일: '+
    (STORY.latest_disclosed_record_date||'확인 불가')+
    ' · 사이트 생성 시각은 원천자료 갱신 시각이나 Pages 배포 완료 시각을 의미하지 않습니다. '+
    '점검 필요 수치는 수도권 의회 출처 진단 범위만 포함합니다.';
})();
