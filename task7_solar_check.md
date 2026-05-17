# Task 7: 태양광 설치 현장 감지 + 모바일 탭 텍스트

## 작업 1: 모바일 탭 아이콘+텍스트 표시

### 문제
모바일에서 result-tab-btn에 아이콘만 보이고 텍스트가 숨겨짐

### 수정 (index.css)
```css
/* 모바일 탭 - 아이콘+텍스트 둘 다 표시 */
@media (max-width: 767px) {
  .result-tab-btn {
    flex-direction: column;
    gap: 4px;
    font-size: 10px;
    padding: 8px 6px;
    min-width: 56px;
  }
  .result-tab-btn i {
    font-size: 16px;
    margin-right: 0;
  }
  .result-tab-btn span {
    display: block !important;
    font-size: 10px;
    white-space: nowrap;
  }
}
```

ResultTabs.jsx에서 각 탭 버튼을 아래 구조로 확인/수정:
```jsx
<button className={`result-tab-btn ${activeTab==='location'?'active':''}`}
  onClick={() => setActiveTab('location')}>
  <i className="fa-solid fa-location-dot"></i>
  <span>입지</span>
</button>
<button className={`result-tab-btn ${activeTab==='revenue'?'active':''}`}
  onClick={() => setActiveTab('revenue')}>
  <i className="fa-solid fa-chart-line"></i>
  <span>수익</span>
</button>
<button className={`result-tab-btn ${activeTab==='design'?'active':''}`}
  onClick={() => setActiveTab('design')}>
  <i className="fa-solid fa-drafting-compass"></i>
  <span>설계</span>
</button>
<button className={`result-tab-btn ${activeTab==='regulation'?'active':''}`}
  onClick={() => setActiveTab('regulation')}>
  <i className="fa-solid fa-scale-balanced"></i>
  <span>규제</span>
</button>
<button className={`result-tab-btn ${activeTab==='ai'?'active':''}`}
  onClick={() => setActiveTab('ai')}>
  <i className="fa-solid fa-robot"></i>
  <span>AI</span>
</button>
```

---

## 작업 2: 태양광 설치 현장 감지 및 안내

### 감지 방법
공공데이터포털 "전국태양광발전소전기사업허가정보표준데이터" 활용
- 이미 설치된 태양광 발전소 위치 데이터 (위도/경도 포함)
- API: https://www.data.go.kr/data/15107742/standard.do

또는 더 간단하게: 건축물대장 + 건물 용도 기반으로 추정

### 백엔드 (data_collector/solar_check.py 새 파일)
```python
import os
import requests
import math

def check_existing_solar(lat: float, lng: float, radius_m: float = 100) -> dict:
    """
    주어진 좌표 근처에 기존 태양광 설비가 있는지 확인
    공공데이터 전국태양광발전소 허가정보 활용
    """
    result = {
        "has_existing": False,
        "nearby_count": 0,
        "message": None,
        "installations": []
    }
    
    api_key = os.environ.get("SOLAR_DATA_API_KEY", "")
    
    if not api_key:
        # API 키 없으면 건물 용도로 추정
        return result
    
    try:
        url = "https://apis.data.go.kr/B552895/unis/getSolarGenFacility"
        params = {
            "serviceKey": api_key,
            "pageNo": 1,
            "numOfRows": 10,
            "latitude": lat,
            "longitude": lng,
            "radius": radius_m
        }
        resp = requests.get(url, params=params, timeout=10)
        # 파싱 로직
        data = resp.json()
        items = data.get("response", {}).get("body", {}).get("items", {}).get("item", [])
        if isinstance(items, dict):
            items = [items]
        
        if items:
            result["has_existing"] = True
            result["nearby_count"] = len(items)
            result["installations"] = items[:3]
            result["message"] = f"반경 {radius_m}m 내 기존 태양광 설비 {len(items)}개 감지"
    
    except Exception as e:
        pass
    
    return result
```

### pipeline.py에 통합
```python
# pipeline.py에서 regulation 조회 후 추가
from data_collector.solar_check import check_existing_solar

solar_check = check_existing_solar(location["lat"], location["lng"])
# result dict에 solar_check 추가
```

### 프론트엔드 안내 메시지 (ResultTabs.jsx 또는 SingleAnalysis.jsx)
분석 완료 후 상단에 배너로 표시:

```jsx
{solarCheck?.has_existing && (
  <div className="solar-existing-banner">
    <i className="fa-solid fa-triangle-exclamation"></i>
    <div>
      <strong>기존 태양광 설비 감지</strong>
      <p>반경 100m 내 {solarCheck.nearby_count}개의 태양광 발전소가 이미 설치되어 있습니다. 
      중복 설치 가능 여부 및 계통 연계 용량을 사전에 확인하세요.</p>
    </div>
  </div>
)}
```

CSS:
```css
.solar-existing-banner {
  background: rgba(255, 179, 0, 0.15);
  border: 1px solid #FFB300;
  border-radius: 8px;
  padding: 12px 16px;
  display: flex;
  align-items: flex-start;
  gap: 12px;
  margin-bottom: 16px;
  color: #FFB300;
}
.solar-existing-banner strong { color: #fff; display: block; margin-bottom: 4px; }
.solar-existing-banner p { color: #8899AA; font-size: 13px; margin: 0; }
.solar-existing-banner .fa-triangle-exclamation { font-size: 20px; margin-top: 2px; flex-shrink: 0; }
```

### API 키 없을 때 폴백
SOLAR_DATA_API_KEY 없어도 아래 조건으로 추정 표시:
- 건물 용도가 "태양광" 포함 시
- 또는 기존 건축물대장에 태양광 관련 정보 있을 때

API 키 없는 경우 안내:
```jsx
<div className="solar-check-info">
  <i className="fa-solid fa-circle-info"></i>
  기존 태양광 설치 여부는 
  <a href="https://www.data.go.kr/data/15107742/standard.do" target="_blank">
    전국태양광발전소 허가정보
  </a>
  에서 직접 확인하세요.
</div>
```

git add -A && git commit -m "feat: 모바일 탭 텍스트 표시 + 태양광 설치 현장 감지 안내" && git push origin master
