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
(여기에 다음에 할 작업을 직접 입력하세요)

---
