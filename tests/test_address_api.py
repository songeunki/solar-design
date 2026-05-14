import pytest
from unittest.mock import patch, MagicMock
from requests.exceptions import ConnectionError, HTTPError

from data_collector.address_api import AddressAPI, AddressAPIError, _parse_sido_sigungu


def _ok_response(lat: str = "37.509", lng: str = "127.060") -> dict:
    return {
        "response": {
            "status": "OK",
            "result": {"point": {"y": lat, "x": lng}},
        }
    }


NOT_FOUND = {"response": {"status": "NOT_FOUND"}}


class TestParseSidoSigungu:
    def test_full_address(self):
        sido, sigungu = _parse_sido_sigungu("서울특별시 강남구 삼성동 169")
        assert sido == "서울특별시"
        assert sigungu == "강남구"

    def test_single_token(self):
        sido, sigungu = _parse_sido_sigungu("서울특별시")
        assert sido == "서울특별시"
        assert sigungu == ""

    def test_empty_string(self):
        sido, sigungu = _parse_sido_sigungu("")
        assert sido == ""
        assert sigungu == ""


class TestAddressAPI:
    @patch("data_collector.address_api.requests.get")
    def test_road_address_success(self, mock_get):
        """도로명 주소 → road 타입 첫 시도에서 성공."""
        mock_get.return_value.json.return_value = _ok_response("37.509", "127.060")
        mock_get.return_value.raise_for_status = MagicMock()

        loc = AddressAPI().get_coordinates("서울특별시 강남구 테헤란로 521")

        assert loc.lat == pytest.approx(37.509)
        assert loc.lng == pytest.approx(127.060)
        assert loc.sido == "서울특별시"
        assert loc.sigungu == "강남구"
        assert mock_get.call_count == 1  # road 첫 시도에서 바로 성공

    @patch("data_collector.address_api.requests.get")
    def test_parcel_fallback(self, mock_get):
        """road NOT_FOUND → parcel fallback 성공."""
        mock_get.return_value.raise_for_status = MagicMock()
        mock_get.return_value.json.side_effect = [
            NOT_FOUND,
            _ok_response("37.510", "127.064"),
        ]

        loc = AddressAPI().get_coordinates("서울특별시 강남구 삼성동 169")

        assert loc.lat == pytest.approx(37.510)
        assert mock_get.call_count == 2

    @patch("data_collector.address_api.requests.get")
    def test_both_fail_raises(self, mock_get):
        """VWorld NOT_FOUND + Kakao 문서 없음 → AddressAPIError."""
        mock_get.return_value.raise_for_status = MagicMock()
        # VWorld: NOT_FOUND, Kakao: documents 없음
        mock_get.return_value.json.return_value = NOT_FOUND

        with pytest.raises(AddressAPIError, match="VWorld·Kakao 모두 실패"):
            AddressAPI().get_coordinates("존재하지않는주소")

    @patch("data_collector.address_api.requests.get")
    def test_network_error_raises(self, mock_get):
        """VWorld + Kakao 모두 네트워크 오류 → AddressAPIError."""
        mock_get.side_effect = ConnectionError("연결 실패")

        with pytest.raises(AddressAPIError, match="VWorld·Kakao 모두 실패"):
            AddressAPI().get_coordinates("서울특별시 강남구 삼성동 169")

    @patch("data_collector.address_api.requests.get")
    def test_location_address_preserved(self, mock_get):
        """반환된 Location.address는 입력 주소와 동일."""
        mock_get.return_value.raise_for_status = MagicMock()
        mock_get.return_value.json.return_value = _ok_response()
        addr = "서울특별시 강남구 삼성동 169"

        loc = AddressAPI().get_coordinates(addr)

        assert loc.address == addr

    @patch("data_collector.address_api.KAKAO_REST_API_KEY", "test-key")
    @patch("data_collector.address_api.requests.get")
    def test_vworld_http_error_kakao_fallback(self, mock_get):
        """VWorld 502 HTTP 오류 → Kakao REST API 폴백 성공."""
        kakao_resp = {
            "documents": [{"x": "127.060", "y": "37.509", "address_name": "테스트"}]
        }

        def side_effect(url, **kwargs):
            m = MagicMock()
            if "vworld" in url:
                m.raise_for_status.side_effect = HTTPError("502 Bad Gateway")
            else:
                m.raise_for_status = MagicMock()
                m.json.return_value = kakao_resp
            return m

        mock_get.side_effect = side_effect

        loc = AddressAPI().get_coordinates("서울특별시 강남구 테헤란로 521")

        assert loc.lat == pytest.approx(37.509)
        assert loc.lng == pytest.approx(127.060)

    @patch("data_collector.address_api.KAKAO_REST_API_KEY", "test-key")
    @patch("data_collector.address_api.requests.get")
    def test_vworld_notfound_kakao_fallback(self, mock_get):
        """VWorld 결과 없음 → Kakao REST API 폴백 성공."""
        kakao_resp = {
            "documents": [{"x": "126.978", "y": "37.566", "address_name": "서울시청"}]
        }

        def side_effect(url, **kwargs):
            m = MagicMock()
            m.raise_for_status = MagicMock()
            if "vworld" in url:
                m.json.return_value = NOT_FOUND
            else:
                m.json.return_value = kakao_resp
            return m

        mock_get.side_effect = side_effect

        loc = AddressAPI().get_coordinates("서울특별시 중구 세종대로 110")

        assert loc.lat == pytest.approx(37.566)
        assert loc.lng == pytest.approx(126.978)
