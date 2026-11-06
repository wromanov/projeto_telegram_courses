from __future__ import annotations

import pytest

from telegram_courses.catalog_selection import (
    CourseMediaOption,
    MediaIdentity,
    SelectionInputError,
    apply_selection_command,
    parse_selection_command,
)


def _options() -> tuple[CourseMediaOption, ...]:
    return tuple(
        CourseMediaOption(
            identity=MediaIdentity(-1001, message_id, 0), course_id=10,
            module_id=module_id, lesson_id=message_id,
            module_title=f"Módulo {module_id}", lesson_title=f"Aula {message_id}",
            kind="DOCUMENT", telegram_media_id=None, original_filename="a.pdf",
            mime_type=None, file_size_bytes=None, selectable=selectable,
            reason=None if selectable else "associação inativa",
        )
        for message_id, module_id, selectable in (
            (101, 20, True), (102, 30, True), (103, 30, False)
        )
    )


@pytest.mark.parametrize(
    ("text", "action", "indices"),
    [
        ("1", "indices", (1,)),
        ("1, 3, 3", "indices", (1, 3)),
        ("2-3", "indices", (2, 3)),
        ("T", "all", ()),
        ("L", "clear", ()),
        ("R", "remove_mode", ()),
        ("V", "review", ()),
        ("P", "prepare", ()),
        ("B", "all_course", ()),
        ("A", "previous_page", ()),
        ("N", "next_page", ()),
        ("Q", "back", ()),
    ],
)
def test_selection_command_grammar(text, action, indices) -> None:
    command = parse_selection_command(text, 3)
    assert (command.action, command.indices) == (action, indices)


@pytest.mark.parametrize(
    "text", ["", "0", "-1", "4", "3-2", "1,,2", "1-999999", "1;2", "x" * 257]
)
def test_invalid_selection_command_is_rejected(text) -> None:
    with pytest.raises(SelectionInputError):
        parse_selection_command(text, 3)


def test_selection_is_a_stable_identity_set_and_rejects_inactive_rows() -> None:
    options = _options()
    first = parse_selection_command("1,2,2", len(options))
    selected = apply_selection_command(options, frozenset(), first)
    assert selected == frozenset({options[0].identity, options[1].identity})
    removed = apply_selection_command(
        options, selected, parse_selection_command("1", len(options)), removing=True
    )
    assert removed == frozenset({options[1].identity})
    with pytest.raises(SelectionInputError):
        apply_selection_command(
            options, selected, parse_selection_command("3", len(options))
        )
    assert selected == frozenset({options[0].identity, options[1].identity})


def test_select_all_omits_nonselectable_rows_and_remove_all_clears() -> None:
    options = _options()
    selected = apply_selection_command(
        options, frozenset(), parse_selection_command("T", len(options))
    )
    assert selected == frozenset({options[0].identity, options[1].identity})
    assert apply_selection_command(
        options, selected, parse_selection_command("T", len(options)), removing=True
    ) == frozenset()
