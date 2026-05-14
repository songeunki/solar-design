import { useEffect, useRef } from 'react'

const APP_KEY = import.meta.env.VITE_KAKAO_JS_APP_KEY || '1a26482813f863a4da8896cde91a820e'

function loadKakaoScript() {
  return new Promise((resolve) => {
    if (window.kakao?.maps) {
      window.kakao.maps.load(resolve)
      return
    }
    if (document.getElementById('kakao-map-sdk')) {
      // 이미 로딩 중 — load 완료 이벤트 대기
      const interval = setInterval(() => {
        if (window.kakao?.maps) {
          clearInterval(interval)
          window.kakao.maps.load(resolve)
        }
      }, 100)
      return
    }
    const script = document.createElement('script')
    script.id  = 'kakao-map-sdk'
    script.src = `//dapi.kakao.com/v2/maps/sdk.js?appkey=${APP_KEY}&libraries=services&autoload=false`
    script.onload = () => window.kakao.maps.load(resolve)
    document.head.appendChild(script)
  })
}

export default function KakaoMap({ onAddressSelect, markerLatLng, markerResult }) {
  const containerRef  = useRef(null)
  const mapRef        = useRef(null)
  const markerRef     = useRef(null)
  const infoWindowRef = useRef(null)

  // 지도 최초 초기화
  useEffect(() => {
    loadKakaoScript().then(() => {
      if (!containerRef.current || mapRef.current) return
      const map = new window.kakao.maps.Map(containerRef.current, {
        center: new window.kakao.maps.LatLng(37.5665, 126.978),
        level: 5,
      })
      mapRef.current = map

      window.kakao.maps.event.addListener(map, 'click', (e) => {
        const latlng = e.latLng
        placeMarker(map, latlng)
        reverseGeocode(latlng)
      })
    })
  }, [])

  // 외부에서 lat/lng가 전달되면 마커 이동 + 지도 중심 이동
  useEffect(() => {
    if (!mapRef.current || !markerLatLng) return
    const latlng = new window.kakao.maps.LatLng(markerLatLng.lat, markerLatLng.lng)
    placeMarker(mapRef.current, latlng)
    mapRef.current.panTo(latlng)
  }, [markerLatLng])

  // 분석 완료 후 인포윈도우 표시
  useEffect(() => {
    if (!mapRef.current || !markerRef.current || !markerResult) return
    if (infoWindowRef.current) {
      infoWindowRef.current.close()
      infoWindowRef.current = null
    }

    const s    = markerResult.summary
    const cap  = s?.['태양광시스템']?.['총용량_kW']
    const gen  = s?.['태양광시스템']?.['연간발전량_kWh']
    const addr = s?.['주소'] || ''
    const type = s?.['건물정보']?.['유형'] || ''
    const pay  = s?.['경제성']?.['단순회수기간_년']

    const content = `
      <div style="padding:14px 16px;min-width:210px;font-family:'Segoe UI',sans-serif;font-size:13px;line-height:1.6">
        <div style="font-weight:700;color:#1f2937;font-size:13px;margin-bottom:4px">
          ${addr.length > 22 ? addr.slice(0, 22) + '…' : addr}
        </div>
        <div style="color:#9ca3af;font-size:11px;margin-bottom:10px">${type}</div>
        <div style="display:flex;flex-direction:column;gap:5px">
          <div style="display:flex;justify-content:space-between;gap:16px">
            <span style="color:#6b7280">⚡ 시스템 용량</span>
            <strong style="color:#d97706">${cap != null ? cap.toFixed(1) + ' kW' : '—'}</strong>
          </div>
          <div style="display:flex;justify-content:space-between;gap:16px">
            <span style="color:#6b7280">🔆 연간 발전량</span>
            <strong style="color:#ea580c">${gen != null ? gen.toLocaleString() + ' kWh' : '—'}</strong>
          </div>
          <div style="display:flex;justify-content:space-between;gap:16px">
            <span style="color:#6b7280">📅 회수 기간</span>
            <strong style="color:#374151">${pay != null ? pay.toFixed(1) + ' 년' : '—'}</strong>
          </div>
        </div>
      </div>`

    const iw = new window.kakao.maps.InfoWindow({ content, removable: true })
    iw.open(mapRef.current, markerRef.current)
    infoWindowRef.current = iw
  }, [markerResult])

  function placeMarker(map, latlng) {
    if (markerRef.current) markerRef.current.setMap(null)
    if (infoWindowRef.current) {
      infoWindowRef.current.close()
      infoWindowRef.current = null
    }
    const marker = new window.kakao.maps.Marker({ position: latlng })
    marker.setMap(map)
    markerRef.current = marker
  }

  function reverseGeocode(latlng) {
    const geocoder = new window.kakao.maps.services.Geocoder()
    geocoder.coord2Address(latlng.getLng(), latlng.getLat(), (result, status) => {
      if (status !== window.kakao.maps.services.Status.OK) return
      const addr =
        result[0]?.road_address?.address_name ||
        result[0]?.address?.address_name || ''
      if (addr) onAddressSelect?.(addr, latlng.getLat(), latlng.getLng())
    })
  }

  return (
    <div style={{ position: 'relative', width: '100%', height: '100%' }}>
      <div
        ref={containerRef}
        style={{ width: '100%', height: '100%', borderRadius: 'var(--radius)' }}
      />
      <div className="map-hint">
        지도를 클릭하면 주소가 자동 입력됩니다
      </div>
    </div>
  )
}
