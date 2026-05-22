SURVIVING_MUTANT_LIMIT = 10


def sorted_surviving_findings(findings: list[dict]) -> list[dict]:
    return sorted(findings, key=_surviving_mutant_sort_key)


def _surviving_mutant_sort_key(finding: dict) -> tuple:
    return (
        0 if finding["covered"] else 1,
        0 if finding["all_survived"] else 1,
        -finding["survived"],
        -finding["total"],
        finding["file"],
        finding["line"],
    )


def coverage_label(finding: dict) -> str:
    return "Covered" if finding["covered"] else "Uncovered"


def mutant_count_label(finding: dict) -> str:
    label = f"{finding['survived']}/{finding['total']} survived"
    if finding["killed"]:
        return f"{finding['killed']} killed, {label}"
    return label


def mutator_descriptions(finding: dict) -> str:
    descriptions = []
    for mutant in finding["mutants"]:
        description = mutant.get("description")
        if description and description not in descriptions:
            descriptions.append(description)
    if not descriptions:
        return "N/A"
    return ", ".join(descriptions)
