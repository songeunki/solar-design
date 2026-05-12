import pytest
from unittest.mock import patch, MagicMock
from requests.exceptions import ConnectionError

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
        """road·parcel 모두 NOT_FOUND → AddressAPIError."""
        mock_get.return_value.raise_for_status = MagicMock()
        mock_get.return_value.json.return_value = NOT_FOUND

        with pytest.raises(AddressAPIError, match="주소를 찾을 수 없습니다"):
            AddressAPI().get_coordinates("존재하지않는주소")

    @patch("data_collector.address_api.requests.get")
    def test_network_error_raises(self, mock_get):
        """네트워크 오류 → AddressAPIError."""
        mock_get.side_effect = ConnectionError("연결 실패")

        with pytest.raises(AddressAPIError, match="VWorld API 호출 실패"):
            AddressAPI().get_coordinates("서울특별시 강남구 삼성동 169")

    @patch("data_collector.address_api.requests.get")
    def test_location_address_preserved(self, mock_get):
        """반환된 Location.address는 입력 주소와 동일."""
        mock_get.return_value.raise_for_status = MagicMock()
        mock_get.return_value.json.return_value = _ok_response()
        addr = "서울특별시 강남구 삼성동 169"

        loc = AddressAPI().get_coordinates(addr)

        assert loc.address == addr
