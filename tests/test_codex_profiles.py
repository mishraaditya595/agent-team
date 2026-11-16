import tomllib
from codex_profiles import render_profiles, merge_into_config, BEGIN, END

MODELS = {"codex": {"deep": "m-deep", "standard": "m-std", "fast": "m-fast"}}


def test_render_profiles_has_three():
    data = tomllib.loads(render_profiles(MODELS))
    assert data["profiles"]["at-deep"]["model"] == "m-deep"
    assert data["profiles"]["at-standard"]["model"] == "m-std"
    assert data["profiles"]["at-fast"]["model"] == "m-fast"


def test_merge_appends_when_absent():
    block = render_profiles(MODELS)
    out = merge_into_config('model = "user-choice"\n', block)
    assert out.startswith('model = "user-choice"\n') and BEGIN in out and END in out


def test_merge_replaces_between_markers():
    old = render_profiles({"codex": {"deep": "old", "standard": "old", "fast": "old"}})
    out = merge_into_config("a = 1\n" + old, render_profiles(MODELS))
    assert '"old"' not in out and out.count(BEGIN) == 1


def test_merge_preserves_user_content():
    user = 'model = "user-choice"\n\n[profiles.mine]\nmodel = "x"\n'
    once = merge_into_config(user, render_profiles(MODELS))
    twice = merge_into_config(once, render_profiles(MODELS))
    assert once == twice
    assert 'model = "user-choice"' in twice and "[profiles.mine]" in twice
    tomllib.loads(twice)  # still valid TOML


def test_missing_tier_skips_cleanly(tmp_path, capsys):
    from codex_profiles import main
    m = tmp_path / "m.yaml"; c = tmp_path / "config.toml"
    m.write_text("tools:\n  codex: {deep: a, standard: b}\n")
    assert main(["x", str(m), str(c)]) == 0
    assert not c.exists()
    assert "codex missing tier 'fast'" in capsys.readouterr().out


def test_missing_codex_tool_skips_cleanly(tmp_path, capsys):
    from codex_profiles import main
    m = tmp_path / "m.yaml"; c = tmp_path / "config.toml"
    m.write_text("tools:\n  claude: {deep: a, standard: b, fast: c}\n")
    assert main(["x", str(m), str(c)]) == 0 and not c.exists()
    assert "no 'codex' tool" in capsys.readouterr().out


def test_effort_written_per_profile():
    data = tomllib.loads(render_profiles(MODELS, {"deep": "high", "fast": "low"}))
    assert data["profiles"]["at-deep"]["model_reasoning_effort"] == "high"
    assert data["profiles"]["at-fast"]["model_reasoning_effort"] == "low"
    assert "model_reasoning_effort" not in data["profiles"]["at-standard"]
