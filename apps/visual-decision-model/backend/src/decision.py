"""Editable native d3 question contracts and strict result validation."""

import math


def text(value, name, limit):
    if not isinstance(value, str) or not value.strip() or len(value) > limit:
        raise ValueError(f"{name} must contain 1–{limit} characters.")
    return value.strip()


def validate_decision(value):
    """Copy and validate a question before the inference worker accepts it."""
    if not isinstance(value, dict) or value.get("type") not in (
        "noul",
        "choice",
        "score",
    ):
        raise ValueError("Select Yes/No, Choice, or Ordered score.")
    kind = value["type"]
    instructions = text(value.get("instructions"), "Question", 2000)
    options = value.get("options")
    if not isinstance(options, list) or not 2 <= len(options) <= 10:
        raise ValueError("Provide 2–10 answer options or score levels.")
    if kind == "noul" and len(options) != 2:
        raise ValueError("Yes/No requires exactly two answers: true, then false.")
    copied = []
    for option in options:
        if not isinstance(option, dict):
            raise ValueError("Each answer needs a label and description.")
        copied.append(
            {
                "label": text(option.get("label"), "Answer label", 60),
                "description": text(
                    option.get("description"), "Answer description", 500
                ),
            }
        )
    if len({o["label"].casefold() for o in copied}) != len(copied):
        raise ValueError("Answer labels must be unique.")
    return {"type": kind, "instructions": instructions, "options": copied}


def validate_questions(value):
    """Bound a multi-question request before it enters the scheduler."""
    if not isinstance(value, list) or not 1 <= len(value) <= 4:
        raise ValueError("Provide one to four decision questions.")
    return [validate_decision(question) for question in value]


def native_question(settings):
    """Use the user's question verbatim, with no anomaly-specific instruction."""
    options = settings["options"]
    if settings["type"] == "noul":
        criteria = {
            key: f"{option['label']}: {option['description']}"
            for key, option in zip(("true", "false"), options)
        }
    elif settings["type"] == "choice":
        criteria = {option["label"]: option["description"] for option in options}
    else:
        criteria = [f"{option['label']}: {option['description']}" for option in options]
    return {
        "type": settings["type"],
        "instructions": settings["instructions"],
        "criteria": criteria,
    }


def finite(value, maximum=1):
    return (
        type(value) in (int, float) and math.isfinite(value) and 0 <= value <= maximum
    )


def parse_answer(body, settings, question_id="scene"):
    """Reject malformed native responses instead of inventing or rescaling scores."""
    try:
        answer = body["answers"][question_id]
        kind = settings["type"]
        options = settings["options"]
        if not isinstance(answer, dict) or answer.get("type") != kind:
            raise ValueError()
        result = {"type": kind}
        if kind == "noul":
            p = answer["noul"]
            if not finite(p):
                raise ValueError()
            values = [p, 1 - p]
            result["yes_probability"] = p
        else:
            keys = (
                [o["label"] for o in options]
                if kind == "choice"
                else [str(i) for i in range(len(options))]
            )
            probabilities = answer["probabilities"]
            if not isinstance(probabilities, dict) or set(probabilities) != set(keys):
                raise ValueError()
            values = [probabilities[key] for key in keys]
            if not all(finite(p) for p in values) or not math.isclose(
                sum(values), 1, abs_tol=0.001
            ):
                raise ValueError()
            if kind == "choice":
                choice = answer["choice"]
                if choice not in keys or probabilities[choice] < max(values) - 1e-6:
                    raise ValueError()
                result["choice"] = choice
            else:
                score = answer["score"]
                expected = sum(i * p for i, p in enumerate(values))
                if not finite(score, len(options) - 1) or not math.isclose(
                    score, expected, abs_tol=0.001
                ):
                    raise ValueError()
                result["score"] = score
        result["probabilities"] = [
            dict(option, probability=p) for option, p in zip(options, values)
        ]
        return result
    except (KeyError, TypeError, ValueError):
        raise ValueError("d3 returned a missing or invalid decision result.") from None


def parse_answers(body, questions):
    answers = body.get("answers") if isinstance(body, dict) else None
    ids = {f"q{i + 1}" for i in range(len(questions))}
    if not isinstance(answers, dict) or set(answers) != ids:
        raise ValueError("d3 returned missing or unexpected question answers.")
    return [
        parse_answer(body, question, f"q{i + 1}")
        for i, question in enumerate(questions)
    ]
