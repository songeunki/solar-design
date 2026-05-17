# Task 2: 비교 분석 페이지 오류 수정

비교 분석 탭에서 주소 입력 후 분석하면 결과 화면이 안 나오는 버그 수정해줘.

## 디버깅 순서

1. frontend/src/components/CompareAnalysis.jsx 열어서 확인:
   - WebSocket 연결 방식 확인 (SingleAnalysis.jsx와 동일한 패턴인지)
   - ws:// vs wss:// 프로토콜 처리 확인
   - 결과 데이터 파싱 방식 확인 (msg.data vs data.result)
   - 상태 업데이트 로직 확인

2. api/routers/compare.py 확인:
   - POST /compare 엔드포인트
   - WS /ws/compare 엔드포인트
   - 반환 데이터 구조가 analyze.py와 동일한지 확인

3. 주요 버그 패턴 (SingleAnalysis.jsx에서 이미 수정된 것들):
   - WebSocket URL: ws:// 하드코딩 → location.protocol 기반 동적 생성
   - 데이터 파싱: data.result → msg.data
   - stale closure: useState → useRef 패턴

4. CompareAnalysis.jsx에서 위 패턴들이 올바르게 적용됐는지 확인하고
   SingleAnalysis.jsx와 동일한 방식으로 수정

5. 결과 표시 컴포넌트가 compare 결과 데이터 구조에 맞게 렌더링되는지 확인

git add -A && git commit -m "fix: 비교 분석 WebSocket 및 결과 표시 오류 수정" && git push origin master
