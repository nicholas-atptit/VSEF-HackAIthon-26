import json

from src.hackaithon_mvp.engine_runtime.engine_result import EngineResult
from src.hackaithon_mvp.engine_runtime.output_store import EngineOutputStore


def test_output_store_writes_run_manifest_and_jsonl_result(tmp_path):
    store = EngineOutputStore("unit-run", root_dir=tmp_path)
    manifest_path = store.write_manifest({"engine_id": "classification.logistic_l2.absolute_direction.h40.feature_set_c.threshold_055"})
    result = EngineResult(
        engine_id="classification.logistic_l2.absolute_direction.h40.feature_set_c.threshold_055",
        status="completed",
        diagnostic_label="neutral_or_uncertain",
        confidence=0.25,
        risk_flags=("static_evidence_only",),
        metrics={"matched_static_records": 1},
        dependencies_used=(),
        claim_scope="diagnostic_only",
        warnings=("static MVP result uses local sample evidence only",),
        metadata={"run_mode": "static_evidence_mvp"},
    )
    jsonl_path = store.append_result(result)

    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert manifest["run_id"] == "unit-run"
    lines = jsonl_path.read_text(encoding="utf-8").splitlines()
    assert len(lines) == 1
    assert json.loads(lines[0])["engine_id"] == result.engine_id
