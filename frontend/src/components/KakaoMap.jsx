import { useEffect, useRef } from 'react'

const APP_KEY = import.meta.env.VITE_KAKAO_JS_APP_KEY || '1a26482813f863a4da8896cde91a820e'

function loadKakaoScript() {
  return new Promise((resolve) => {
    if (window.kakao?.maps) { window.kakao.maps.load(resolve); return }
    if (document.getElementById('kakao-map-sdk')) {
      const t = setInterval(() => {
        if (window.kakao?.maps) { clearInterval(t); window.kakao.maps.load(resolve) }
      }, 100)
      return
    }
    const script  = document.createElement('script')
    script.id     = 'kakao-map-sdk'
    script.src    = `//dapi.kakao.com/v2/maps/sdk.js?appkey=${APP_KEY}&libraries=services&autoload=false`
    script.onload = () => window.kakao.maps.load(resolve)
    document.head.appendChild(script)
  })
}

function buildOverlayContent({ addr, type, cap, gen, pay }) {
  const row = (label, value, color) => `
    <div style="display:flex;justify-content:space-between;gap:16px;padding:5px 0;
                border-bottom:1px solid #F1F5F9;">
      <span style="color:#64748B;font-size:11px;white-space:nowrap">${label}</span>
      <strong style="color:${color};font-size:12px;font-weight:600">${value}</strong>
    </div>`

  return `
    <div style="
      position:relative;
      font-family:'IBM Plex Sans',system-ui,sans-serif;
      background:#fff;
      border:1px solid #E2E8F0;
      border-radius:12px;
      overflow:visible;
      min-width:220px;
      box-shadow:0 4px 24px rgba(0,0,0,0.15);
    ">
      <div style="padding:11px 14px;border-bottom:1px solid #F1F5F9;background:#F8FAFC;border-radius:12px 12px 0 0;">
        <div style="font-weight:700;font-size:13px;color:#0F172A;white-space:nowrap;
                    overflow:hidden;text-overflow:ellipsis;max-width:180px;margin-bottom:2px">
          ${addr}
        </div>
        <div style="font-size:10px;color:#94A3B8;font-weight:500">${type || '건물'}</div>
        <button onclick="window.__closeKakaoOverlay()"
          style="position:absolute;top:8px;right:10px;background:none;border:none;
                 cursor:pointer;font-size:16px;color:#94A3B8;line-height:1;padding:2px 4px">×</button>
      </div>
      <div style="padding:10px 14px;display:flex;flex-direction:column;gap:0;background:#fff;border-radius:0 0 12px 12px">
        ${row('⚡ 시스템 용량', cap != null ? `${cap.toFixed(1)} kW` : '—',  '#3B82F6')}
        ${row('🔆 연간 발전량', gen != null ? `${gen.toLocaleString()} kWh` : '—', '#10B981')}
        ${row('📅 회수 기간',   pay != null ? `${pay.toFixed(1)} 년` : '—',  '#64748B')}
      </div>
      <div style="
        position:absolute;bottom:-8px;left:50%;transform:translateX(-50%);
        width:14px;height:8px;overflow:hidden;
      ">
        <div style="
          width:10px;height:10px;background:#fff;border:1px solid #E2E8F0;
          transform:rotate(45deg);margin:-5px auto 0;
          box-shadow:2px 2px 4px rgba(0,0,0,0.08);
        "></div>
      </div>
    </div>`
}

export default function KakaoMap({ onAddressSelect, markerLatLng, markerResult }) {
  const containerRef = useRef(null)
  const mapRef       = useRef(null)
  const markerRef    = useRef(null)
  const overlayRef   = useRef(null)  // InfoWindow → CustomOverlay

  // 전역 닫기 함수 등록 (오버레이 버튼에서 호출)
  useEffect(() => {
    window.__closeKakaoOverlay = () => {
      if (overlayRef.current) {
        overlayRef.current.setMap(null)
        overlayRef.current = null
      }
    }
    return () => { delete window.__closeKakaoOverlay }
  }, [])

  useEffect(() => {
    loadKakaoScript().then(() => {
      if (!containerRef.current || mapRef.current) return
      const map = new window.kakao.maps.Map(containerRef.current, {
        center: new window.kakao.maps.LatLng(37.5665, 126.978),
        level:  5,
      })
      map.setMapTypeId(window.kakao.maps.MapTypeId.ROADMAP)
      mapRef.current = map

      window.kakao.maps.event.addListener(map, 'click', (e) => {
        placeMarker(map, e.latLng)
        reverseGeocode(e.latLng)
      })
    })
  }, [])

  useEffect(() => {
    if (!mapRef.current || !markerLatLng) return
    const latlng = new window.kakao.maps.LatLng(markerLatLng.lat, markerLatLng.lng)
    placeMarker(mapRef.current, latlng)
    mapRef.current.panTo(latlng)
  }, [markerLatLng])

  useEffect(() => {
    if (!mapRef.current || !markerRef.current || !markerResult) return

    // 기존 오버레이 제거
    if (overlayRef.current) { overlayRef.current.setMap(null); overlayRef.current = null }

    const s = markerResult.summary
    const content = buildOverlayContent({
      addr: s?.['주소'] || '',
      type: s?.['건물정보']?.['유형'] || '',
      cap:  s?.['태양광시스템']?.['총용량_kW'],
      gen:  s?.['태양광시스템']?.['연간발전량_kWh'],
      pay:  s?.['경제성']?.['단순회수기간_년'],
    })

    // InfoWindow 대신 CustomOverlay: 마커 좌표에 정확히 고정
    const overlay = new window.kakao.maps.CustomOverlay({
      position: markerRef.current.getPosition(),
      content,
      xAnchor: 0.5,   // 수평 중앙
      yAnchor: 1.35,  // 마커 위쪽 (1.0 = 정확히 마커 위치, >1 = 위로 올림)
      zIndex:  3,
    })
    overlay.setMap(mapRef.current)
    overlayRef.current = overlay
  }, [markerResult])

  function placeMarker(map, latlng) {
    if (markerRef.current) markerRef.current.setMap(null)
    if (overlayRef.current) { overlayRef.current.setMap(null); overlayRef.current = null }
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
      <div ref={containerRef} style={{ width: '100%', height: '100%' }} />
      <div className="map-hint">클릭으로 위치 선택</div>
    </div>
  )
}
