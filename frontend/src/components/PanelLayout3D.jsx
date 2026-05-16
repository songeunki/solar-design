/**
 * PanelLayout3D — Three.js 3D 태양광 패널 배치 뷰어 (v2)
 *
 * 개선사항:
 *   1. 경사 지붕: tilt_deg 기반 실제 3D 경사면 + 패널 경사면 배치
 *   2. 나침반 오버레이: 카메라 회전 추적, azimuth 빨간 화살표
 *   3. 위성 지면 텍스처: /satellite-map API 호출, 실패 시 회색 폴백
 *
 * 좌표계 (Three.js):
 *   X = 동(+) / 서(-)
 *   Y = 위(+)
 *   Z = 남(+) / 북(-)    ← 패널 lat→dz 변환과 일치
 */
import { useEffect, useRef, useState, useCallback } from 'react';
import * as THREE from 'three';
import { OrbitControls } from 'three/examples/jsm/controls/OrbitControls.js';
import { getSolarPosition, MONTH_LABELS, SIM_MONTHS } from '../utils/solar.js';

const DEG          = Math.PI / 180;
const M_PER_DEG_LAT = 111320;

const SUN_COLORS = [0xffd4a0, 0xffeecc, 0xfffbe6, 0xffeebb]; // Jan·Apr·Jul·Oct

export default function PanelLayout3D({ layout, building = {}, lat = 37.5 }) {
  const containerRef  = useRef(null);
  const compassRef    = useRef(null);    // SVG compass DOM
  const sunLightRef   = useRef(null);
  const sunSphereRef  = useRef(null);
  const animIdRef     = useRef(null);
  const groundRef     = useRef(null);
  const cameraRef     = useRef(null);
  const controlsRef   = useRef(null);

  const [monthIdx,   setMonthIdx]   = useState(0);
  const [hourSlider, setHourSlider] = useState(0);

  if (!layout?.panels?.length) return null;

  const {
    panels, roof_polygon,
    panel_w_deg_lng: pw_deg,
    panel_h_deg_lat: ph_deg,
    stats,
    center_lat, center_lng,
  } = layout;

  const tiltDeg     = stats.tilt_deg    ?? 30;
  const azimuthDeg  = stats.azimuth_deg ?? 180;
  const tiltRad     = tiltDeg * DEG;
  const mPerDegLng  = M_PER_DEG_LAT * Math.cos(lat * DEG);

  const bFloors  = building.floor || 3;
  const bAreaM2  = building.area  || 200;
  const D        = Math.sqrt(bAreaM2);   // 건물 한 변 (m)
  const bH       = bFloors * 3.0;        // 건물 높이 (m)
  const rise     = D * Math.tan(tiltRad); // 지붕 남북 고저차

  // ── 태양 위치 → 조명 업데이트 ──────────────────────────────────────────
  const updateSun = useCallback((mIdx, hour) => {
    const sun    = sunLightRef.current;
    const sphere = sunSphereRef.current;
    if (!sun || !sphere) return;

    const { elevation, azimuth } = getSolarPosition(lat, SIM_MONTHS[mIdx], hour);
    if (elevation <= 0) { sun.intensity = 0.05; return; }

    const R     = 120;
    const el    = elevation * DEG;
    const az    = azimuth   * DEG;

    // Three.js 좌표계: Z=남(+), Z=북(-), X=동(+)
    // 방위각 0=북(-Z), 90=동(+X), 180=남(+Z), 270=서(-X)
    const sx =  Math.sin(az) * Math.cos(el) * R;   // 동서
    const sy =  Math.sin(el) * R;                   // 고도
    const sz = -Math.cos(az) * Math.cos(el) * R;   // 남북 (북=-)

    sun.position.set(sx, sy, sz);
    sphere.position.set(sx, sy, sz);
    sun.intensity = 0.35 + (elevation / 90) * 0.9;
    sun.color.setHex(SUN_COLORS[mIdx]);
  }, [lat]);

  // ── Three.js 씬 초기화 ──────────────────────────────────────────────────
  useEffect(() => {
    if (!containerRef.current) return;
    const W = containerRef.current.clientWidth  || 620;
    const H = 480;

    // ── Renderer ───────────────────────────────────────────────────────
    const renderer = new THREE.WebGLRenderer({ antialias: true });
    renderer.setSize(W, H);
    renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
    renderer.shadowMap.enabled = true;
    renderer.shadowMap.type    = THREE.PCFSoftShadowMap;
    renderer.setClearColor(0xddeeff, 1);
    containerRef.current.appendChild(renderer.domElement);

    // ── Scene ──────────────────────────────────────────────────────────
    const scene = new THREE.Scene();
    scene.fog   = new THREE.FogExp2(0xd4e3f5, 0.006);

    // ── Camera ─────────────────────────────────────────────────────────
    const camera = new THREE.PerspectiveCamera(55, W / H, 0.1, 1000);
    camera.position.set(D * 1.1, bH + 18, D * 1.6);
    camera.lookAt(0, bH * 0.5, 0);
    cameraRef.current = camera;

    // ── OrbitControls ──────────────────────────────────────────────────
    const controls = new OrbitControls(camera, renderer.domElement);
    controls.target.set(0, bH * 0.4, 0);
    controls.enableDamping  = true;
    controls.dampingFactor  = 0.08;
    controls.minDistance    = 8;
    controls.maxDistance    = 250;
    controls.maxPolarAngle  = Math.PI / 2 - 0.04;
    controlsRef.current = controls;

    // ── 지면 (위성 텍스처 또는 회색) ──────────────────────────────────
    const groundSize = D * 4;
    const groundGeo  = new THREE.PlaneGeometry(groundSize, groundSize);
    const groundMat  = new THREE.MeshLambertMaterial({ color: 0xa8c090 });
    const groundMesh = new THREE.Mesh(groundGeo, groundMat);
    groundMesh.rotation.x = -Math.PI / 2;
    groundMesh.receiveShadow = true;
    scene.add(groundMesh);
    groundRef.current = groundMesh;

    // 위성 텍스처 비동기 로드 (실패해도 회색으로 폴백)
    const loader = new THREE.TextureLoader();
    loader.load(
      `/satellite-map?lat=${center_lat}&lng=${center_lng}&level=2`,
      (tex) => {
        if (!groundRef.current) return;
        groundRef.current.material.map         = tex;
        groundRef.current.material.color.set(0xffffff);
        groundRef.current.material.needsUpdate = true;
      },
      undefined,
      () => { /* 실패 시 회색 유지 */ }
    );

    // 그리드
    const grid = new THREE.GridHelper(groundSize, 40, 0x9baabb, 0x9baabb);
    grid.material.opacity     = 0.2;
    grid.material.transparent = true;
    scene.add(grid);

    // ── 건물 본체 ──────────────────────────────────────────────────────
    const bldGeo  = new THREE.BoxGeometry(D, bH, D);
    const bldMat  = new THREE.MeshLambertMaterial({ color: 0xc8d4e0 });
    const bldMesh = new THREE.Mesh(bldGeo, bldMat);
    bldMesh.position.y  = bH / 2;
    bldMesh.castShadow  = true;
    bldMesh.receiveShadow = true;
    scene.add(bldMesh);

    // 건물 엣지
    const edgesGeo = new THREE.EdgesGeometry(bldGeo);
    const edgeMat  = new THREE.LineBasicMaterial({ color: 0x8899aa, transparent: true, opacity: 0.4 });
    const edgeLine = new THREE.LineSegments(edgesGeo, edgeMat);
    edgeLine.position.y = bH / 2;
    scene.add(edgeLine);

    // ── 경사 지붕 (BufferGeometry로 4 꼭짓점) ─────────────────────────
    // 좌표계: Z+=남(낮음), Z-=북(높음)
    // azimuth_deg 회전은 지붕 그룹에 적용
    const roofVerts = new Float32Array([
      -D/2, bH,       +D/2,   // SW (남쪽 낮음)
      +D/2, bH,       +D/2,   // SE
      +D/2, bH + rise, -D/2,  // NE (북쪽 높음)
      -D/2, bH + rise, -D/2,  // NW
    ]);
    const roofIdx = new Uint16Array([0, 1, 2,  0, 2, 3]);
    const roofGeo = new THREE.BufferGeometry();
    roofGeo.setAttribute('position', new THREE.BufferAttribute(roofVerts, 3));
    roofGeo.setIndex(new THREE.BufferAttribute(roofIdx, 1));
    roofGeo.computeVertexNormals();

    // UV (위성 텍스처 미적용, 단색)
    const roofMat  = new THREE.MeshLambertMaterial({ color: 0x8899aa, side: THREE.FrontSide });
    const roofMesh = new THREE.Mesh(roofGeo, roofMat);
    roofMesh.castShadow    = true;
    roofMesh.receiveShadow = true;

    // azimuth 방향으로 지붕 그룹 회전
    // 기본 남향(azimuth=180°) 이미 적용됨, 다른 방위이면 Y축 회전
    const roofGroup = new THREE.Group();
    roofGroup.add(roofMesh);
    // azimuth: 0=북, 90=동, 180=남, 270=서
    // 남향 기본이 맞으므로, 차이만큼 Y 회전
    roofGroup.rotation.y = -(azimuthDeg - 180) * DEG;
    scene.add(roofGroup);

    // 지붕 능선 (하이라이트)
    const ridgeGeo = new THREE.BufferGeometry().setFromPoints([
      new THREE.Vector3(-D/2, bH + rise, -D/2),
      new THREE.Vector3(+D/2, bH + rise, -D/2),
    ]);
    scene.add(new THREE.Line(ridgeGeo, new THREE.LineBasicMaterial({ color: 0x667788 })));

    // ── 패널 (경사면 위에 배치) ────────────────────────────────────────
    const THICK  = 0.05;
    const panelGeo = new THREE.BoxGeometry(stats.panel_w_m || 1.134, THICK, stats.panel_h_m || 2.094);
    const matActive = new THREE.MeshPhongMaterial({
      color: 0x1a56c4, specular: 0x4499ff, shininess: 90,
      transparent: true, opacity: 0.88,
    });
    const matShade = new THREE.MeshPhongMaterial({
      color: 0xff6b35, specular: 0xff9966, shininess: 40,
      transparent: true, opacity: 0.78,
    });

    panels.forEach((p) => {
      const dx = (p.lng + pw_deg / 2 - center_lng) * mPerDegLng;
      // Z=남(+), Z=북(-): 위도가 크면(북) → dz 음수
      const dz = -((p.lat + ph_deg / 2 - center_lat) * M_PER_DEG_LAT);

      // 경사면의 Y 높이 계산
      // Z=+D/2(남,낮음)=bH, Z=-D/2(북,높음)=bH+rise
      // roofY(dz) = bH + rise * (0.5 - dz/D)
      const roofY = bH + rise * (0.5 - dz / D);

      const mat  = p.status === 'shade' ? matShade : matActive;
      const mesh = new THREE.Mesh(panelGeo, mat);

      // 패널 중심 위치: 경사면 위 (THICK/2 올림)
      mesh.position.set(dx, roofY + THICK / 2, dz);
      // 경사면과 같은 각도로 기울이기 (남향 경사: X축으로 tiltRad 회전)
      mesh.rotation.x = tiltRad;

      mesh.castShadow    = true;
      mesh.receiveShadow = true;
      scene.add(mesh);
    });

    // ── 조명 ───────────────────────────────────────────────────────────
    scene.add(new THREE.AmbientLight(0xffffff, 0.4));
    scene.add(new THREE.HemisphereLight(0xcce0ff, 0x88aa44, 0.3));

    const sun = new THREE.DirectionalLight(0xfffbe6, 1.0);
    sun.castShadow = true;
    sun.shadow.mapSize.set(1024, 1024);
    const sc = D * 3;
    Object.assign(sun.shadow.camera, { near: 1, far: 400, left: -sc, right: sc, top: sc, bottom: -sc });
    scene.add(sun);
    sunLightRef.current = sun;

    // 태양 시각화 구
    const sunSphere = new THREE.Mesh(
      new THREE.SphereGeometry(2.5, 12, 12),
      new THREE.MeshBasicMaterial({ color: 0xffdd44 })
    );
    scene.add(sunSphere);
    sunSphereRef.current = sunSphere;

    updateSun(0, 0);

    // ── 애니메이션 + 나침반 업데이트 ───────────────────────────────────
    const _dir = new THREE.Vector3();
    const animate = () => {
      animIdRef.current = requestAnimationFrame(animate);
      controls.update();

      // 나침반: 카메라 수평 방향 → 회전각
      camera.getWorldDirection(_dir);
      // Z-=북, X+=동 → azimuth from north: atan2(X, -Z)
      const camAzRad = Math.atan2(_dir.x, -_dir.z);
      if (compassRef.current) {
        // rose를 반시계로 camAzimuth만큼 회전 → 북 표시가 항상 올바른 방향
        compassRef.current.style.transform = `rotate(${-camAzRad * 180 / Math.PI}deg)`;
      }

      renderer.render(scene, camera);
    };
    animate();

    // 리사이즈
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
      if (containerRef.current?.contains(renderer.domElement)) {
        containerRef.current.removeChild(renderer.domElement);
      }
    };
  }, []); // 최초 1회

  // 태양 위치 업데이트
  useEffect(() => { updateSun(monthIdx, hourSlider); }, [monthIdx, hourSlider, updateSun]);

  const { elevation } = getSolarPosition(lat, SIM_MONTHS[monthIdx], hourSlider);
  const hourLabel = hourSlider === 0 ? '정오' : `정오 ${hourSlider > 0 ? '+' : ''}${hourSlider}h`;

  // ── 나침반 SVG ─────────────────────────────────────────────────────────
  // rose div는 camera azimuth에 따라 CSS transform으로 회전
  // azimuth_deg 화살표는 rose 안에서 고정 방향으로 그림
  const azArrowAngle = azimuthDeg; // 0=북→위, 180=남→아래
  const compassSize  = 88;
  const cx = compassSize / 2, cy = compassSize / 2, r = 36;
  const azRad = azArrowAngle * DEG;
  // SVG에서: 북=위(y-), 동=오른쪽(x+)
  const arrowX = cx + r * 0.72 * Math.sin(azRad);
  const arrowY = cy - r * 0.72 * Math.cos(azRad);

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
      {/* 컨트롤 패널 */}
      <div style={{
        display: 'flex', gap: 14, flexWrap: 'wrap', alignItems: 'center',
        padding: '10px 16px', background: 'var(--bg)',
        borderRadius: 10, border: '1px solid var(--border)',
      }}>
        {/* 월 선택 */}
        <div style={{ display: 'flex', gap: 6, alignItems: 'center' }}>
          <span style={{ fontSize: 12, fontWeight: 600, color: 'var(--text-muted)' }}>월:</span>
          {SIM_MONTHS.map((m, i) => (
            <button key={m} onClick={() => setMonthIdx(i)} style={{
              padding: '4px 10px', borderRadius: 6, border: 'none', cursor: 'pointer',
              fontWeight: 600, fontSize: 12,
              background: monthIdx === i ? '#f59e0b' : 'white',
              color:      monthIdx === i ? 'white' : 'var(--text-secondary)',
              boxShadow: '0 1px 3px rgba(0,0,0,0.1)',
            }}>{MONTH_LABELS[m]}</button>
          ))}
        </div>

        {/* 시간 슬라이더 */}
        <div style={{ display: 'flex', alignItems: 'center', gap: 10, flex: 1, minWidth: 220 }}>
          <span style={{ fontSize: 12, fontWeight: 600, color: 'var(--text-muted)', whiteSpace: 'nowrap' }}>시각:</span>
          <input type="range" min="-4" max="4" step="0.5"
            value={hourSlider}
            onChange={(e) => setHourSlider(parseFloat(e.target.value))}
            style={{ flex: 1, accentColor: '#f59e0b' }}
          />
          <span style={{ fontSize: 12, fontWeight: 700, color: '#f59e0b', minWidth: 68, textAlign: 'right' }}>
            {hourLabel}
          </span>
        </div>

        {/* 정보 */}
        <div style={{ display: 'flex', gap: 12 }}>
          <div style={{ fontSize: 12, color: elevation > 0 ? '#1E6FD9' : '#a0aec0', fontWeight: 600 }}>
            ☀ {elevation > 0 ? `고도 ${elevation.toFixed(1)}°` : '야간'}
          </div>
          <div style={{ fontSize: 12, color: 'var(--text-muted)' }}>
            경사 {tiltDeg}° · 방위 {azimuthDeg}°
          </div>
        </div>
      </div>

      {/* Three.js 캔버스 + 나침반 오버레이 */}
      <div style={{ position: 'relative' }}>
        <div
          ref={containerRef}
          style={{ width: '100%', height: 480, borderRadius: 10, overflow: 'hidden', border: '1px solid var(--border)' }}
        />

        {/* 나침반 오버레이 (우하단) */}
        <div style={{
          position: 'absolute', bottom: 14, right: 14, zIndex: 10,
          filter: 'drop-shadow(0 2px 6px rgba(0,0,0,0.3))',
        }}>
          {/* 배경 원 */}
          <svg width={compassSize} height={compassSize} viewBox={`0 0 ${compassSize} ${compassSize}`}>
            <circle cx={cx} cy={cy} r={r + 4} fill="rgba(255,255,255,0.88)" stroke="#e2e8f0" strokeWidth="1.5" />
          </svg>

          {/* 회전하는 나침반 로즈 (카메라 방향에 따라 CSS rotate) */}
          <div
            ref={compassRef}
            style={{
              position: 'absolute', top: 0, left: 0,
              width: compassSize, height: compassSize,
              transition: 'transform 0.05s linear',
            }}
          >
            <svg width={compassSize} height={compassSize} viewBox={`0 0 ${compassSize} ${compassSize}`}>
              {/* 눈금 (8방위) */}
              {[0,45,90,135,180,225,270,315].map(a => {
                const ar = a * DEG;
                return <line key={a}
                  x1={cx + (r-8) * Math.sin(ar)} y1={cy - (r-8) * Math.cos(ar)}
                  x2={cx + r     * Math.sin(ar)} y2={cy - r     * Math.cos(ar)}
                  stroke={a % 90 === 0 ? '#64748b' : '#cbd5e1'} strokeWidth={a % 90 === 0 ? 2 : 1}
                />;
              })}

              {/* N/S/E/W 레이블 */}
              {[
                { label: 'N', a: 0,   color: '#1E6FD9', fw: 800 },
                { label: 'E', a: 90,  color: '#475569', fw: 600 },
                { label: 'S', a: 180, color: '#475569', fw: 600 },
                { label: 'W', a: 270, color: '#475569', fw: 600 },
              ].map(({ label, a, color, fw }) => {
                const ar = a * DEG;
                return <text key={label}
                  x={cx + (r-16) * Math.sin(ar)} y={cy - (r-16) * Math.cos(ar) + 4}
                  textAnchor="middle" fontSize="11" fontWeight={fw} fill={color}
                >{label}</text>;
              })}

              {/* 방위각 화살표 (빨강) — rose와 함께 회전 → 절대 방향 고정 */}
              <line
                x1={cx} y1={cy}
                x2={arrowX} y2={arrowY}
                stroke="#dc2626" strokeWidth="2.5" strokeLinecap="round"
              />
              <circle cx={arrowX} cy={arrowY} r="3" fill="#dc2626" />
            </svg>
          </div>

          {/* 중심 점 (고정) */}
          <div style={{
            position: 'absolute', top: cy - 4, left: cx - 4,
            width: 8, height: 8, borderRadius: '50%',
            background: '#1E6FD9', border: '2px solid white',
          }} />

          {/* 방위각 레이블 */}
          <div style={{
            position: 'absolute', bottom: -18, left: '50%', transform: 'translateX(-50%)',
            fontSize: 9, fontWeight: 600, color: '#dc2626', whiteSpace: 'nowrap',
          }}>
            설치방위 {azimuthDeg}°
          </div>
        </div>
      </div>

      {/* 조작 안내 */}
      <div style={{ fontSize: 11, color: 'var(--text-muted)', textAlign: 'center' }}>
        🖱 드래그: 회전 &nbsp;|&nbsp; 휠: 줌 &nbsp;|&nbsp; 우클릭 드래그: 이동 &nbsp;|&nbsp;
        🔴 빨간 화살표 = 패널 방위 ({azimuthDeg}° = {azimuthDeg === 180 ? '남향' : azimuthDeg < 180 ? '남동향' : '남서향'})
      </div>
    </div>
  );
}
