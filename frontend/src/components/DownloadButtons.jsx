/**
 * DownloadButtons
 * props:
 *   reportUrl - HTML 보고서 URL → 새 탭에서 바로 열기 (다운로드 없음)
 *   pdfUrl    - PDF URL → 파일 다운로드 전용
 */
export default function DownloadButtons({ reportUrl, pdfUrl }) {
  if (!reportUrl && !pdfUrl) return null;

  return (
    <div style={{
      display: 'flex',
      alignItems: 'center',
      gap: 12,
      padding: '14px 20px',
      background: 'var(--bg)',
      borderTop: '1px solid var(--border)',
      flexWrap: 'wrap',
    }}>
      {/* 섹션 라벨 */}
      <span style={{
        fontSize: 12,
        fontWeight: 700,
        color: 'var(--text-muted)',
        textTransform: 'uppercase',
        letterSpacing: '0.5px',
      }}>
        보고서
      </span>

      <div style={{ display: 'flex', gap: 10, marginLeft: 'auto' }}>

        {/* HTML — 새 탭에서 바로 보기 (다운로드 아님) */}
        {reportUrl && (
          <a
            href={reportUrl}
            target="_blank"
            rel="noopener noreferrer"
            style={{
              display: 'inline-flex',
              alignItems: 'center',
              gap: 7,
              padding: '8px 16px',
              borderRadius: 7,
              border: '1.5px solid var(--blue)',
              background: 'var(--blue-light)',
              color: 'var(--blue)',
              fontSize: 13,
              fontWeight: 600,
              textDecoration: 'none',
              fontFamily: "'Noto Sans KR', sans-serif",
              transition: 'all 0.18s',
              cursor: 'pointer',
            }}
            onMouseEnter={e => {
              e.currentTarget.style.background = 'var(--blue)';
              e.currentTarget.style.color = 'white';
            }}
            onMouseLeave={e => {
              e.currentTarget.style.background = 'var(--blue-light)';
              e.currentTarget.style.color = 'var(--blue)';
            }}
          >
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none"
              stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round">
              <path d="M18 13v6a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h6"/>
              <polyline points="15 3 21 3 21 9"/>
              <line x1="10" y1="14" x2="21" y2="3"/>
            </svg>
            웹 보고서 보기
          </a>
        )}

        {/* PDF — 파일 다운로드 */}
        {pdfUrl && (
          <a
            href={pdfUrl}
            download
            style={{
              display: 'inline-flex',
              alignItems: 'center',
              gap: 7,
              padding: '8px 16px',
              borderRadius: 7,
              border: 'none',
              background: 'var(--orange)',
              color: 'white',
              fontSize: 13,
              fontWeight: 600,
              textDecoration: 'none',
              fontFamily: "'Noto Sans KR', sans-serif",
              boxShadow: '0 2px 8px rgba(255,107,53,0.3)',
              transition: 'all 0.18s',
              cursor: 'pointer',
            }}
            onMouseEnter={e => {
              e.currentTarget.style.background = '#e55a25';
              e.currentTarget.style.boxShadow = '0 4px 16px rgba(255,107,53,0.4)';
              e.currentTarget.style.transform = 'translateY(-1px)';
            }}
            onMouseLeave={e => {
              e.currentTarget.style.background = 'var(--orange)';
              e.currentTarget.style.boxShadow = '0 2px 8px rgba(255,107,53,0.3)';
              e.currentTarget.style.transform = 'translateY(0)';
            }}
          >
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none"
              stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round">
              <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/>
              <polyline points="7 10 12 15 17 10"/>
              <line x1="12" y1="15" x2="12" y2="3"/>
            </svg>
            PDF 다운로드
          </a>
        )}

      </div>
    </div>
  );
}
