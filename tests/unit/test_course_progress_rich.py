from __future__ import annotations

import io
from dataclasses import replace

from rich.console import Console
from tests.unit.test_course_download_planning import _plan, _review

from telegram_courses.course_execution import CourseProgressTracker
from telegram_courses.course_progress_rich import RichCourseProgress


def test_rich_progress_preserves_untrusted_names_as_literal_text(tmp_path) -> None:
    plan = _plan()
    item = plan.items[0]
    candidate = replace(item.candidate, original_filename="[bold]x[/bold].bin")
    plan = replace(plan, items=(replace(item, candidate=candidate),))
    context = ((-1001, 10, 0, 5, 6, 7, "[red]Modulo[/red]"),)
    review = _review(plan, tmp_path, catalog_context=(context,))
    tracker = CourseProgressTracker(plan, lambda: 0.0)
    tracker.start_attempt(item.identity)
    output = io.StringIO()
    presenter = RichCourseProgress(review, Console(file=output, width=240, force_terminal=False))
    presenter(tracker.snapshot())
    presenter.close()
    text = output.getvalue()
    assert "[red]Modulo[/red]" in text
    assert "[bold]x[/bold].bin" in text
    assert "Indisponível" in text
