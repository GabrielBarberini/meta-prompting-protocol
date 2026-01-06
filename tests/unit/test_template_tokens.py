from mpp_dspy.template_tokens import (
    extract_mutable_blocks,
    list_mutable_blocks,
    render_mutable_template,
)


def test_extract_mutable_blocks() -> None:
    template = "Hi {{MPP_MUTABLE:foo}}bar{{/MPP_MUTABLE}}."
    assert extract_mutable_blocks(template) == {"foo": "bar"}


def test_list_mutable_blocks() -> None:
    template = (
        "{{MPP_MUTABLE:first}}one{{/MPP_MUTABLE}} "
        "{{MPP_MUTABLE:second}}two{{/MPP_MUTABLE}}"
    )
    assert list_mutable_blocks(template) == ["first", "second"]


def test_render_mutable_template_replaces_all_occurrences() -> None:
    template = (
        "{{MPP_MUTABLE:foo}}one{{/MPP_MUTABLE}} "
        "{{MPP_MUTABLE:foo}}two{{/MPP_MUTABLE}}"
    )
    rendered = render_mutable_template(template, {"foo": "swap"})
    assert rendered == "swap swap"


def test_render_mutable_template_keeps_original_if_missing() -> None:
    template = "Hi {{MPP_MUTABLE:foo}}bar{{/MPP_MUTABLE}}."
    assert render_mutable_template(template, {}) == "Hi bar."


def test_render_mutable_template_raises_on_unclosed() -> None:
    template = "Hi {{MPP_MUTABLE:foo}}bar"
    try:
        render_mutable_template(template, {})
    except ValueError as exc:
        assert "Unclosed" in str(exc) or "Missing" in str(exc)
    else:
        raise AssertionError("Expected ValueError for missing end token.")
