---
# SolarDesign AI 프로젝트 인수인계

## 나는 누구인가
태양광 입지 분석 AI 서비스 SolarDesign AI를 개발 중입니다.
새로운 Claude 채팅창에서 이어서 작업합니다.

## 서비스 정보
- 서비스명: SolarDesign AI (Beta v1.0)
- 프론트엔드: https://solar-design-opal.vercel.app
- 백엔드: https://solar-design.onrender.com
- GitHub: https://github.com/songeunki/solar-design
- 로컬: 프론트 localhost:5173 / 백엔드 localhost:8001

## 기술 스택
- Frontend: React + Vite → Vercel 자동배포
- Backend: FastAPI + Python → Render 자동배포 (Docker)
- AI: Gemini 2.0 Flash API
- 지도: 카카오맵 JavaScript API
- 배포: GitHub push → 자동배포 (Vercel + Render)

## 주요 파일 구조
frontend/src/components/
  - SingleAnalysis.jsx : 단일분석 메인 컴포넌트
  - ResultTabs.jsx : 결과 탭 (입지/수익/설계/규제/AI/보고서)
  - KakaoMap.jsx : 카카오맵 위성지도
analyzer/
  - regulation_api.py : 규제/용도지역 분석
  - ordinance_api.py : 지자체 조례 조회
  - panel_layout.py : 태양광 패널 배치 계산
  - roof_capture.py : 위성 이미지 건물 감지
api/
  - main.py : FastAPI 진입점
  - routers/analyze.py : 분석 WebSocket 라우터

## 환경변수
[Render 백엔드 등록완료]
GEMINI_API_KEY, VWORLD_API_KEY, VWORLD_LAND_API_KEY,
KAKAO_JS_APP_KEY, KAKAO_REST_API_KEY, BUILDING_API_KEY,
JUSO_API_KEY, LURIS_API_KEY

[Render 백엔드 미등록]
LAW_API_KEY - 국가법령정보센터 (지자체 조례 고도화용)

[Vercel 프론트엔드]
VITE_API_URL=https://solar-design.onrender.com
VITE_KAKAO_JS_APP_KEY

## 완료된 기능
- 주소 입력 → AI 태양광 입지 자동 분석
- 카카오맵 위성지도 + 분석 위치 마커 + 줌인
- 결과 6개 탭: 입지 / 수익 / 설계 / 규제 / AI / 보고서
- Gemini AI 종합 평가 (429 retry 3회 적용)
- 개발행위허가 자동 판단 (용량/용도지역 기반)
- 지자체 조례 실시간 조회 + fallback 링크 제공
- 한전 계통연계 용량 안내
- 지도 하단 주소 입력창 (빠른 재분석)
- 로고 클릭 → 메인 화면 이동
- 비교 분석 탭

## 알려진 이슈
- V-World 토지특성 API 간헐적 502 오류 (fallback 처리 완료)
- Gemini 429 오류 간헐적 발생 (retry 완료)
- 지자체 조례 지역명 추출 정확도 개선 필요
- LAW_API_KEY 미등록으로 조례 fallback 모드 동작 중

## 개발 방법
새 기능 추가 시:
1. Claude Code에서 코드 수정
2. git push → Vercel/Render 자동배포
3. solar-design-opal.vercel.app 에서 확인

로컬 실행:
cd frontend && npm run dev
uvicorn api.main:app --reload --port 8001

## 다음 작업 예정

### 우선순위 높음
1. **LAW_API_KEY 등록 후 조례 조회 검증**
   - Render 대시보드에서 LAW_API_KEY 등록
   - 실제 조례 데이터 조회 및 Gemini 요약 동작 확인
   - ordinance_api.py: 법령명한글 파싱 정확도 점검

2. **V-World 토지특성 API 안정화**
   - data_collector/regulation_api.py 재시도 로직 강화
   - VWORLD_LAND_API_KEY 미설정 환경에서 fallback 메시지 개선
   - 지목/이용현황/지형고저 실제 데이터 수신 확인

3. **주소 파싱 정확도 개선**
   - sido/sigungu 추출 로직 개선 (현재 단순 split 방식)
   - "경기도 수원시 장안구" 같은 3단계 행정구역 처리
   - data_collector/address_api.py: _parse_sido_sigungu 함수 개선

### 우선순위 보통
4. **규제 탭 용도지역 실데이터 연동**
   - 현재 건물 용도 기반 추정값 사용 중
   - V-World 용도지역 API 연동으로 실제 용도지역 표시
   - regulation_api.py: _fetch_vworld 함수에 용도지역 파싱 추가

5. **비교 분석 탭 기능 완성**
   - 현재 기본 UI만 구성된 상태
   - 2~4개 주소 동시 분석 후 수익/용량 비교 테이블
   - CompareAnalysis.jsx 결과 표시 섹션 추가

6. **보고서 PDF 품질 개선**
   - output/report_generator.py 레이아웃 개선
   - 규제 정보(개발행위허가, 전력계통) 보고서에 포함
   - 위성지도 이미지 캡처 안정화

### 우선순위 낮음
7. **UI/UX 개선**
   - 분석 중 단계별 진행 메시지 상세화
   - 모바일 반응형 레이아웃 점검
   - 다크모드 색상 일관성 정리

8. **성능 최적화**
   - Render 무료 플랜 Cold Start 대응 (첫 요청 지연 안내)
   - 분석 결과 캐싱 (동일 주소 재분석 시 빠른 응답)

---
