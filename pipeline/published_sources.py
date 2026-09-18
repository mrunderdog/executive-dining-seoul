from __future__ import annotations

import json
import math
import re
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RAW_DIR = ROOT / "data" / "raw"
REPORTS = ROOT / "reports"

SOURCE_SPECS = {
    "goyang": {
        "origin": "고양시",
        "region": "경기",
        "jurisdiction": "고양특례시",
        "institution": "고양특례시의회",
        "min_visits": 4,
        "min_months": 3,
        "min_score": 55.0,
        "max_records": 30,
        "home_tokens": ("고양",),
    },
    "suwon": {
        "origin": "수원시",
        "region": "경기",
        "jurisdiction": "수원특례시",
        "institution": "수원특례시의회",
        "min_visits": 4,
        "min_months": 3,
        "min_score": 55.0,
        "max_records": 30,
        "home_tokens": ("수원",),
    },
    "bupyeong": {
        "origin": "부평구",
        "region": "인천",
        "jurisdiction": "인천광역시 부평구",
        "institution": "부평구의회",
        "min_visits": 4,
        "min_months": 3,
        "min_score": 55.0,
        "max_records": 30,
        "home_tokens": ("부평", "인천"),
    },
    "yeonsu": {
        "origin": "연수구",
        "region": "인천",
        "jurisdiction": "인천광역시 연수구",
        "institution": "연수구의회",
        "min_visits": 4,
        "min_months": 3,
        "min_score": 55.0,
        "max_records": 30,
        "home_tokens": ("연수", "인천"),
    },
    "gyeyang": {
        "origin": "계양구",
        "region": "인천",
        "jurisdiction": "인천광역시 계양구",
        "institution": "계양구의회",
        "min_visits": 4,
        "min_months": 3,
        "min_score": 55.0,
        "max_records": 30,
        "home_tokens": ("계양", "인천"),
    },
    "ganghwa": {
        "origin": "강화군",
        "region": "인천",
        "jurisdiction": "인천광역시 강화군",
        "institution": "강화군의회",
        "min_visits": 3,
        "min_months": 2,
        "min_score": 50.0,
        "max_records": 30,
        "home_tokens": ("강화", "인천"),
    },
    "ongjin": {
        "origin": "옹진군",
        "region": "인천",
        "jurisdiction": "인천광역시 옹진군",
        "institution": "옹진군의회",
        "min_visits": 3,
        "min_months": 2,
        "min_score": 50.0,
        "max_records": 30,
        "home_tokens": ("옹진", "인천"),
    },
    "gyeonggi_council": {
        "origin": "경기도의회",
        "region": "경기",
        "jurisdiction": "경기도",
        "institution": "경기도의회",
        "min_visits": 3,
        "min_months": 2,
        "min_score": 50.0,
        "max_records": 40,
        "home_tokens": ("경기", "수원"),
    },
}

ENTITY_ALIASES = {
    "일산하인선생": "하인선생 일산점",
    "하인선생": "하인선생 일산점",
    "우설화": "우설화 일산점",
    "일산우설화": "우설화 일산점",
    "송포털레기.추어탕": "송포털레기 추어탕",
    "송포털레기": "송포털레기 추어탕",
}

ENTITY_OVERRIDES = {
    "고봉산한우터": {"address":"경기도 고양시 일산동구 성석로 17","phone":"031-975-9234","category":"고기·구이 · 한우","url":"https://place.udanax.org/p/12167/%EA%B3%A0%EB%B4%89%EC%82%B0%ED%95%9C%EC%9A%B0%ED%84%B0"},
    "원주추옥": {"address":"경기도 고양시 덕양구 원당로33번길 58","phone":"031-968-7888","category":"국물·탕 · 추어탕","url":"https://www.diningcode.com/profile.php?rid=TREuf7DSQEq9"},
    "맛있는정원": {"address":"경기도 고양시 덕양구 성사동 338-20","phone":"031-967-9888","category":"고기·구이","url":""},
    "사계절어촌": {"address":"경기도 고양시 일산서구 주엽로 80","phone":"031-929-6765","category":"회·해산물","url":""},
    "화정가든": {"address":"경기도 고양시 덕양구 행주로15번길 49-12","phone":"031-972-7705","category":"한식 · 보리굴비/홍어","url":"https://www.hjgarden.net/main/index.html"},
    "일산긴자": {"address":"경기도 고양시 일산동구 무궁화로 359","phone":"","category":"일식","url":""},
    "일산들밥": {"address":"경기도 고양시 일산서구 중앙로 1581","phone":"031-922-6862","category":"한식 · 한정식","url":""},
    "엄선 엄마의 생선찜 구이": {"address":"경기도 고양시 일산서구 대산로212번길 7-6","phone":"","category":"해물·생선","url":"https://bizno.net/article/3631602079"},
    "오대돌솥추어탕": {"address":"경기도 고양시 일산서구 대화로 150-3","phone":"031-911-2200","category":"국물·탕 · 추어탕","url":"https://www.diningcode.com/profile.php?rid=06lUMa5DF9nO"},
    "고양회관": {"address":"경기도 고양시 덕양구 고양시청로 16-5","phone":"","category":"한식","url":"https://opengo.kr/5601fb7e0e887edf2cf45ac3"},
    "남궁": {"address":"경기도 고양시 일산서구 대화동 2101","phone":"031-911-3773","category":"중식","url":""},
    "하인선생 일산점": {"address":"경기도 고양시 일산동구 식사동 833-14","phone":"031-968-9819","category":"중식","url":""},
    "우설화 일산점": {"address":"경기도 고양시 일산동구 식사동 833-14","phone":"031-968-9401","category":"고기·구이 · 한우/갈비","url":""},
    "보양삼계탕": {"address":"경기도 고양시 일산서구 주화로 180","phone":"031-912-9911","category":"국물·탕 · 삼계탕","url":""},
    "교촌치킨(강선점)": {"address":"경기도 고양시 일산동구 정발산동 687-5","phone":"031-911-9980","category":"치킨","url":""},
    "송포털레기 추어탕": {"address":"경기도 고양시 일산서구 강성로214번길 8-22","phone":"031-916-8252","category":"국물·탕 · 추어탕/매운탕","url":"https://www.diningcode.com/profile.php?rid=gwD2hIJr83yt"},
    "진국한식부페": {"address":"경기도 고양시 덕양구 고양시청로 5","phone":"","category":"한식 · 한식뷔페","url":"https://www.diningcode.com/profile.php?rid=8RrQuUfVlLi6"},
}

CATEGORY_RULES = [
    (("참치",), "일식·참치"), (("스시", "초밥"), "일식·스시/초밥"),
    (("횟집", "회집", "세꼬시", "수산", "사시미", "어촌", "막회"), "회·해산물"),
    (("복어", "복집"), "복어"),
    (("아구", "동태", "코다리", "갈치", "낙지", "쭈꾸미", "꼼장어", "생선", "오징어"), "해물·생선"),
    (("한우", "갈비", "숯불", "고기", "삼겹", "곱창", "막창", "축산", "오리", "돈판", "양꼬치", "양갈비", "대창"), "고기·구이"),
    (("장어",), "장어"),
    (("삼계탕", "추어탕", "순대", "설렁탕", "곰탕", "감자탕", "해장국", "국밥", "찌개", "전골"), "국물·탕"),
    (("면옥", "냉면", "막국수", "칼국수", "소바", "국수", "메밀"), "면·국수"),
    (("족발",), "족발"), (("보쌈",), "보쌈"),
    (("반점", "중화", "짜장", "짬뽕", "샤오롱", "하인선생", "남궁"), "중식"),
    (("치킨", "통닭", "비비큐"), "치킨"), (("샤브",), "샤브샤브"),
    (("파스타", "비스트로", "레스토랑"), "양식"), (("분식", "김밥"), "분식"),
]


def _txt(v) -> str:
    return " ".join(str(v or "").split()).strip()


def _canonical(name: str) -> str:
    name = _txt(name)
    return ENTITY_ALIASES.get(name, name)


def _category(name: str) -> str:
    if name in ENTITY_OVERRIDES and ENTITY_OVERRIDES[name].get("category"):
        return ENTITY_OVERRIDES[name]["category"]
    for words, label in CATEGORY_RULES:
        if any(w in name for w in words):
            return f"{label} (상호명 기반 추정)"
    return "업종 확인 필요"


def _role_bucket(role: str) -> str | None:
    s = re.sub(r"\s+", "", _txt(role))
    return s if s in {"의장", "부의장"} else None


def _most_common(values: list[str]) -> str:
    vals = [_txt(x) for x in values if _txt(x)]
    return Counter(vals).most_common(1)[0][0] if vals else ""


def _is_evening(value: str) -> bool:
    m = re.match(r"\s*(\d{1,2})(?::|시)", _txt(value))
    return bool(m and int(m.group(1)) >= 17)


def _is_outside_home(address: str, home_tokens: tuple[str, ...]) -> bool | None:
    a = _txt(address)
    if not a:
        return None
    return not any(token in a for token in home_tokens)


def _destination_score(visits: int, roles: int, months: int, evening_ratio: float, outside_ratio: float) -> float:
    distance = min(max(outside_ratio, 0.0), 1.0)
    visit_norm = min(math.log1p(visits) / math.log1p(10), 1.0)
    role_norm = min(roles / 4, 1.0)
    month_norm = min(months / 5, 1.0)
    return round(100 * (0.25*distance + 0.45*visit_norm + 0.15*role_norm + 0.10*month_norm + 0.05*evening_ratio), 1)


def _load_source(source: str) -> tuple[dict, dict] | None:
    raw_path = RAW_DIR / f"{source}_expense.json"
    cand_path = REPORTS / f"{source}-executive-candidates.json"
    if not raw_path.exists() or not cand_path.exists():
        return None
    return json.loads(raw_path.read_text(encoding="utf-8")), json.loads(cand_path.read_text(encoding="utf-8"))


def _build_source_records(source: str, spec: dict) -> list[dict]:
    loaded = _load_source(source)
    if not loaded:
        return []
    raw, candidates_doc = loaded
    grouped_candidates: dict[str, dict] = {}
    for c in candidates_doc.get("candidates", []):
        name = _canonical(c.get("merchant"))
        cur = grouped_candidates.setdefault(name, {"merchant": name, "score": 0.0, "visits": 0, "months": 0})
        cur["score"] = max(float(cur.get("score") or 0), float(c.get("score") or 0))
        cur["visits"] += int(c.get("visits") or 0)
        cur["months"] = max(int(cur.get("months") or 0), int(c.get("months") or 0))
    selected = [c for c in grouped_candidates.values()
        if int(c.get("visits") or 0) >= spec["min_visits"]
        and int(c.get("months") or 0) >= spec["min_months"]
        and float(c.get("score") or 0) >= spec["min_score"]]
    selected.sort(key=lambda c: (float(c.get("score") or 0), int(c.get("visits") or 0)), reverse=True)
    selected = selected[:spec["max_records"]]
    selected_names = {c["merchant"] for c in selected}
    grouped: dict[str, list[dict]] = defaultdict(list)
    for r in raw.get("rows", []):
        name = _canonical(r.get("merchant"))
        if name not in selected_names or r.get("date_quality") != "in_period" or not _role_bucket(r.get("role")):
            continue
        grouped[name].append(r)
    out = []
    for rank, c in enumerate(selected, start=1):
        name = c["merchant"]
        rows = sorted(grouped.get(name, []), key=lambda x: (x.get("used_date") or "", x.get("used_time") or ""))
        if not rows:
            continue
        visits = len(rows); spend = sum(int(r.get("amount") or 0) for r in rows); people = sum(int(r.get("people") or 0) for r in rows)
        months_set = sorted({(r.get("used_date") or "")[:7] for r in rows if re.match(r"20\d{2}-\d{2}", r.get("used_date") or "")})
        evening = sum(_is_evening(r.get("used_time") or "") for r in rows); evening_ratio = round(evening/visits, 3) if visits else 0
        raw_address = _most_common([r.get("address") or "" for r in rows])
        override = ENTITY_OVERRIDES.get(name, {})
        address = _txt(override.get("address")) or raw_address
        role_map = defaultdict(lambda: {"visits":0,"people":0,"spend":0})
        for r in rows:
            role = _role_bucket(r.get("role")) or _txt(r.get("role")) or "직책 미상"
            role_map[role]["visits"] += 1; role_map[role]["people"] += int(r.get("people") or 0); role_map[role]["spend"] += int(r.get("amount") or 0)
        roles = [{"role":role, **vals} for role, vals in sorted(role_map.items(), key=lambda kv:(kv[1]["visits"],kv[1]["spend"]), reverse=True)]
        purposes_count = Counter(_txt(r.get("purpose")) for r in rows if _txt(r.get("purpose")))
        purposes = [{"text":text,"count":count} for text,count in purposes_count.most_common(5)]
        recent = [{"date":_txt(r.get("used_date")),"time":_txt(r.get("used_time")),"role":_role_bucket(r.get("role")) or _txt(r.get("role")),"people":int(r.get("people") or 0),"amount":int(r.get("amount") or 0),"purpose":_txt(r.get("purpose")),"source":_txt(r.get("source_post_url"))} for r in reversed(rows[-8:])]
        outside_flags = [_is_outside_home(r.get("address") or "", spec["home_tokens"]) for r in rows]
        outside_known = [x for x in outside_flags if x is not None]
        outside_count = sum(1 for x in outside_known if x); outside_ratio = round(outside_count/len(outside_known),3) if outside_known else 0.0
        has_destination = outside_count >= 2 and outside_ratio >= 0.5
        destination = {"rank":rank,"score":_destination_score(visits,len(roles),len(months_set),evening_ratio,outside_ratio),"events":visits,"exec_events":visits,"roles":len(roles),"months":len(months_set),"evening_ratio":evening_ratio,"outside_ratio":outside_ratio,"source":source} if has_destination else None
        executive = {"rank":rank,"score":round(float(c.get("score") or 0),1),"exec_events":visits,"roles":len(roles),"months":len(months_set),"evening_ratio":evening_ratio,"source":source}
        role_label = "·".join(x["role"] for x in roles[:2]) if roles else "의장단"
        why = f"{spec['institution']} {role_label} 공개 업무추진비에서 {visits}회 반복 선택, {len(months_set)}개월 지속"
        if evening_ratio >= .5: why += f", 저녁 사용 {round(evening_ratio*100)}%"
        if has_destination: why += f", 관외 주소 사용 비중 {round(outside_ratio*100)}%"
        why += "이 확인됩니다."
        out.append({
            "name":name,"origin":spec["origin"],"region":spec["region"],"jurisdiction":spec["jurisdiction"],"institution":spec["institution"],
            "type":"both" if destination else "executive","destination":destination,"executive":executive,"address":address,
            "search_query":" ".join(x for x in (name,address or spec["jurisdiction"]) if x),
            "business":{"display":name,"category":_category(name),"phone":_txt(override.get("phone")),"status":"업무추진비 원자료 + 업체정보 보강" if override else "공개 원자료상 업소명 확인","rating":"","note":f"{spec['institution']} 공개 업무추진비 원자료 기반. 업체 주소/업종은 확인 가능한 경우 별도 보강.","url":_txt(override.get("url"))},
            "evidence":{"visits":visits,"spend":spend,"people":people,"months":len(months_set),"evening":evening,"evening_ratio":evening_ratio,"ppc":round(spend/people) if people else 0,"date_min":rows[0].get("used_date") or "","date_max":rows[-1].get("used_date") or "","roles":roles,"purposes":purposes,"recent":recent,"source_rows":[r.get("row_id") for r in rows if r.get("row_id")]},
            "why":why,"published_source":source,
        })
    return out


def _build_seoul_city_records(max_records: int = 100) -> list[dict]:
    path = REPORTS / "seoul-city-hall-executive-candidates.json"
    if not path.exists():
        return []
    doc = json.loads(path.read_text(encoding="utf-8"))
    candidates = doc.get("candidates") or []
    # Publication gate: require a usable address plus strong repeat/persistence evidence.
    publishable = [c for c in candidates
        if _txt(c.get("address"))
        and int(c.get("visits") or 0) >= 5
        and int(c.get("months") or 0) >= 3
        and int(c.get("department_count") or 0) >= 3]
    publishable.sort(key=lambda c: (float(c.get("executive_score") or 0), int(c.get("visits") or 0)), reverse=True)
    out = []
    for rank, c in enumerate(publishable[:max_records], 1):
        name = _txt(c.get("merchant")); address = _txt(c.get("address"))
        visits = int(c.get("visits") or 0); spend = int(c.get("spend") or 0); months = int(c.get("months") or 0)
        dept_count = int(c.get("department_count") or 0); evening_ratio = float(c.get("evening_ratio") or 0)
        evening = round(visits * evening_ratio)
        dept_stats = c.get("department_stats") or []
        roles = [{"role":_txt(x.get("department")),"visits":int(x.get("visits") or 0),"people":0,"spend":int(x.get("spend") or 0)} for x in dept_stats if _txt(x.get("department"))]
        purposes = [{"text":_txt(x.get("text")),"count":int(x.get("count") or 0)} for x in (c.get("purpose_stats") or []) if _txt(x.get("text"))]
        recent = [{"date":_txt(x.get("date")),"time":_txt(x.get("time")),"role":_txt(x.get("department")),"people":int(x.get("people") or 0),"amount":int(x.get("amount") or 0),"purpose":_txt(x.get("purpose")),"source":_txt(x.get("source"))} for x in (c.get("recent") or [])]
        has_destination = float(c.get("destination_weight") or 0) >= .65
        executive = {"rank":rank,"score":round(float(c.get("executive_score") or 0),1),"exec_events":visits,"roles":dept_count,"months":months,"evening_ratio":evening_ratio,"source":"seoul_city_hall"}
        destination = {"rank":rank,"score":round(float(c.get("destination_score") or 0),1),"events":visits,"exec_events":visits,"roles":dept_count,"months":months,"evening_ratio":evening_ratio,"outside_ratio":float(c.get("destination_weight") or 0),"source":"seoul_city_hall"} if has_destination else None
        why = f"서울특별시 본청 업무추진비에서 {visits}회 선택, {dept_count}개 부서, {months}개월에 걸쳐 반복 사용되었습니다."
        if evening_ratio >= .5: why += f" 저녁 사용 비중은 {round(evening_ratio*100)}%입니다."
        if has_destination: why += " 서울시청 생활권을 벗어난 목적지 선택 신호도 확인됩니다."
        out.append({
            "name":name,"origin":"서울시청","region":"서울","jurisdiction":"서울특별시","institution":"서울특별시 본청",
            "type":"both" if destination else "executive","destination":destination,"executive":executive,"address":address,
            "search_query":f"{name} {address}",
            "business":{"display":name,"category":_category(name),"phone":"","status":"서울시 업무추진비 원자료상 업소명·주소 확인","rating":"","note":"서울 열린데이터광장 OA-22156 업무추진비 공개자료 기반. 업종은 상호명 기반 추정이며 별도 업체 검증 전에는 참고용입니다.","url":""},
            "evidence":{"visits":visits,"spend":spend,"people":int(c.get("known_people") or 0),"months":months,"evening":evening,"evening_ratio":evening_ratio,"ppc":0,"date_min":_txt(c.get("date_min")),"date_max":_txt(c.get("date_max")),"roles":roles,"purposes":purposes,"recent":recent,"source_rows":[]},
            "why":why,"published_source":"seoul_city_hall","cohort":"regional_executive","location_bucket":_txt(c.get("location_bucket")),
        })
    return out


def merge_published_sources(payload: dict) -> dict:
    base = list(payload.get("records", []))
    seen = {(str(r.get("name","")).strip(),str(r.get("origin","")).strip()) for r in base}
    added=[]
    for source,spec in SOURCE_SPECS.items():
        for r in _build_source_records(source,spec):
            k=(r["name"],r["origin"])
            if k in seen: continue
            seen.add(k); added.append(r)
    for r in _build_seoul_city_records():
        k=(r["name"],r["origin"])
        if k in seen: continue
        seen.add(k); added.append(r)
    records=base+added
    payload=dict(payload); payload["records"]=records
    payload["origins"]=sorted({str(r.get("origin","")).strip() for r in records if str(r.get("origin","")).strip()})
    payload["stats"]={"total":len(records),"destination":sum(bool(r.get("destination")) for r in records),"executive":sum(bool(r.get("executive")) for r in records),"both":sum(bool(r.get("destination")) and bool(r.get("executive")) for r in records),"supplemental":len(added)}
    meta=dict(payload.get("meta") or {})
    sources=set(SOURCE_SPECS) | {"seoul_city_hall"}
    meta["published_supplements"]={source:sum(1 for r in added if r.get("published_source")==source) for source in sources}
    meta["scope"]="수도권 공공부문 Executive Dining — 기초의회 + 광역 집행부"
    meta["source_scope"]="서울 자치구의회 seed + 검증·정규화된 수도권 의회 업무추진비 + 서울특별시 본청 OA-22156"
    if added:
        dates=[r.get("evidence",{}).get("date_max","") for r in added if r.get("evidence",{}).get("date_max")]
        if dates: meta["period_end"]=max(str(meta.get("period_end") or ""),max(dates))
    payload["meta"]=meta
    return payload
