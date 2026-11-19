from conftest import role_md, ROLE_BODY, GOOD_MODELS
from validate import validate_repo


def has(errors, fragment):
    return any(fragment in e for e in errors)


def test_valid_fixture_passes(make_repo):
    assert validate_repo(make_repo({"dev": role_md("dev")})) == []


def test_name_must_match_folder(make_repo):
    errs = validate_repo(make_repo({"y": role_md("x")}))
    assert has(errs, "name 'x' != folder 'y'")


def test_non_portable_frontmatter_rejected(make_repo):
    errs = validate_repo(make_repo({"dev": role_md("dev", extra_fm="model: opus\n")}))
    assert has(errs, "non-portable field 'model'")


def test_role_tier_must_be_allowed(make_repo):
    errs = validate_repo(make_repo({"dev": role_md("dev", tier="deep", allowed="[fast]")}))
    assert has(errs, "tier 'deep' not in allowed-tiers")


def test_unknown_tier_rejected(make_repo):
    errs = validate_repo(make_repo({"dev": role_md("dev", tier="ultra", allowed="[ultra]")}))
    assert has(errs, "unknown tier 'ultra'")


def test_models_yaml_missing_tier(make_repo):
    models = GOOD_MODELS.replace("standard: m-std, fast: m-fast", "standard: m-std")
    errs = validate_repo(make_repo({}, models=models))
    assert "models.yaml: tool 'codex' missing tier 'fast'" in errs


def test_role_needs_sections(make_repo):
    errs = validate_repo(make_repo({"dev": role_md("dev", body="nothing here\n")}))
    for h in ("## Reads", "## Writes", "## Never"):
        assert has(errs, f"missing heading '{h}'")


def test_role_length_limit(make_repo):
    long_body = ROLE_BODY + "line\n" * 160
    errs = validate_repo(make_repo({"dev": role_md("dev", body=long_body)}))
    assert has(errs, "exceeds 150 lines")


def test_missing_frontmatter_reported(make_repo):
    errs = validate_repo(make_repo({"dev": "# no frontmatter\n"}))
    assert has(errs, "no frontmatter")


def test_agents_model_matches_tier(make_repo):
    root = make_repo({"dev": role_md("dev", tier="fast")})
    (root / "agents").mkdir()
    (root / "agents" / "dev.md").write_text("---\nname: dev\ndescription: Use when testing.\nmodel: opus\n---\nx\n")
    assert has(validate_repo(root), "agents/dev.md: model 'opus' != 'haiku'")


def test_role_without_agent_file_reported(make_repo):
    root = make_repo({"dev": role_md("dev")})
    (root / "agents").mkdir()
    assert has(validate_repo(root), "agents/dev.md: missing")


def test_real_repo_is_valid():
    from conftest import ROOT
    assert validate_repo(ROOT) == []


def test_plugin_manifests_parse():
    import json
    from conftest import ROOT
    plugin = json.loads((ROOT / ".claude-plugin/plugin.json").read_text())
    market = json.loads((ROOT / ".claude-plugin/marketplace.json").read_text())
    assert plugin["name"] == "solo-squad" == market["plugins"][0]["name"] == market["name"]


def test_namespaced_agent_fallback_uses_plugin_name():
    import json
    from conftest import ROOT
    name = json.loads((ROOT / ".claude-plugin/plugin.json").read_text())["name"]
    text = (ROOT / "skills/team-build/references/dispatch-claude.md").read_text()
    assert f"`{name}:<role>`" in text


def test_models_yaml_missing_tool(make_repo):
    models = "tools:\n  claude: {deep: opus, standard: sonnet, fast: haiku}\n"
    errs = validate_repo(make_repo({}, models=models))
    assert "models.yaml: missing tool 'codex'" in errs and "models.yaml: missing tool 'gemini'" in errs


def test_models_yaml_is_a_real_file_in_the_skill():
    from conftest import ROOT
    ref = ROOT / "skills" / "team-build" / "references" / "models.yaml"
    assert ref.is_file() and not ref.is_symlink()
    assert not (ROOT / "config").exists()


def test_bad_effort_rejected(make_repo):
    errs = validate_repo(make_repo({}, models=GOOD_MODELS + "effort:\n  deep: huge\n  turbo: low\n"))
    assert has(errs, "effort 'huge'") and has(errs, "unknown tier 'turbo'")


def test_missing_reference_reported(make_repo):
    body = ROLE_BODY + "Use `references/nope.md`.\n"
    errs = validate_repo(make_repo({"dev": role_md("dev", body=body)}))
    assert has(errs, "mentions 'references/nope.md'")


def test_reference_in_other_skill_ok(make_repo):
    root = make_repo({"dev": role_md("dev", body=ROLE_BODY + "See the other skill's `references/x.md`.\n")})
    (root / "skills" / "team-build" / "references" / "x.md").write_text("x")
    assert validate_repo(root) == []


def test_agent_description_must_match(make_repo):
    root = make_repo({"dev": role_md("dev", tier="fast")})
    (root / "agents").mkdir()
    (root / "agents" / "dev.md").write_text("---\nname: dev\ndescription: something else\nmodel: haiku\n---\nx\n")
    assert has(validate_repo(root), "description doesn't match")


def test_status_schema_mismatch_reported(make_repo):
    root = make_repo({})
    ref = root / "skills" / "team-build"
    (ref / "references" / "status-template.md").write_text("stage: spec\nextra: 1\n\n## Log\n")
    (ref / "scripts").mkdir()
    (ref / "scripts" / "agent_team.py").write_text('STATUS_KEYS = ("stage", "pr")\n')
    assert has(validate_repo(root), "status-template.md keys")
