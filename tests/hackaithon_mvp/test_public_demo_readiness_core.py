from src.hackaithon_mvp.public_demo_readiness import (
    build_public_demo_readiness_summary,
    get_public_demo_commands,
)


def test_demo_command_registry_exists():
    commands = get_public_demo_commands()

    assert len(commands) == 6
    assert commands[0]["command"] == "python -m src.hackaithon_mvp.end_to_end_demo"


def test_demo_commands_are_local_and_read_only_by_default():
    commands = get_public_demo_commands()

    assert all(command["writes_files"] is False for command in commands)
    assert all(command["requires_live_data"] is False for command in commands)
    assert all(command["requires_provider"] is False for command in commands)
    assert all(command["runs_training"] is False for command in commands)
    assert all(command["runs_inference"] is False for command in commands)
    assert all(command["runs_benchmark"] is False for command in commands)


def test_readiness_summary_is_ready_with_manual_review():
    summary = build_public_demo_readiness_summary()

    assert summary["readiness_status"] == "ready_with_manual_review"
    assert summary["submission_recommendation"] == "safe_for_local_public_demo_after_human_review"
    assert summary["demo_command_count"] == 6
    assert summary["default_commands_write_files"] is False


def test_remaining_manual_items_mention_configs_and_scripts():
    summary = build_public_demo_readiness_summary()
    text = " ".join(summary["remaining_manual_items"]).lower()

    assert "configs/" in text
    assert "scripts/" in text
    assert "data gateway" in text
    assert "server database" in text
