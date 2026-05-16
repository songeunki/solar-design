/**
 * PanelLayout3D — Three.js 3D 태양광 패널 배치 뷰어
 * props:
 *   layout   - panel_layout 객체
 *   building - { floor, area }
 *   lat      - 건물 위도
 */
import { useEffect, useRef, useState, useCallback } from 'react';
import * as THREE from 'three';
import { OrbitControls } from 'three/examples/jsm/controls/OrbitControls.js';
import { getSolarPosition, MONTH_LABELS, SIM_MONTHS } from '../utils/solar.js';

const DEG = Math.PI / 180;
const M_PER_DEG_LAT = 111320;

// 계절별 태양광 색온도
const SUN_COLOR_BY_MONTH = [0xffd4a0, 0xffeecc, 0xfffbe6, 0xffeebb];

export default function PanelLayout3D({ layout, building = {}, lat = 37.5 }) {
  const containerRef = useRef(null);
  const sceneRef     = useRef(null);
  const rendererRef  = useRef(null);
  const cameraRef    = useRef(null);
  const controlsRef  = useRef(null);
  const sunLightRef  = useRef(null);
  const sunSphereRef = useRef(null);
  const animIdRef    = useRef(null);

  const [monthIdx,  setMonthIdx]  = useState(0);  // SIM_MONTHS index
  const [hourSlider, setHourSlider] = useState(0); // -4 ~ +4 (태양시)

  if (!layout?.panels?.length) return null;

  const { panels, panel_w_deg_lng: pw_deg, panel_h_deg_lat: ph_deg, stats, center_lat, center_lng } = layout;

  const buildingFloors = building.floor || 3;
  const buildingAreaM2 = building.area  || layout.stats?.panel_h_m * layout.stats?.col_count * 14 || 200;
  const buildingSideM  = Math.sqrt(buildingAreaM2);
  const buildingH      = buildingFloors * 3.0;
  const tiltDeg        = stats.tilt_deg;

  const mPerDegLng = M_PER_DEG_LAT * Math.cos(lat * DEG);
  const panelW_m   = stats.panel_w_m || 1.134;
  const panelH_m   = stats.panel_h_m || 2.094;

  // 태양 위치 → Three.js 조명 위치
  const updateSunPosition = useCallback((mIdx, hour) => {
    const sun = sunLightRef.current;
    const sphere = sunSphereRef.current;
    if (!sun || !sphere) return;

    const { elevation, azimuth } = getSolarPosition(lat, SIM_MONTHS[mIdx], hour);
    if (elevation < 0) {
      sun.intensity = 0.1;
      return;
    }

    const R    = 120;
    const elRad = elevation * DEG;
    const azRad = azimuth   * DEG;

    // Three.js: X=East, Y=Up, Z=North
    // azimuth: 0=North → Z=+; 90=East → X=+; 180=South → Z=-; 270=West → X=-
    const sx =  Math.sin(azRad) * Math.cos(elRad) * R;
    const sy =  Math.sin(elRad) * R;
    const sz =  Math.cos(azRad) * Math.cos(elRad) * R;

    sun.position.set(sx, sy, sz);
    sphere.position.set(sx, sy, sz);
    sun.intensity = 0.4 + (elevation / 90) * 0.9;
  }, [lat]);

  // ── Three.js 씬 초기화 ──────────────────────────────────────────────────
  useEffect(() => {
    if (!containerRef.current) return;
    const W = containerRef.current.clientWidth || 620;
    const H = 460;

    // Renderer
    const renderer = new THREE.WebGLRenderer({ antialias: true, alpha: true });
    renderer.setSize(W, H);
    renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
    renderer.shadowMap.enabled = true;
    renderer.shadowMap.type = THREE.PCFSoftShadowMap;
    renderer.setClearColor(0xf0f4ff, 1);
    containerRef.current.appendChild(renderer.domElement);
    rendererRef.current = renderer;

    // Scene
    const scene = new THREE.Scene();
    scene.fog = new THREE.FogExp2(0xd4e3f5, 0.008);
    sceneRef.current = scene;

    // Camera
    const camera = new THREE.PerspectiveCamera(55, W / H, 0.1, 1000);
    camera.position.set(buildingSideM * 1.2, buildingH + 20, buildingSideM * 1.5);
    camera.lookAt(0, buildingH, 0);
    cameraRef.current = camera;

    // OrbitControls
    const controls = new OrbitControls(camera, renderer.domElement);
    controls.target.set(0, buildingH * 0.5, 0);
    controls.enableDamping = true;
    controls.dampingFactor = 0.08;
    controls.minDistance = 10;
    controls.maxDistance = 200;
    controls.maxPolarAngle = Math.PI / 2 - 0.05;
    controlsRef.current = controls;

    // ── 지면 ──────────────────────────────────────────────────────────────
    const groundGeo = new THREE.PlaneGeometry(300, 300);
    const groundMat = new THREE.MeshLambertMaterial({ color: 0xc8d8a0 });
    const ground = new THREE.Mesh(groundGeo, groundMat);
    ground.rotation.x = -Math.PI / 2;
    ground.receiveShadow = true;
    scene.add(ground);

    // 그리드
    const grid = new THREE.GridHelper(300, 60, 0xaabbcc, 0xaabbcc);
    grid.material.opacity = 0.3;
    grid.material.transparent = true;
    scene.add(grid);

    // ── 건물 본체 ──────────────────────────────────────────────────────────
    const bldMat = new THREE.MeshLambertMaterial({ color: 0xd0d8e8 });
    const bldGeo = new THREE.BoxGeometry(buildingSideM, buildingH, buildingSideM);
    const bldMesh = new THREE.Mesh(bldGeo, bldMat);
    bldMesh.position.y = buildingH / 2;
    bldMesh.castShadow = true;
    bldMesh.receiveShadow = true;
    scene.add(bldMesh);

    // 건물 엣지
    const edges = new THREE.EdgesGeometry(bldGeo);
    const lineMat = new THREE.LineBasicMaterial({ color: 0x8899aa, opacity: 0.5, transparent: true });
    scene.add(new THREE.LineSegments(edges, lineMat).translateY(buildingH / 2));

    // ── 옥상 ──────────────────────────────────────────────────────────────
    const roofGeo = new THREE.PlaneGeometry(buildingSideM, buildingSideM);
    const roofMat = new THREE.MeshLambertMaterial({ color: 0xb0bcc8, side: THREE.DoubleSide });
    const roofMesh = new THREE.Mesh(roofGeo, roofMat);
    roofMesh.rotation.x = -Math.PI / 2;
    roofMesh.position.y = buildingH + 0.02;
    roofMesh.receiveShadow = true;
    scene.add(roofMesh);

    // ── 패널 ──────────────────────────────────────────────────────────────
    const PANEL_THICKNESS = 0.05;
    const panelGeoBase = new THREE.BoxGeometry(panelW_m, PANEL_THICKNESS, panelH_m);
    const matActive = new THREE.MeshPhongMaterial({
      color: 0x1E6FD9, specular: 0x4499ff, shininess: 80,
      transparent: true, opacity: 0.85,
    });
    const matShade = new THREE.MeshPhongMaterial({
      color: 0xff6b35, specular: 0xff9966, shininess: 40,
      transparent: true, opacity: 0.75,
    });

    // 패널 기울기 (남향, 경사각)
    const tiltRad = tiltDeg * DEG;

    panels.forEach((p) => {
      // 위경도 → 미터 오프셋
      const dx = (p.lng + pw_deg / 2 - center_lng) * mPerDegLng;
      const dz = -((p.lat + ph_deg / 2 - center_lat) * M_PER_DEG_LAT); // Z=-남, Z=+북 → north=+Z

      const mat = p.status === 'shade' ? matShade : matActive;
      const mesh = new THREE.Mesh(panelGeoBase, mat);

      // 패널 위치: 옥상 위 + 경사 때문에 중심이 약간 올라감
      const halfH = panelH_m / 2;
      mesh.position.set(
        dx,
        buildingH + PANEL_THICKNESS / 2 + halfH * Math.sin(tiltRad),
        dz + halfH * Math.cos(tiltRad) * 0.5
      );
      // 경사각 적용 (south-facing: north edge up → rotate around +X)
      mesh.rotation.x = tiltRad;

      mesh.castShadow    = true;
      mesh.receiveShadow = true;
      scene.add(mesh);
    });

    // ── 조명 ──────────────────────────────────────────────────────────────
    const ambient = new THREE.AmbientLight(0xffffff, 0.45);
    scene.add(ambient);

    const hemi = new THREE.HemisphereLight(0xd4eaf5, 0x7ab648, 0.3);
    scene.add(hemi);

    const sun = new THREE.DirectionalLight(SUN_COLOR_BY_MONTH[monthIdx], 1.0);
    sun.castShadow = true;
    sun.shadow.mapSize.set(1024, 1024);
    sun.shadow.camera.near = 1;
    sun.shadow.camera.far  = 400;
    const sc = buildingSideM * 2;
    sun.shadow.camera.left = -sc; sun.shadow.camera.right = sc;
    sun.shadow.camera.top  =  sc; sun.shadow.camera.bottom = -sc;
    scene.add(sun);
    sunLightRef.current = sun;

    // 태양 구 (시각화)
    const sunGeo    = new THREE.SphereGeometry(3, 16, 16);
    const sunMat    = new THREE.MeshBasicMaterial({ color: 0xffdd44 });
    const sunSphere = new THREE.Mesh(sunGeo, sunMat);
    scene.add(sunSphere);
    sunSphereRef.current = sunSphere;

    updateSunPosition(0, 0);

    // ── 애니메이션 루프 ────────────────────────────────────────────────────
    const animate = () => {
      animIdRef.current = requestAnimationFrame(animate);
      controls.update();
      renderer.render(scene, camera);
    };
    animate();

    // ── 리사이즈 ──────────────────────────────────────────────────────────
    const onResize = () => {
      if (!containerRef.current) return;
      const w = containerRef.current.clientWidth;
      camera.aspect = w / H;
      camera.updateProjectionMatrix();
      renderer.setSize(w, H);
    };
    window.addEventListener('resize', onResize);

    return () => {
      window.removeEventListener('resize', onResize);
      cancelAnimationFrame(animIdRef.current);
      controls.dispose();
      renderer.dispose();
      if (containerRef.current && renderer.domElement.parentNode === containerRef.current) {
        containerRef.current.removeChild(renderer.domElement);
      }
    };
  }, []); // 최초 1회만

  // 태양 위치 업데이트 (슬라이더/월 변경 시)
  useEffect(() => {
    updateSunPosition(monthIdx, hourSlider);
    if (sunLightRef.current) {
      sunLightRef.current.color.setHex(SUN_COLOR_BY_MONTH[monthIdx]);
    }
  }, [monthIdx, hourSlider, updateSunPosition]);

  const hourLabel = hourSlider === 0 ? '정오' : `정오 ${hourSlider > 0 ? '+' : ''}${hourSlider}h`;
  const { elevation } = getSolarPosition(lat, SIM_MONTHS[monthIdx], hourSlider);

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>
      {/* 컨트롤 */}
      <div style={{ display: 'flex', gap: 16, flexWrap: 'wrap', alignItems: 'center', padding: '12px 20px', background: 'var(--bg)', borderRadius: 10, border: '1px solid var(--border)' }}>
        {/* 월 선택 */}
        <div style={{ display: 'flex', gap: 6, alignItems: 'center' }}>
          <span style={{ fontSize: 12, fontWeight: 600, color: 'var(--text-muted)' }}>월:</span>
          {SIM_MONTHS.map((m, i) => (
            <button key={m} onClick={() => setMonthIdx(i)} style={{
              padding: '4px 10px', borderRadius: 6, border: 'none', cursor: 'pointer',
              fontWeight: 600, fontSize: 12,
              background: monthIdx === i ? '#f59e0b' : 'white',
              color: monthIdx === i ? 'white' : 'var(--text-secondary)',
              boxShadow: '0 1px 3px rgba(0,0,0,0.1)',
            }}>
              {MONTH_LABELS[m]}
            </button>
          ))}
        </div>

        {/* 시간 슬라이더 */}
        <div style={{ display: 'flex', alignItems: 'center', gap: 10, flex: 1, minWidth: 240 }}>
          <span style={{ fontSize: 12, fontWeight: 600, color: 'var(--text-muted)', whiteSpace: 'nowrap' }}>시각:</span>
          <input
            type="range" min="-4" max="4" step="0.5"
            value={hourSlider}
            onChange={(e) => setHourSlider(parseFloat(e.target.value))}
            style={{ flex: 1, accentColor: '#f59e0b' }}
          />
          <span style={{ fontSize: 12, fontWeight: 700, color: '#f59e0b', minWidth: 72, textAlign: 'right' }}>
            {hourLabel}
          </span>
        </div>

        {/* 태양 고도각 표시 */}
        <div style={{ fontSize: 12, color: elevation > 0 ? '#1E6FD9' : '#a0aec0', fontWeight: 600, whiteSpace: 'nowrap' }}>
          ☀ {elevation > 0 ? `고도각 ${elevation.toFixed(1)}°` : '야간'}
        </div>
      </div>

      {/* Three.js 캔버스 */}
      <div
        ref={containerRef}
        style={{ width: '100%', height: 460, borderRadius: 10, overflow: 'hidden', border: '1px solid var(--border)', background: '#f0f4ff' }}
      />

      {/* 조작 안내 */}
      <div style={{ fontSize: 11, color: 'var(--text-muted)', textAlign: 'center' }}>
        🖱 드래그: 회전 &nbsp;|&nbsp; 휠: 줌 &nbsp;|&nbsp; 우클릭 드래그: 이동 &nbsp;|&nbsp; 슬라이더로 태양 위치 조정
      </div>
    </div>
  );
}
