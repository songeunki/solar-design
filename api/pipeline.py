"""파이프라인 공통 로직 — routers에서 재사용."""
from __future__ import annotations
from typing import Callable

# (step, total, message)
ProgressCb = Callable[[int, int, str], None]

_MONTHS_KR = ["1월","2월","3월","4월","5월","6월","7월","8월","9월","10월","11월","12월"]


def run_pipeline(address: str, on_progress: ProgressCb | None = None) -> dict:
    """단일 주소 전체 파이프라인 실행. 동기 함수 (ThreadPoolExecutor로 호출)."""
    from data_collector.address_api import AddressAPI
    from data_collector.building_api import BuildingAPI
    from data_collector.weather_api import WeatherAPI
    from analyzer.roof_analyzer import RoofAnalyzer
    from designer.electrical import ElectricalDesigner
    from designer.structural import StructuralDesigner
    from output.report_generator import ReportGenerator

    def p(step: int, msg: str) -> None:
        if on_progress:
            on_progress(step, 5, msg)

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

    p(5, "보고서 생성")
    report = ReportGenerator().generate(
        address, building, roof, electrical, structural,
        lat=location.lat, lng=location.lng,
    )

    # 경제성 (report_generator와 동일한 계산값 재사용)
    ec             = report.summary.get("경제성", {})
    install_cost   = ec.get("예상설치비_만원", 0) * 10_000      # 원
    yearly_revenue = round(ec.get("연간절감액_만원", 0) * 10_000)  # 원/년
    payback_year   = ec.get("단순회수기간_년", 0)
    net_profit_20y = round(yearly_revenue * 20 - install_cost)

    return {
        # 보고서 원본
        "summary":   report.summary,
        "html_path": report.file_path,
        "pdf_path":  report.pdf_path,
        "lat":       location.lat,
        "lng":       location.lng,
        # ResultCards용 구조화 필드
        "building": {
            "address":  address,
            "floor":    building.floors,
            "area":     building.extra.get("total_floor_area_m2") or building.roof_area_m2,
            "roofType": building.roof_type,
        },
        "system": {
            "panelCount":  electrical.panel_count,
            "totalKw":     electrical.total_capacity_kw,
            "inverterKw":  electrical.inverter_capacity_kw,
            "monthlyAvg":  round(electrical.annual_generation_kwh / 12),
            "yearlyTotal": electrical.annual_generation_kwh,
        },
        "financial": {
            "installCost":   install_cost,
            "yearlyRevenue": yearly_revenue,
            "paybackYear":   payback_year,
            "netProfit20y":  net_profit_20y,
        },
        "monthly_data": [
            {
                "month":       _MONTHS_KR[i],
                "kwh":         electrical.monthly_generation_kwh[i],
                "irradiation": weather.monthly_irradiance[i],
            }
            for i in range(12)
        ],
        "report_url": report.file_path,
        "pdf_url":    report.pdf_path,
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
    from output.report_generator import ComparisonReportGenerator

    n       = len(addresses)
    # 전체 스텝: 건물당 5단계 + 비교보고서 1단계
    total   = n * 5 + 1
    current = 0

    def p(msg: str) -> None:
        nonlocal current
        current += 1
        if on_progress:
            on_progress(current, total, msg)

    results = []
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
        results.append(dict(
            address=address, building=building, roof=roof,
            electrical=electrical, structural=structural,
        ))

    p("비교 보고서 생성")
    report = ComparisonReportGenerator().generate(results)

    return {
        "html_path": report.file_path,
        "addresses": report.addresses,
    }
