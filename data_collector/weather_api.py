import urllib.request
import urllib.parse
import json
from dataclasses import dataclass
from data_collector.address_api import Location

NASA_POWER_URL = "https://power.larc.nasa.gov/api/temporal/climatology/point"

_MONTH_KEYS = ["JAN", "FEB", "MAR", "APR", "MAY", "JUN",
               "JUL", "AUG", "SEP", "OCT", "NOV", "DEC"]
_DAYS_IN_MONTH = [31, 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31]


@dataclass
class SolarData:
    annual_irradiance_kwh_m2: float     # 연간 수평면 일사량
    peak_sun_hours: float               # 일평균 피크일조시간 (h/day)
    monthly_irradiance: list[float]     # 월별 일사량 (12개월)
    avg_temp_c: float                   # 연평균 기온


class WeatherAPIError(Exception):
    pass


class WeatherAPI:
    """NASA POWER API로 위치별 일사량·기온 climatology 수집 (API 키 불필요)"""

    def get_solar_irradiance(self, location: Location) -> SolarData:
        params = urllib.parse.urlencode({
            "parameters": "ALLSKY_SFC_SW_DWN,T2M",
            "community": "RE",
            "longitude": location.lng,
            "latitude": location.lat,
            "format": "JSON",
        })
        try:
            with urllib.request.urlopen(f"{NASA_POWER_URL}?{params}", timeout=20) as resp:
                data = json.loads(resp.read().decode("utf-8"))
        except Exception as e:
            raise WeatherAPIError(f"NASA POWER API 호출 실패: {e}") from e

        param_data = data.get("properties", {}).get("parameter", {})
        irr = param_data.get("ALLSKY_SFC_SW_DWN", {})
        temp = param_data.get("T2M", {})

        if not irr or not temp:
            raise WeatherAPIError("NASA POWER 응답에 일사량/기온 데이터가 없습니다.")

        # 월별 일사량: 일평균(kWh/m²/day) × 해당 월 일수 = 월 합계(kWh/m²)
        monthly = [irr[m] * d for m, d in zip(_MONTH_KEYS, _DAYS_IN_MONTH)]
        annual = sum(monthly)

        return SolarData(
            annual_irradiance_kwh_m2=round(annual, 1),
            peak_sun_hours=round(irr.get("ANN", annual / 365), 2),
            monthly_irradiance=[round(v, 1) for v in monthly],
            avg_temp_c=round(temp.get("ANN", 0.0), 1),
        )
