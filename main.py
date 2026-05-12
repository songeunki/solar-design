"""
태양광 설계 자동화 메인 진입점
사용법:
  python main.py --address "서울시 강남구 ..."
  python main.py --compare "주소1" "주소2" ...
"""

import argparse
from data_collector.address_api import AddressAPI
from data_collector.building_api import BuildingAPI
from data_collector.weather_api import WeatherAPI
from analyzer.roof_analyzer import RoofAnalyzer
from designer.electrical import ElectricalDesigner
from designer.structural import StructuralDesigner
from output.report_generator import ReportGenerator, ComparisonReportGenerator


def _pipeline(address: str) -> dict:
    """단일 주소에 대해 전체 파이프라인을 실행하고 결과 dict 반환."""
    location  = AddressAPI().get_coordinates(address)
    building  = BuildingAPI().get_building_info(location)
    weather   = WeatherAPI().get_solar_irradiance(location)
    roof      = RoofAnalyzer().analyze(building)
    electrical = ElectricalDesigner().design(roof, weather)
    structural = StructuralDesigner().design(roof, electrical)
    return dict(
        address=address,
        building=building,
        roof=roof,
        electrical=electrical,
        structural=structural,
    )


def run(address: str) -> None:
    print(f"[1/5] 주소 조회: {address}")
    print("[2/5] 건물 정보 수집")
    print("[3/5] 기상 데이터 수집")
    print("[4/5] 지붕 분석 및 설계")
    result = _pipeline(address)

    print("[5/5] 보고서 생성")
    report = ReportGenerator().generate(
        result["address"], result["building"], result["roof"],
        result["electrical"], result["structural"],
    )
    print(f"HTML: {report.file_path}")
    if report.pdf_path:
        print(f"PDF : {report.pdf_path}")


def run_compare(addresses: list[str]) -> None:
    results = []
    total = len(addresses)
    for i, address in enumerate(addresses, 1):
        print(f"\n[{i}/{total}] {address}")
        try:
            r = _pipeline(address)
            e = r["electrical"]
            print(f"       → {e.panel_count}장 / {e.total_capacity_kw} kWp"
                  f" / {e.annual_generation_kwh:,} kWh/년")
            results.append(r)
        except Exception as exc:
            print(f"       [오류] {exc}")

    if len(results) < 2:
        print("\n비교 보고서 생성에는 정상 조회된 주소가 최소 2개 필요합니다.")
        return

    print("\n[비교 보고서 생성]")
    report = ComparisonReportGenerator().generate(results)
    print(f"HTML: {report.file_path}")
    if report.pdf_path:
        print(f"PDF : {report.pdf_path}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="태양광 설계 자동화")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--address", help="단일 주소 설계")
    group.add_argument(
        "--compare", nargs="+", metavar="ADDRESS",
        help='비교할 주소 목록 (각 주소를 따옴표로 감싸서 전달)',
    )
    args = parser.parse_args()

    if args.address:
        run(args.address)
    else:
        run_compare(args.compare)
