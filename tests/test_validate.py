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
