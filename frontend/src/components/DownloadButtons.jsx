function extractFilename(path) {
  if (!path) return null
  return path.replace(/\\/g, '/').split('/').pop()
}

function downloadUrl(path) {
  const name = extractFilename(path)
  return name ? `/files/${name}` : null
}

export default function DownloadButtons({ htmlPath, pdfPath }) {
  const htmlUrl = downloadUrl(htmlPath)
  const pdfUrl  = downloadUrl(pdfPath)

  return (
    <div className="download-row">
      {htmlUrl ? (
        <a className="dl-btn dl-btn-html" href={htmlUrl} target="_blank" rel="noreferrer" download>
          🌐 HTML 보고서
        </a>
      ) : (
        <button className="dl-btn dl-btn-html" disabled>🌐 HTML 보고서</button>
      )}
      {pdfUrl ? (
        <a className="dl-btn dl-btn-pdf" href={pdfUrl} target="_blank" rel="noreferrer" download>
          📄 PDF 보고서
        </a>
      ) : (
        <button className="dl-btn dl-btn-pdf" disabled>
          📄 PDF 보고서{!pdfPath ? ' (생성 안됨)' : ''}
        </button>
      )}
    </div>
  )
}
