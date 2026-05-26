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


def test_prompt_upgrade_mode_has_dedicated_fields_and_no_target_path():
    html = (ROOT / "web/index.html").read_text(encoding="utf-8")
    app_js = (ROOT / "web/app.js").read_text(encoding="utf-8")

    assert '<option value="prompt_upgrade">Prompt Upgrade</option>' in html
    assert 'id="promptUpgradeFields"' in html
    assert 'id="rawPrompt"' in html
    assert 'id="revisionRequest"' in html
    assert 'id="revisePromptButton"' in html
    assert html.index('id="revisionFields"') > html.index('id="promptOutput"')
    assert "Edit with Request" in html
    assert "Regenerate with Request" not in html
    assert 'els.targetPathRow.hidden = isPromptUpgrade' in app_js
    assert "const hasPromptUpgradeResult = isPromptUpgrade" in app_js
    assert "els.result.hidden = isPromptUpgrade ? !hasPromptUpgradeResult : !isVerify" in app_js
    assert "if (isPromptUpgrade) {\n    els.revisionFields.hidden = true;\n  }" in app_js
    assert 'els.rawPrompt.addEventListener("input", resetPromptUpgradeResult)' in app_js
    assert '"/api/prompt/upgrade"' in app_js
    assert '"/api/prompt/revise"' in app_js
