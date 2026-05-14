import { useEffect, useRef } from 'react'

const APP_KEY = import.meta.env.VITE_KAKAO_JS_APP_KEY || '1a26482813f863a4da8896cde91a820e'

function loadKakaoScript() {
  return new Promise((resolve) => {
    if (window.kakao?.maps) {
      window.kakao.maps.load(resolve)
      return
    }
    if (document.getElementById('kakao-map-sdk')) {
      const interval = setInterval(() => {
        if (window.kakao?.maps) {
          clearInterval(interval)
          window.kakao.maps.load(resolve)
        }
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

function buildInfoContent({ addr, type, cap, gen, pay }) {
  const row = (label, value, color = '#64748B') => `
    <div style="display:flex;justify-content:space-between;align-items:center;gap:20px;padding:4px 0;border-bottom:1px solid #f1f5f910">
      <span style="color:#94A3B8;font-size:11px">${label}</span>
      <strong style="color:${color};font-size:12px;font-weight:600">${value}</strong>
    </div>`

  return `
    <div style="
      font-family:'IBM Plex Sans',system-ui,sans-serif;
      background:#0C1222;
      color:#F1F5F9;
      border:1px solid rgba(59,130,246,0.25);
      border-radius:12px;
      overflow:hidden;
      min-width:220px;
      box-shadow:0 8px 32px rgba(0,0,0,0.5);
    ">
      <div style="padding:12px 14px;border-bottom:1px solid rgba(255,255,255,0.06);background:rgba(59,130,246,0.06)">
        <div style="font-weight:700;font-size:13px;color:#F1F5F9;margin-bottom:2px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;max-width:200px">
          ${addr}
        </div>
        <div style="font-size:10px;color:#64748B;font-weight:500;letter-spacing:0.3px">${type || '건물'}</div>
      </div>
      <div style="padding:10px 14px;display:flex;flex-direction:column;gap:0">
        ${row('⚡ 시스템 용량', cap != null ? `${cap.toFixed(1)} kW` : '—', '#60A5FA')}
        ${row('🔆 연간 발전량', gen != null ? `${gen.toLocaleString()} kWh` : '—', '#34D399')}
        ${row('📅 회수 기간',   pay != null ? `${pay.toFixed(1)} 년`   : '—', '#94A3B8')}
      </div>
    </div>`
}

export default function KakaoMap({ onAddressSelect, markerLatLng, markerResult }) {
  const containerRef  = useRef(null)
  const mapRef        = useRef(null)
  const markerRef     = useRef(null)
  const infoWindowRef = useRef(null)

  useEffect(() => {
    loadKakaoScript().then(() => {
      if (!containerRef.current || mapRef.current) return
      const map = new window.kakao.maps.Map(containerRef.current, {
        center: new window.kakao.maps.LatLng(37.5665, 126.978),
        level:  5,
      })
      // 기본 밝은 지도 스타일 명시 (다크 테마 오염 방지)
      map.setMapTypeId(window.kakao.maps.MapTypeId.ROADMAP)
      mapRef.current = map

      window.kakao.maps.event.addListener(map, 'click', (e) => {
        const latlng = e.latLng
        placeMarker(map, latlng)
        reverseGeocode(latlng)
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
    if (infoWindowRef.current) {
      infoWindowRef.current.close()
      infoWindowRef.current = null
    }

    const s = markerResult.summary
    const content = buildInfoContent({
      addr: s?.['주소'] || '',
      type: s?.['건물정보']?.['유형'] || '',
      cap:  s?.['태양광시스템']?.['총용량_kW'],
      gen:  s?.['태양광시스템']?.['연간발전량_kWh'],
      pay:  s?.['경제성']?.['단순회수기간_년'],
    })

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
      <div ref={containerRef} style={{ width: '100%', height: '100%' }} />
      <div className="map-hint">클릭으로 위치 선택</div>
    </div>
  )
}
