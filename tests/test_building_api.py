import pytest
import warnings
from unittest.mock import patch, MagicMock

from data_collector.address_api import Location
from data_collector.building_api import (
    BuildingAPI, BuildingAPIError,
    _get_pnu, _pnu_via_juso, _call_building_api, _parse_item, _fallback_info,
)

SAMPLE_LOCATION = Location(
    address="서울특별시 강남구 삼성동 169",
    lat=37.510, lng=127.064,
    sido="서울특별시", sigungu="강남구",
)

SAMPLE_ITEM = {
    "mainPurpsCdNm": "업무시설",
    "grndFlrCnt": 11,
    "archArea": 1108.93,
    "roofCdNm": "(철근)콘크리트",
    "strctCdNm": "철근콘크리트구조",
    "totArea": 17260.67,
    "ugrndFlrCnt": 4,
}

PNU_19 = "1168010500100690000"  # 19자리 샘플 PNU


def _vworld_pnu_resp(pnu: str = PNU_19) -> dict:
    return {
        "response": {
            "status": "OK",
            "refined": {"structure": {"level4LC": pnu}},
        }
    }


def _juso_resp(bd_mgt_sn: str = PNU_19 + "000000") -> dict:
    return {
        "results": {
            "common": {"errorCode": "0", "errorMessage": "정상"},
            "juso": [{"bdMgtSn": bd_mgt_sn}],
        }
    }


def _building_resp(item: dict = None) -> dict:
    return {
        "response": {
            "body": {"items": {"item": item or SAMPLE_ITEM}}
        }
    }


# ── _get_pnu ─────────────────────────────────────────────────────────────────

class TestGetPnu:
    @patch("data_collector.building_api.requests.get")
    def test_road_success(self, mock_get):
        """road 타입에서 바로 19자리 PNU 반환."""
        mock_get.return_value.raise_for_status = MagicMock()
        mock_get.return_value.json.return_value = _vworld_pnu_resp(PNU_19)

        assert _get_pnu(SAMPLE_LOCATION) == PNU_19
        assert mock_get.call_count == 1

    @patch("data_collector.building_api.requests.get")
    def test_parcel_fallback(self, mock_get):
        """road level4LC 없음 → parcel fallback 성공."""
        mock_get.return_value.raise_for_status = MagicMock()
        mock_get.return_value.json.side_effect = [
            _vworld_pnu_resp(""),          # road: level4LC 비어있음
            _vworld_pnu_resp(PNU_19),      # parcel: 성공
        ]

        assert _get_pnu(SAMPLE_LOCATION) == PNU_19

    @patch("data_collector.building_api._pnu_via_juso")
    @patch("data_collector.building_api.requests.get")
    def test_juso_fallback(self, mock_get, mock_juso):
        """VWorld 모두 실패 → Juso API fallback."""
        mock_get.return_value.raise_for_status = MagicMock()
        mock_get.return_value.json.return_value = _vworld_pnu_resp("")
        mock_juso.return_value = PNU_19

        assert _get_pnu(SAMPLE_LOCATION) == PNU_19
        mock_juso.assert_called_once_with(SAMPLE_LOCATION.address)


# ── _pnu_via_juso ─────────────────────────────────────────────────────────────

class TestPnuViaJuso:
    @patch("data_collector.building_api.requests.get")
    @patch("data_collector.building_api.JUSO_API_KEY", "test-key")
    def test_success(self, mock_get):
        mock_get.return_value.raise_for_status = MagicMock()
        mock_get.return_value.json.return_value = _juso_resp(PNU_19 + "000000")

        assert _pnu_via_juso("서울특별시 강남구 테헤란로 521") == PNU_19

    @patch("data_collector.building_api.JUSO_API_KEY", "")
    def test_no_key_raises(self):
        with pytest.raises(BuildingAPIError, match="JUSO_API_KEY"):
            _pnu_via_juso("서울특별시 강남구 테헤란로 521")

    @patch("data_collector.building_api.requests.get")
    @patch("data_collector.building_api.JUSO_API_KEY", "test-key")
    def test_empty_result_raises(self, mock_get):
        mock_get.return_value.raise_for_status = MagicMock()
        mock_get.return_value.json.return_value = {
            "results": {"common": {"errorCode": "0"}, "juso": []}
        }

        with pytest.raises(BuildingAPIError, match="주소를 찾을 수 없습니다"):
            _pnu_via_juso("없는주소")

    @patch("data_collector.building_api.requests.get")
    @patch("data_collector.building_api.JUSO_API_KEY", "test-key")
    def test_api_error_code_raises(self, mock_get):
        mock_get.return_value.raise_for_status = MagicMock()
        mock_get.return_value.json.return_value = {
            "results": {"common": {"errorCode": "E0001", "errorMessage": "인증 오류"}}
        }

        with pytest.raises(BuildingAPIError, match="Juso API 오류"):
            _pnu_via_juso("서울특별시 강남구 테헤란로 521")


# ── _call_building_api ────────────────────────────────────────────────────────

class TestCallBuildingApi:
    @patch("data_collector.building_api.requests.get")
    def test_success_returns_item(self, mock_get):
        mock_get.return_value.raise_for_status = MagicMock()
        mock_get.return_value.content = b"data"
        mock_get.return_value.json.return_value = _building_resp(SAMPLE_ITEM)

        item = _call_building_api({"sigunguCd": "11680"})
        assert item["grndFlrCnt"] == 11

    @patch("data_collector.building_api.requests.get")
    def test_empty_response_raises(self, mock_get):
        mock_get.return_value.raise_for_status = MagicMock()
        mock_get.return_value.content = b""

        with pytest.raises(BuildingAPIError, match="비어 있습니다"):
            _call_building_api({})

    @patch("data_collector.building_api.requests.get")
    def test_no_items_raises(self, mock_get):
        mock_get.return_value.raise_for_status = MagicMock()
        mock_get.return_value.content = b"data"
        mock_get.return_value.json.return_value = {
            "response": {"body": {"items": {"item": []}}}
        }

        with pytest.raises(BuildingAPIError, match="건물 정보를 찾을 수 없습니다"):
            _call_building_api({})


# ── _parse_item ───────────────────────────────────────────────────────────────

class TestParseItem:
    def test_business_building(self):
        info = _parse_item("서울특별시 강남구 삼성동 169", SAMPLE_ITEM)

        assert info.building_type == "상업"
        assert info.floors == 11
        assert info.roof_area_m2 == pytest.approx(1108.93)
        assert info.roof_type == "평지붕"
        assert info.roof_slope_deg == 0.0
        assert info.structure == "철근콘크리트구조"
        assert info.extra["purpose"] == "업무시설"
        assert info.extra["underground_floors"] == 4

    def test_sloped_roof(self):
        item = {**SAMPLE_ITEM, "roofCdNm": "경사지붕"}
        info = _parse_item("주소", item)

        assert info.roof_type == "경사지붕"
        assert info.roof_slope_deg == 30.0

    def test_unknown_purpose_defaults_to_기타(self):
        item = {**SAMPLE_ITEM, "mainPurpsCdNm": "기타시설"}
        info = _parse_item("주소", item)

        assert info.building_type == "기타"

    def test_missing_floor_defaults_to_1(self):
        item = {**SAMPLE_ITEM, "grndFlrCnt": None}
        info = _parse_item("주소", item)

        assert info.floors == 1


# ── BuildingAPI (통합) ────────────────────────────────────────────────────────

class TestBuildingAPI:
    @patch("data_collector.building_api._fetch_building_item")
    @patch("data_collector.building_api._get_pnu")
    def test_success_path(self, mock_pnu, mock_fetch):
        mock_pnu.return_value = PNU_19
        mock_fetch.return_value = SAMPLE_ITEM

        info = BuildingAPI().get_building_info(SAMPLE_LOCATION)

        assert info.floors == 11
        assert info.building_type == "상업"

    @patch("data_collector.building_api._get_pnu")
    def test_fallback_on_error(self, mock_pnu):
        mock_pnu.side_effect = BuildingAPIError("PNU 추출 실패")

        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            info = BuildingAPI().get_building_info(SAMPLE_LOCATION)

        assert info.extra.get("fallback") is True
        assert len(w) == 1
        assert "기본값으로 대체" in str(w[0].message)
