"""파이프라인 공통 로직 — routers에서 재사용."""
from __future__ import annotations
import pathlib
from typing import Callable

# (step, total, message)
ProgressCb = Callable[[int, int, str], None]

_MONTHS_KR = ["1월","2월","3월","4월","5월","6월","7월","8월","9월","10월","11월","12월"]

# 월별 태양 적위 근사값 (1~12월, 도)
_MONTHLY_DECLINATIONS = [-23.1, -17.3, -8.4, 2.2, 11.9, 20.0, 23.4, 20.4, 12.1, 1.8, -8.8, -18.8]


def _calc_solar_altitude(lat: float) -> list[float]:
    """위도로 월별 최대 태양 고도각 계산. 공식: 90 - |위도 - 적위|"""
    return [round(90 - abs(lat - dec), 1) for dec in _MONTHLY_DECLINATIONS]


def _to_url(path: str | None) -> str | None:
    """절대 파일 경로 → FastAPI /files 정적 서빙 URL로 변환."""
    if not path:
        return None
    return f"/files/{pathlib.Path(path).name}"


def run_pipeline(
    address: str,
    on_progress: ProgressCb | None = None,
    azimuth_override: float | None = None,
) -> dict:
    """단일 주소 전체 파이프라인 실행. 동기 함수 (ThreadPoolExecutor로 호출).

    azimuth_override: 사용자 직접 입력 방위각(°). None이면 OSM 자동 계산값 사용.
    """
    from data_collector.address_api import AddressAPI
    from data_collector.building_api import BuildingAPI
    from data_collector.weather_api import WeatherAPI
    from analyzer.roof_analyzer import RoofAnalyzer
    from designer.electrical import ElectricalDesigner
    from designer.structural import StructuralDesigner
    from output.report_generator import ReportGenerator

    def p(step: int, msg: str) -> None:
        if on_progress:
            on_progress(step, 6, msg)

    p(1, "주소 조회")
    location = AddressAPI().get_coordinates(address)

    p(2, "건물 정보 수집")
    building = BuildingAPI().get_building_info(location)

    p(3, "기상 데이터 수집")
    weather = WeatherAPI().get_solar_irradiance(location)

    p(4, "지붕 분석 및 설계")
    roof       = RoofAnalyzer().analyze(building)
    electrical = ElectricalDesigner().design(roof, weather)
    structural = StructuralDesigner().design(roof, electrical)

    p(5, "보고서 생성 및 규제 분석")
    solar_altitude_deg = _calc_solar_altitude(location.lat)

    # 패널 배치 계산 (직사각형 근사)
    from analyzer.panel_layout import PanelLayoutEngine

    roof_shape   = building.extra.get("roof_shape", "flat")
    arch_area_m2 = building.extra.get("arch_area_m2") or building.roof_area_m2

    # azimuth: 사용자 override > OSM 자동 계산
    effective_azimuth = azimuth_override if azimuth_override is not None else roof.azimuth_deg
    azimuth_source    = "override" if azimuth_override is not None else "osm"

    # OSM 실측 건물 치수 (없으면 None → panel_layout이 추정)
    osm_ew_m = building.extra.get("building_ew_m")
    osm_ns_m = building.extra.get("building_ns_m")

    # OSM polygon → [{"lat":..., "lng":...}] 형식으로 변환 (저장 형식은 [[lon, lat], ...])
    raw_polygon = building.extra.get("osm_polygon")  # [[lon, lat], ...]
    roof_polygon_dicts = (
        [{"lat": c[1], "lng": c[0]} for c in raw_polygon]
        if raw_polygon else None
    )

    panel_layout = PanelLayoutEngine().compute(
        lat=location.lat,
        lng=location.lng,
        usable_area_m2=roof.usable_area_m2,
        tilt_deg=roof.tilt_deg,
        sun_elevation_winter_deg=roof.solar_elevations.get("동지", 29.4),
        annual_generation_kwh=electrical.annual_generation_kwh,
        azimuth_deg=effective_azimuth,
        arch_area_m2=arch_area_m2,
        roof_shape=roof_shape,
        target_panel_count=electrical.panel_count,
        osm_building_ew_m=osm_ew_m,
        osm_building_ns_m=osm_ns_m,
        roof_polygon=roof_polygon_dicts,
    )

    report = ReportGenerator().generate(
        address, building, roof, electrical, structural,
        lat=location.lat, lng=location.lng,
        monthly_irradiance=weather.monthly_irradiance,
        solar_altitude_deg=solar_altitude_deg,
        panel_layout=panel_layout.to_dict(),
    )

    # 경제성 (report_generator와 동일한 계산값 재사용)
    ec             = report.summary.get("경제성", {})
    install_cost   = ec.get("예상설치비_만원", 0) * 10_000      # 원
    yearly_revenue = round(ec.get("연간절감액_만원", 0) * 10_000)  # 원/년
    rec_revenue    = round(ec.get("연간REC수익_만원", 0) * 10_000)  # 원/년
    payback_year   = ec.get("단순회수기간_년", 0)
    net_profit_20y = round((yearly_revenue + rec_revenue) * 20 - install_cost)

    html_url = _to_url(report.file_path)
    pdf_url  = _to_url(report.pdf_path)

    p(6, "규제 분석")
    regulation = None
    try:
        from data_collector.regulation_api import RegulationAPI
        _pnu     = building.extra.get("pnu")
        _purpose = building.extra.get("purpose", "")
        regulation = RegulationAPI().fetch(address, pnu=_pnu, building_purpose=_purpose).to_dict()
    except Exception:
        pass

    solar_check: dict = {}
    try:
        from data_collector.solar_check import check_existing_solar
        solar_check = check_existing_solar(location.lat, location.lng)
    except Exception:
        pass

    return {
        # 보고서 원본
        "summary":   report.summary,
        "html_path": html_url,
        "pdf_path":  pdf_url,
        "lat":       location.lat,
        "lng":       location.lng,
        # ResultCards용 구조화 필드
        "building": {
            "address":       address,
            "floor":         building.floors,
            "area":          building.extra.get("total_floor_area_m2") or building.roof_area_m2,
            "archArea":      arch_area_m2,
            "roofType":      building.roof_type,
            "roofShape":     roof_shape,
            "azimuth":       effective_azimuth,
            "azimuthSource": azimuth_source,
            "structure":     building.structure or "",
            "purpose":       building.extra.get("purpose", ""),
            "irradiation":   round(sum(weather.monthly_irradiance), 1),
            "polygon":       building.extra.get("osm_polygon"),  # [[lon, lat], ...] or None
        },
        "system": {
            "panelCount":   electrical.panel_count,
            "totalKw":      electrical.total_capacity_kw,
            "inverterKw":   electrical.inverter_capacity_kw,
            "monthlyAvg":   round(electrical.annual_generation_kwh / 12),
            "yearlyTotal":  electrical.annual_generation_kwh,
            "stringConfig": electrical.string_config,
            "co2Year":      ec.get("연간CO2저감_kg", 0),
        },
        "financial": {
            "installCost":   install_cost,
            "yearlyRevenue": yearly_revenue,
            "recRevenue":    rec_revenue,
            "paybackYear":   payback_year,
            "netProfit20y":  net_profit_20y,
        },
        "monthly_data": [
            {
                "month":          _MONTHS_KR[i],
                "kwh":            electrical.monthly_generation_kwh[i],
                "irradiation":    weather.monthly_irradiance[i],
                "solar_altitude": solar_altitude_deg[i],
            }
            for i in range(12)
        ],
        "report_url":   html_url,
        "pdf_url":      pdf_url,
        "panel_layout": panel_layout.to_dict(),
        "regulation":   regulation,
        "solar_check":  solar_check,
    }


def run_compare_pipeline(
    addresses: list[str],
    on_progress: ProgressCb | None = None,
) -> dict:
    """복수 주소 비교 파이프라인 실행."""
    from data_collector.address_api import AddressAPI
    from data_collector.building_api import BuildingAPI
    from data_collector.weather_api import WeatherAPI
    from analyzer.roof_analyzer import RoofAnalyzer
    from designer.electrical import ElectricalDesigner
    from designer.structural import StructuralDesigner
    from output.report_generator import ComparisonReportGenerator, ReportGenerator

    n       = len(addresses)
    # 전체 스텝: 건물당 5단계 + 비교보고서 1단계
    total   = n * 5 + 1
    current = 0

    def p(msg: str) -> None:
        nonlocal current
        current += 1
        if on_progress:
            on_progress(current, total, msg)

    raw_for_report = []   # ComparisonReportGenerator용 도메인 객체
    formatted      = []   # 프론트엔드 표시용 구조화 데이터

    for i, address in enumerate(addresses, 1):
        prefix = f"[{i}/{n}] {address[:20]}"

        p(f"{prefix} — 주소 조회")
        location = AddressAPI().get_coordinates(address)

        p(f"{prefix} — 건물 정보 수집")
        building = BuildingAPI().get_building_info(location)

        p(f"{prefix} — 기상 데이터 수집")
        weather = WeatherAPI().get_solar_irradiance(location)

        p(f"{prefix} — 지붕 분석 및 설계")
        roof       = RoofAnalyzer().analyze(building)
        electrical = ElectricalDesigner().design(roof, weather)
        structural = StructuralDesigner().design(roof, electrical)

        p(f"{prefix} — 보고서 생성")
        solar_altitude_deg = _calc_solar_altitude(location.lat)
        report = ReportGenerator().generate(
            address, building, roof, electrical, structural,
            lat=location.lat, lng=location.lng,
            monthly_irradiance=weather.monthly_irradiance,
            solar_altitude_deg=solar_altitude_deg,
        )

        ec             = report.summary.get("경제성", {})
        install_cost   = ec.get("예상설치비_만원", 0) * 10_000
        yearly_revenue = round(ec.get("연간절감액_만원", 0) * 10_000)
        rec_revenue    = round(ec.get("연간REC수익_만원", 0) * 10_000)
        payback_year   = ec.get("단순회수기간_년", 0)
        net_profit_20y = round((yearly_revenue + rec_revenue) * 20 - install_cost)

        raw_for_report.append(dict(
            address=address, building=building, roof=roof,
            electrical=electrical, structural=structural,
        ))
        formatted.append({
            "address": address,
            "building": {
                "address":     address,
                "floor":       building.floors,
                "archArea":    building.extra.get("arch_area_m2") or building.roof_area_m2,
                "roofType":    building.roof_type,
                "purpose":     building.extra.get("purpose", ""),
                "irradiation": round(sum(weather.monthly_irradiance), 1),
            },
            "system": {
                "panelCount":  electrical.panel_count,
                "totalKw":     electrical.total_capacity_kw,
                "inverterKw":  electrical.inverter_capacity_kw,
                "yearlyTotal": electrical.annual_generation_kwh,
                "monthlyAvg":  round(electrical.annual_generation_kwh / 12),
            },
            "financial": {
                "installCost":   install_cost,
                "yearlyRevenue": yearly_revenue,
                "recRevenue":    rec_revenue,
                "paybackYear":   payback_year,
                "netProfit20y":  net_profit_20y,
            },
            "monthly_data": [
                {
                    "month":          _MONTHS_KR[j],
                    "kwh":            electrical.monthly_generation_kwh[j],
                    "irradiation":    weather.monthly_irradiance[j],
                    "solar_altitude": solar_altitude_deg[j],
                }
                for j in range(12)
            ],
            "report_url": _to_url(report.file_path),
            "pdf_url":    _to_url(report.pdf_path),
        })

    p("비교 보고서 생성")
    compare_report = ComparisonReportGenerator().generate(raw_for_report)

    return {
        "results":     formatted,
        "compare_url": _to_url(compare_report.file_path),
    }
