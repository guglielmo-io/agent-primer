from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_settings_ui_supports_custom_openrouter_models():
    html = (ROOT / "web/index.html").read_text(encoding="utf-8")
    app_js = (ROOT / "web/app.js").read_text(encoding="utf-8")

    assert 'id="customModel"' in html
    assert "Custom OpenRouter model" in html
    assert 'CUSTOM_MODEL = "__custom__"' in app_js
    assert "selectedModelId()" in app_js


def test_existing_project_setup_cannot_overwrite_context_from_ui():
    app_js = (ROOT / "web/app.js").read_text(encoding="utf-8")

    assert "overwrite: isNew && els.overwrite.checked" in app_js
    assert "els.overwriteRow.hidden = !isNew" in app_js
    assert "els.overwrite.checked = false" in app_js
