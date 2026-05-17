# Task 3: 한전 선로 잔여용량 구현

한전 API 키가 없으므로 두 가지 방법을 조합해서 구현해줘.

## 방법 1: 공공데이터포털 한전 API 연동 (data.go.kr)
- data.go.kr의 "한국전력공사_분산전원연계정보" API 사용
- 환경변수: KEPCO_API_KEY (아직 없으면 None 처리)
- endpoint: https://apis.data.go.kr/B552584/PowerInfoService/getDistributedPowerInfo
- 파라미터: serviceKey, sigunguCd(시군구코드), pageNo, numOfRows

## 방법 2: 한전 사이버지점 웹 바로가기 버튼 (API 없을 때 폴백)
- 주소에서 시도/시군구 추출해서 한전 조회 URL 생성
- URL: https://cyber.kepco.co.kr/ckepco/front/main.do

## 구현할 내용

### 백엔드 (data_collector/regulation_api.py)
_fetch_kepco 함수 수정:
```python
def _fetch_kepco(self, address, lat, lng, result):
    # 주소에서 시도코드, 시군구코드 추출
    # 예: 부산광역시 강서구 → metroCd=26, cityCd=440
    
    METRO_CODES = {
        "서울": "11", "부산": "26", "대구": "27", "인천": "28",
        "광주": "29", "대전": "30", "울산": "31", "세종": "36",
        "경기": "41", "강원": "42", "충북": "43", "충남": "44",
        "전북": "45", "전남": "46", "경북": "47", "경남": "48", "제주": "50"
    }
    
    kepco_api_key = os.environ.get("KEPCO_API_KEY", "")
    
    if kepco_api_key:
        # bigdata.kepco.co.kr API 호출 시도
        # GET https://bigdata.kepco.co.kr/openapi/v1/dispersedGeneration.do
        # 파라미터: metroCd, cityCd, apiKey, returnType=json
        pass
    
    # API 없어도 항상 링크 정보는 제공
    metro_cd = 추출한_시도코드
    result.kepco = {
        "available": False,
        "message": "한전 분산전원 연계정보는 직접 조회가 필요합니다",
        "direct_url": "https://cyber.kepco.co.kr/ckepco/front/main.do",
        "metro_cd": metro_cd,
        "guide": [
            "1. 아래 '한전 선로용량 조회' 버튼 클릭",
            "2. 주소 또는 전주번호 입력",
            "3. 변전소/변압기/DL별 잔여용량 확인",
            "4. 설치 용량(kW) 대비 잔여용량 충분한지 확인"
        ]
    }
```

### 프론트엔드 (규제 분석 탭 한전 섹션 개선)
현재 단순 링크 버튼 → 아래처럼 개선:

```jsx
<div className="kepco-section">
  <h3><i className="fa-solid fa-bolt"></i> 한전 계통연계 선로용량</h3>
  
  {/* 안내 카드 */}
  <div className="kepco-guide-card">
    <div className="kepco-steps">
      <div className="step">
        <span className="step-num">1</span>
        <span>아래 버튼으로 한전 사이버지점 접속</span>
      </div>
      <div className="step">
        <span className="step-num">2</span>
        <span>주소 또는 전주번호 입력하여 조회</span>
      </div>
      <div className="step">
        <span className="step-num">3</span>
        <span>배전선로 잔여용량 확인 (설치용량 {systemKw}kW 이상 필요)</span>
      </div>
    </div>
    
    {/* 확인 기준 */}
    <div className="kepco-criteria">
      <div className="criteria-item">
        <i className="fa-solid fa-check-circle text-green"></i>
        <span>변전소 여유용량 (vol1): 설치용량 이상</span>
      </div>
      <div className="criteria-item">
        <i className="fa-solid fa-check-circle text-green"></i>
        <span>변압기 여유용량 (vol2): 설치용량 이상</span>
      </div>
      <div className="criteria-item">
        <i className="fa-solid fa-check-circle text-green"></i>
        <span>DL 여유용량 (vol3): 설치용량 이상</span>
      </div>
    </div>
    
    {/* 바로가기 버튼 */}
    <a href="https://cyber.kepco.co.kr/ckepco/front/main.do" 
       target="_blank" 
       className="btn-kepco-primary">
      <i className="fa-solid fa-external-link"></i>
      한전 선로용량 직접 조회
    </a>
  </div>
  
  {/* 주의사항 */}
  <div className="kepco-notice">
    <i className="fa-solid fa-triangle-exclamation"></i>
    현재 잔여용량이 있어도 타 사업자 허가 신청 현황 확인 필수
  </div>
</div>
```

CSS도 함께 추가 (index.css):
- .kepco-guide-card: 연한 파란 배경 카드
- .step: flex, 번호 원형 배지
- .criteria-item: 체크리스트 스타일
- .btn-kepco-primary: 파란 버튼, 새 탭 아이콘
- .kepco-notice: 노란 경고 배너

git add -A && git commit -m "feat: 한전 선로용량 조회 가이드 UI 개선" && git push origin master
