import io
import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from leads import tdlr_source

# SAMPLE rows only, in the API's format (every field quoted, LF line ends).
SAMPLE_DOWNLOAD = (
    b'"license_type","license_number","business_name","owner_name","business_county"\n'
    b'"A/C Contractor","1001","SAMPLE AIR LLC","SAMPLE HOLDER ONE","DALLAS"\n'
    b'"A/C Contractor","1002","SAMPLE, COOLING INC","SAMPLE HOLDER TWO","TARRANT"\n'
)


def test_a_download_with_owner_name_is_written_without_it(tmp_path, monkeypatch):
    monkeypatch.setattr(tdlr_source, "DATA_DIR", tmp_path)
    monkeypatch.setattr(tdlr_source.urllib.request, "urlopen", lambda url, timeout: io.BytesIO(SAMPLE_DOWNLOAD))

    raw = tdlr_source.download_ac_contractor_licences(date(2026, 10, 29)).read_bytes()

    assert b"owner_name" not in raw and b"SAMPLE HOLDER" not in raw
    assert raw == (
        b'"license_type","license_number","business_name","business_county"\n'
        b'"A/C Contractor","1001","SAMPLE AIR LLC","DALLAS"\n'
        b'"A/C Contractor","1002","SAMPLE, COOLING INC","TARRANT"\n'
    )
    assert [r["business_name"] for r in tdlr_source.read_licences(tmp_path / "raw" / "tdlr_ac_contractors_2026-10-29.csv")] \
        == ["SAMPLE AIR LLC", "SAMPLE, COOLING INC"]
