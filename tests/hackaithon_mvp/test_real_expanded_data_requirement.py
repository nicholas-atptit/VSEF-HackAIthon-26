from src.hackaithon_mvp.real_expanded_data_requirement import (
    check_real_expanded_data_available,
    render_real_expanded_data_requirement_report,
)


def _write_panel(path, header, rows):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(header + "\n" + "\n".join(rows) + "\n", encoding="utf-8")
    return path


def test_requirement_blocks_missing_expanded_data(tmp_path):
    result = check_real_expanded_data_available(output_root=str(tmp_path / ".tmp_real_expanded_60pct"))
    report = render_real_expanded_data_requirement_report(result)

    assert result["expanded_data_requirement_status"] == "expanded_data_required_for_60pct_attempt"
    assert result["real_expanded_data_available"] is False
    assert "OHLCV-only data is not accepted" in report


def test_requirement_rejects_ohlcv_only_panel(tmp_path):
    panel = _write_panel(
        tmp_path / "expanded_price_panel.csv",
        "ticker,timestamp,open,high,low,close,volume",
        ["AAA,2026-01-01,1,2,1,1.5,100", "AAA,2026-01-02,1,2,1,1.7,110"],
    )

    result = check_real_expanded_data_available(input_path=str(panel))

    assert result["expanded_data_requirement_status"] == "expanded_data_missing_ohlcv_only"
    assert result["is_ohlcv_only"] is True
    assert result["additional_context_group_count"] == 0


def test_requirement_accepts_ohlcv_plus_two_context_groups(tmp_path):
    panel = _write_panel(
        tmp_path / "expanded_price_panel.csv",
        "ticker,timestamp,open,high,low,close,volume,adjusted_close,index_return",
        ["AAA,2026-01-01,1,2,1,1.5,100,1.45,0.001", "AAA,2026-01-02,1,2,1,1.7,110,1.65,0.002"],
    )

    result = check_real_expanded_data_available(input_path=str(panel))

    assert result["expanded_data_requirement_status"] == "real_expanded_data_available"
    assert result["real_expanded_data_available"] is True
    assert result["additional_context_group_count"] == 2
    assert "adjusted_price" in result["additional_context_groups_present"]
    assert "index_context" in result["additional_context_groups_present"]


def test_requirement_counts_intraday_as_context_group(tmp_path):
    panel = _write_panel(
        tmp_path / "expanded_price_panel.csv",
        "ticker,timestamp,open,high,low,close,volume,sector",
        [
            "AAA,2026-01-01T10:15:00,1,2,1,1.5,100,banking",
            "AAA,2026-01-01T10:30:00,1,2,1,1.7,110,banking",
        ],
    )

    result = check_real_expanded_data_available(input_path=str(panel))

    assert result["expanded_data_requirement_status"] == "real_expanded_data_available"
    assert "intraday_granularity" in result["additional_context_groups_present"]
    assert "sector_or_industry" in result["additional_context_groups_present"]
