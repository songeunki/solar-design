import pytest
import warnings
from unittest.mock import patch, MagicMock

from data_collector.address_api import Location
from data_collector.building_api import (
    BuildingAPI, BuildingAPIError,
    _get_pnu, _pnu_via_juso, _pnu_via_kakao, _call_building_api, _parse_item, _fallback_info,
    BUILDING_TITLE_URL,
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
    @patch("data_collector.building_api._pnu_via_kakao")
    def test_kakao_success(self, mock_kakao):
        """Kakao 1차 성공 → PNU 바로 반환."""
        mock_kakao.return_value = PNU_19
        assert _get_pnu(SAMPLE_LOCATION.address) == PNU_19
        mock_kakao.assert_called_once_with(SAMPLE_LOCATION.address)

    @patch("data_collector.building_api._pnu_via_juso")
    @patch("data_collector.building_api._pnu_via_kakao")
    def test_juso_fallback(self, mock_kakao, mock_juso):
        """Kakao 실패 → Juso fallback."""
        mock_kakao.side_effect = BuildingAPIError("Kakao 실패")
        mock_juso.return_value = PNU_19

        assert _get_pnu(SAMPLE_LOCATION.address) == PNU_19
        mock_juso.assert_called_once_with(SAMPLE_LOCATION.address)

    @patch("data_collector.building_api._pnu_via_juso")
    @patch("data_collector.building_api._pnu_via_kakao")
    def test_both_fail_raises(self, mock_kakao, mock_juso):
        """Kakao + Juso 모두 실패 → BuildingAPIError."""
        mock_kakao.side_effect = BuildingAPIError("Kakao 실패")
        mock_juso.side_effect = BuildingAPIError("Juso 실패")

        with pytest.raises(BuildingAPIError):
            _get_pnu(SAMPLE_LOCATION.address)

    @patch("data_collector.building_api._pnu_via_juso")
    @patch("data_collector.building_api._pnu_via_kakao")
    def test_kakao_fail_juso_success(self, mock_kakao, mock_juso):
        """Kakao 실패 + Juso 성공 → Juso PNU 반환."""
        mock_kakao.side_effect = BuildingAPIError("키 없음")
        mock_juso.return_value = PNU_19

        assert _get_pnu("서울특별시 강남구 삼성동 169") == PNU_19

    @patch("data_collector.building_api._pnu_via_juso")
    @patch("data_collector.building_api._pnu_via_kakao")
    def test_vworld_http_error_kakao_fallback(self, mock_kakao, mock_juso):
        """Kakao 성공 → Juso 호출 없음."""
        mock_kakao.return_value = PNU_19

        assert _get_pnu(SAMPLE_LOCATION.address) == PNU_19
        mock_juso.assert_not_called()

    @patch("data_collector.building_api._pnu_via_juso")
    @patch("data_collector.building_api._pnu_via_kakao")
    def test_juso_fail_kakao_fallback(self, mock_kakao, mock_juso):
        """Kakao 실패 → Juso 호출."""
        mock_kakao.side_effect = BuildingAPIError("키 없음")
        mock_juso.return_value = PNU_19

        assert _get_pnu(SAMPLE_LOCATION.address) == PNU_19
        mock_juso.assert_called_once()


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

        with pytest.raises(BuildingAPIError, match="결과 없음"):
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


def _kakao_addr_resp(b_code="1168010500", mountain_yn="N",
                     main_no="0169", sub_no="0000") -> dict:
    return {
        "documents": [{
            "address": {
                "b_code": b_code,
                "mountain_yn": mountain_yn,
                "main_address_no": main_no,
                "sub_address_no": sub_no,
            }
        }]
    }


# ── _pnu_via_kakao ────────────────────────────────────────────────────────────

class TestPnuViaKakao:
    @patch("data_collector.building_api.requests.get")
    @patch("data_collector.building_api.KAKAO_REST_API_KEY", "test-key")
    def test_success(self, mock_get):
        """정상 응답 → 19자리 PNU 반환."""
        mock_get.return_value.raise_for_status = MagicMock()
        mock_get.return_value.json.return_value = _kakao_addr_resp()

        pnu = _pnu_via_kakao("서울특별시 강남구 삼성동 169")
        assert len(pnu) == 19
        assert pnu == "1168010500" + "0" + "0169" + "0000"

    @patch("data_collector.building_api.KAKAO_REST_API_KEY", "")
    def test_no_key_raises(self):
        """키 없으면 BuildingAPIError."""
        with pytest.raises(BuildingAPIError, match="KAKAO_REST_API_KEY"):
            _pnu_via_kakao("서울특별시 강남구 삼성동 169")

    @patch("data_collector.building_api.requests.get")
    @patch("data_collector.building_api.KAKAO_REST_API_KEY", "test-key")
    def test_empty_docs_raises(self, mock_get):
        """documents 빈 배열 → BuildingAPIError."""
        mock_get.return_value.raise_for_status = MagicMock()
        mock_get.return_value.json.return_value = {"documents": []}

        with pytest.raises(BuildingAPIError, match="결과 없음"):
            _pnu_via_kakao("없는주소")

    @patch("data_collector.building_api.requests.get")
    @patch("data_collector.building_api.KAKAO_REST_API_KEY", "test-key")
    def test_mountain_address(self, mock_get):
        """산 주소(mountain_yn=Y) → PNU 산여부 비트 1."""
        mock_get.return_value.raise_for_status = MagicMock()
        mock_get.return_value.json.return_value = _kakao_addr_resp(
            mountain_yn="Y", main_no="0042", sub_no="0000"
        )

        pnu = _pnu_via_kakao("산 주소 테스트")
        assert pnu[10] == "1"


# ── _call_building_api ────────────────────────────────────────────────────────

class TestCallBuildingApi:
    @patch("data_collector.building_api.requests.get")
    def test_success_returns_item(self, mock_get):
        mock_get.return_value.raise_for_status = MagicMock()
        mock_get.return_value.content = b"data"
        mock_get.return_value.json.return_value = _building_resp(SAMPLE_ITEM)

        item = _call_building_api(BUILDING_TITLE_URL, {"sigunguCd": "11680"})
        assert item["grndFlrCnt"] == 11

    @patch("data_collector.building_api.requests.get")
    def test_empty_response_raises(self, mock_get):
        mock_get.return_value.raise_for_status = MagicMock()
        mock_get.return_value.content = b""

        with pytest.raises(BuildingAPIError, match="비어 있음"):
            _call_building_api(BUILDING_TITLE_URL, {})

    @patch("data_collector.building_api.requests.get")
    def test_no_items_raises(self, mock_get):
        mock_get.return_value.raise_for_status = MagicMock()
        mock_get.return_value.content = b"data"
        mock_get.return_value.json.return_value = {
            "response": {"body": {"items": {"item": []}}}
        }

        with pytest.raises(BuildingAPIError, match="데이터 없음"):
            _call_building_api(BUILDING_TITLE_URL, {})


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
        messages = [str(x.message) for x in w]
        assert any("PNU 조회 실패" in m for m in messages)
