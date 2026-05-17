# Task 8: 3D 배치도 건물 모양 + 패널 방향 정밀화

## 현재 문제
1. 3D 건물이 직사각형 박스로만 표현됨 (실제 건물 모양과 다름)
2. 패널 배치 방향이 위성지도 실제 건물 방향과 불일치

## 작업 1: OSM 폴리곤 기반 실제 건물 모양 3D 렌더링

### 백엔드 (data_collector/building_api.py 수정)
OSM Overpass API로 건물 폴리곤 꼭짓점 좌표 가져오기:

```python
def get_building_polygon(lat: float, lng: float) -> dict:
    """OSM에서 건물 폴리곤 꼭짓점 좌표 조회"""
    overpass_url = "https://overpass-api.de/api/interpreter"
    query = f"""
    [out:json];
    way(around:30,{lat},{lng})["building"];
    out geom;
    """
    try:
        resp = requests.post(overpass_url, data={"data": query}, timeout=15)
        data = resp.json()
        elements = data.get("elements", [])
        
        if not elements:
            return {"polygon": None, "azimuth": None}
        
        # 가장 가까운 건물 선택
        building = elements[0]
        geometry = building.get("geometry", [])
        
        # 꼭짓점 좌표 목록
        vertices = [(g["lon"], g["lat"]) for g in geometry]
        
        # 장변 방위각 계산
        azimuth = calculate_building_azimuth(vertices)
        
        return {
            "polygon": vertices,
            "azimuth": azimuth,
            "osm_id": building.get("id")
        }
    except Exception as e:
        return {"polygon": None, "azimuth": None}

def calculate_building_azimuth(vertices: list) -> float:
    """건물 폴리곤에서 장변 방위각 계산"""
    if len(vertices) < 3:
        return 0.0
    
    max_length = 0
    azimuth = 0.0
    
    for i in range(len(vertices) - 1):
        x1, y1 = vertices[i]
        x2, y2 = vertices[i+1]
        
        dx = x2 - x1
        dy = y2 - y1
        length = math.sqrt(dx**2 + dy**2)
        
        if length > max_length:
            max_length = length
            # 방위각 계산 (북쪽 기준 시계방향)
            azimuth = math.degrees(math.atan2(dx, dy)) % 360
    
    return round(azimuth, 1)
```

### pipeline.py에 폴리곤 데이터 추가
```python
# building 정보 수집 후 폴리곤 추가
polygon_data = BuildingAPI().get_building_polygon(location["lat"], location["lng"])
building["polygon"] = polygon_data.get("polygon")
building["osm_azimuth"] = polygon_data.get("azimuth")
```

---

## 작업 2: PanelLayout3D.jsx - 실제 건물 모양 렌더링

### Three.js로 실제 폴리곤 모양 건물 생성

```javascript
// PanelLayout3D.jsx 핵심 수정

import * as THREE from 'three'

// 건물 폴리곤을 Three.js Shape으로 변환
function createBuildingFromPolygon(polygon, centerLat, centerLng) {
  if (!polygon || polygon.length < 3) {
    // 폴리곤 없으면 기존 직사각형 사용
    return createDefaultBuilding()
  }
  
  // 좌표 → 미터 변환 (중심점 기준 상대좌표)
  const metersPerDegLat = 111320
  const metersPerDegLng = 111320 * Math.cos(centerLat * Math.PI / 180)
  
  const points2D = polygon.map(([lng, lat]) => new THREE.Vector2(
    (lng - centerLng) * metersPerDegLng,
    (lat - centerLat) * metersPerDegLat
  ))
  
  const shape = new THREE.Shape(points2D)
  
  // ExtrudeGeometry로 3D 건물 생성
  const extrudeSettings = {
    depth: buildingHeight,  // 건물 높이
    bevelEnabled: false
  }
  
  const geometry = new THREE.ExtrudeGeometry(shape, extrudeSettings)
  const material = new THREE.MeshLambertMaterial({
    color: 0x2A3F5F,
    transparent: true,
    opacity: 0.85
  })
  
  return new THREE.Mesh(geometry, material)
}

// 패널 배치도 방위각 적용
function placePanelsOnRoof(polygon, azimuth, panelWidth, panelHeight, rows, cols) {
  const panels = []
  const rad = (azimuth * Math.PI) / 180
  
  // 건물 중심 계산
  const centerX = polygon.reduce((s, [x]) => s + x, 0) / polygon.length
  const centerY = polygon.reduce((s, [, y]) => s + y, 0) / polygon.length
  
  // 방위각 기준으로 패널 그리드 생성
  for (let r = 0; r < rows; r++) {
    for (let c = 0; c < cols; c++) {
      // 방위각 회전 적용
      const localX = (c - cols/2) * (panelWidth + 0.1)
      const localY = (r - rows/2) * (panelHeight + 0.5)
      
      const worldX = localX * Math.cos(rad) - localY * Math.sin(rad) + centerX
      const worldY = localX * Math.sin(rad) + localY * Math.cos(rad) + centerY
      
      panels.push({ x: worldX, y: worldY, rotation: azimuth })
    }
  }
  
  return panels
}
```

### 위성지도 배경 텍스처 정렬
```javascript
// 위성지도 텍스처를 건물 중심으로 정렬
const KAKAO_STATIC_MAP = `https://sapi.kakao.com/v2/maps/staticmap?appkey=${KAKAO_KEY}&center=${lng},${lat}&level=1&size=512x512&maptype=satellite`

// Three.js 평면에 텍스처 적용
const loader = new THREE.TextureLoader()
loader.load(KAKAO_STATIC_MAP, (texture) => {
  const planeGeo = new THREE.PlaneGeometry(50, 50)
  const planeMat = new THREE.MeshBasicMaterial({ map: texture })
  const plane = new THREE.Mesh(planeGeo, planeMat)
  plane.rotation.x = -Math.PI / 2
  scene.add(plane)
})
```

---

## 작업 3: 2D 패널 배치도도 동일한 방위각 적용 (PanelLayoutViewer.jsx)

```javascript
// 건물 방위각 기준으로 패널 SVG 회전
const azimuthRad = (azimuth * Math.PI) / 180

// SVG transform으로 전체 패널 그룹 회전
<g transform={`rotate(${azimuth}, ${centerX}, ${centerY})`}>
  {panels.map((panel, i) => (
    <rect key={i}
      x={panel.x} y={panel.y}
      width={panelW} height={panelH}
      fill="#1E6FD9" opacity={0.8}
      stroke="#fff" strokeWidth={0.5}
    />
  ))}
</g>
```

---

## 데이터 흐름 요약
```
주소 입력
  → Kakao/VWorld 좌표 변환
  → OSM Overpass API → 건물 폴리곤 + 장변 방위각
  → pipeline.py → building.polygon, building.osm_azimuth
  → PanelLayout3D.jsx → ExtrudeGeometry(폴리곤) + 패널 방위각 회전
  → PanelLayoutViewer.jsx → SVG 패널 방위각 회전
```

## 주의사항
- OSM에 건물 폴리곤이 없는 경우 기존 직사각형 폴백 유지
- 건물 좌표 → Three.js 좌표 변환 시 스케일 조정 필요 (너무 크거나 작지 않게)
- 위성지도 배경과 3D 건물 크기/위치 일치 확인

git add -A && git commit -m "feat: OSM 폴리곤 기반 3D 건물 모양 + 패널 방위각 정밀화" && git push origin master
