import json
from pathlib import Path

p=Path('sources/entity_enrichment.json')
d=json.loads(p.read_text(encoding='utf-8'))
s=d.setdefault('source',{})
updates={
  'public_enterprise|에스서울깍두기전포점': {
    'display':'에스서울깍두기 전포점','address':'부산광역시 부산진구 서전로 49','phone':'051-816-3950','category':'한식 · 곰탕/설렁탕','url':'https://autoreserve.com/ko/restaurants/uGdEcg6dbgeX6NCsvbZB','verified_at':'2026-10-02','confidence':'HIGH'
  },
  'public_enterprise|남도한식-정든님': {
    'display':'남도한식 정든님','address':'서울특별시 중구 세종대로14길 22-5','phone':'02-775-0038','category':'한식 · 남도한정식','url':'https://www.tabling.co.kr/place/677cc7c366de5f069875573e','verified_at':'2026-10-02','confidence':'HIGH'
  },
  'public_enterprise|백호양대창 이수점': {
    'display':'백호양대창 이수점','address':'서울특별시 동작구 동작대로25길 30','phone':'02-591-5255','category':'고기·구이 · 양대창','url':'https://www.tabling.co.kr/place/677ccfa666de5f0698849d28','verified_at':'2026-10-02','confidence':'HIGH'
  },
  'public_enterprise|세광양대창 수서점': {
    'display':'세광양대창 수서점','address':'서울특별시 강남구 광평로51길 6-5 나성빌딩 2층','phone':'0507-1372-0824','category':'고기·구이 · 양대창','url':'https://www.sgfco.kr/sub/community/store.php','verified_at':'2026-10-02','confidence':'HIGH'
  },
  'public_enterprise|산들해반포': {
    'display':'산들해 반포점','address':'서울특별시 서초구 반포대로 287','phone':'02-537-0113','category':'한식 · 한정식','url':'https://www.tabling.co.kr/place/677cc74466de5f069874627d','verified_at':'2026-10-02','confidence':'HIGH'
  },
  'public_enterprise|민소한우(서린점)': {
    'display':'민소한우 서린점','address':'서울특별시 종로구 종로 22 지하1층','category':'고기·구이 · 한우/한식','url':'https://fmr.purpleo.co.kr/view/80','verified_at':'2026-10-02','confidence':'MEDIUM'
  },
  'public_enterprise|호텔롯데 롯데호텔제주': {
    'display':'롯데호텔 제주','address':'제주특별자치도 서귀포시 중문관광로72번길 35','phone':'064-731-1000','category':'호텔 · 레스토랑/F&B','url':'https://www.visitjeju.net/kr/detail/view?contentsid=CONT_000000000500859','verified_at':'2026-10-02','confidence':'HIGH'
  },
  'public_enterprise|남포면옥': {
    'display':'남포면옥','address':'서울특별시 중구 을지로3길 24','phone':'02-777-3131','category':'한식 · 평양냉면/어복쟁반','url':'https://english.visitkorea.or.kr/svc/whereToGo/locIntrdn/rgnContentsView.do?vcontsId=99736','verified_at':'2026-10-02','confidence':'HIGH'
  }
}
s.update(updates)
p.write_text(json.dumps(d,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
print('KOSPO_ENRICHED',len(updates))
