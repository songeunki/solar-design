Font Awesome 6 아이콘으로 전면 교체해줘.

1. frontend/index.html head 태그 안에 추가:
<link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.5.1/css/all.min.css">

2. 아래 이모지/텍스트를 FA 아이콘으로 교체 (프로젝트 전체 검색):
- ☀️ 또는 태양 → <i class="fa-solid fa-solar-panel"></i> (헤더), <i class="fa-solid fa-sun"></i> (발전량)
- 🏠 단일분석 → <i class="fa-solid fa-house"></i>
- 비교분석(🐾 또는 텍스트) → <i class="fa-solid fa-code-compare"></i>
- 📍 입지분석 → <i class="fa-solid fa-location-dot"></i>
- 💰 수익분석 → <i class="fa-solid fa-chart-line"></i>
- ✏️ 설계분석 → <i class="fa-solid fa-drafting-compass"></i>
- 🏛️ 규제분석 → <i class="fa-solid fa-scale-balanced"></i>
- AI종합평가(🐾) → <i class="fa-solid fa-robot"></i>
- 관리자설정 → <i class="fa-solid fa-gear"></i>
- 메인으로 화살표 → <i class="fa-solid fa-arrow-left"></i>
- 🔍 분석버튼 → <i class="fa-solid fa-magnifying-glass"></i>
- 💾 저장하기 → <i class="fa-solid fa-floppy-disk"></i>
- 새분석 → <i class="fa-solid fa-rotate"></i>
- 웹보고서 → <i class="fa-solid fa-file-lines"></i>
- PDF → <i class="fa-solid fa-file-pdf"></i>
- AI평가생성 → <i class="fa-solid fa-wand-magic-sparkles"></i>
- 다시생성 → <i class="fa-solid fa-arrows-rotate"></i>
- ⚡ 설치용량 KPI → <i class="fa-solid fa-bolt"></i>
- 연간발전량 KPI → <i class="fa-solid fa-sun"></i>
- 연간수익 KPI → <i class="fa-solid fa-coins"></i>
- 투자회수 KPI → <i class="fa-solid fa-clock-rotate-left"></i>

3. 아이콘 CSS (index.css에 추가):
.fa-solid { margin-right: 6px; }
탭버튼 아이콘은 color: inherit 유지
헤더 아이콘은 color: white

git add -A && git commit -m "feat: Font Awesome 6 아이콘 전면 교체" && git push origin master
