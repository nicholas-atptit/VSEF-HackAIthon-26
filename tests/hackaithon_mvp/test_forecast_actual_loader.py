import csv
import json

from src.hackaithon_mvp.forecast_actual_evaluation import load_forecast_actual_rows

from forecast_actual_fixtures import forecast_actual_rows


def test_csv_loader_works(tmp_path):
    path = tmp_path / "rows.csv"
    rows = forecast_actual_rows()
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=sorted({key for row in rows for key in row}))
        writer.writeheader()
        writer.writerows(rows)

    loaded = load_forecast_actual_rows(str(path))
    assert len(loaded) == 7
    assert loaded[0]["timeframe"] == "1d"


def test_json_loader_works(tmp_path):
    path = tmp_path / "rows.json"
    path.write_text(json.dumps({"rows": list(forecast_actual_rows())}), encoding="utf-8")

    loaded = load_forecast_actual_rows(str(path))
    assert len(loaded) == 7
    assert loaded[4]["timeframe"] == "5m"


def test_jsonl_loader_works(tmp_path):
    path = tmp_path / "rows.jsonl"
    path.write_text("\n".join(json.dumps(row) for row in forecast_actual_rows()) + "\n", encoding="utf-8")

    loaded = load_forecast_actual_rows(str(path))
    assert len(loaded) == 7
    assert loaded[-1]["forecast_diagnostic"] == "exploratory_only"
