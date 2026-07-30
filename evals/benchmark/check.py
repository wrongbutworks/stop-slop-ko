#!/usr/bin/env python3
"""stop-slop-ko 벤치마크 채점기.

사용법: python3 check.py <outputs_dir>

<outputs_dir>에 케이스별 출력 파일이 있다고 가정한다:
  {case_id}.with.txt     — 스킬을 로드한 조건의 출력
  {case_id}.without.txt  — 스킬 없이 낸 출력

cases.json(이 스크립트와 같은 디렉터리)의 어설션을 케이스×조건별로 실행하고
결과 표를 마크다운으로 stdout에 출력한다. 표준 라이브러리만 사용한다.
"""

import json
import re
import sys
from pathlib import Path

CONDITIONS = ("with", "without")
NUMBER_RE = re.compile(r"[0-9]+(?:\.[0-9]+)?%?")


def load_cases(path):
    with open(path, encoding="utf-8") as f:
        return json.load(f)["cases"]


def extract_numbers(text):
    """숫자 토큰 전수 추출. '15,000' 같은 천 단위 쉼표는 붙여서 하나로 본다."""
    joined = re.sub(r"(?<=[0-9]),(?=[0-9]{3})", "", text)
    return NUMBER_RE.findall(joined)


def check_case(case, output_text):
    """어설션을 실행해 (통과 수, 전체 수, 실패 목록)을 돌려준다."""
    a = case.get("assertions", {})
    failures = []
    total = 0

    for pat in a.get("must_absent", []):
        total += 1
        if re.search(pat, output_text, re.MULTILINE):
            failures.append(f"must_absent 위반: /{pat}/")

    for pat in a.get("must_present", []):
        total += 1
        if not re.search(pat, output_text, re.MULTILINE):
            failures.append(f"must_present 누락: /{pat}/")

    ratio = a.get("min_length_ratio")
    if ratio is not None:
        total += 1
        in_len = len(case["input"])
        out_len = len(output_text)
        actual = out_len / in_len if in_len else 0.0
        if actual < ratio:
            failures.append(
                f"min_length_ratio 미달: {actual:.2f} < {ratio} (출력 {out_len}자 / 입력 {in_len}자)"
            )

    allowed = a.get("allowed_numbers")
    if allowed is not None:
        total += 1
        allowed_set = {str(x).rstrip("%") for x in allowed}
        invented = sorted(
            {tok for tok in extract_numbers(output_text) if tok.rstrip("%") not in allowed_set}
        )
        if invented:
            failures.append(f"허용 외 숫자 발명: {', '.join(invented)}")

    return total - len(failures), total, failures


def main():
    if len(sys.argv) != 2:
        print("사용법: python3 check.py <outputs_dir>", file=sys.stderr)
        return 2

    outputs_dir = Path(sys.argv[1])
    if not outputs_dir.is_dir():
        print(f"디렉터리가 없다: {outputs_dir}", file=sys.stderr)
        return 2

    cases = load_cases(Path(__file__).parent / "cases.json")

    rows = []
    for case in cases:
        for cond in CONDITIONS:
            path = outputs_dir / f"{case['id']}.{cond}.txt"
            if not path.exists():
                rows.append((case["id"], cond, "-", "파일 없음: " + path.name))
                continue
            text = path.read_text(encoding="utf-8")
            passed, total, failures = check_case(case, text)
            rows.append(
                (case["id"], cond, f"{passed}/{total}", "; ".join(failures) if failures else "-")
            )

    print("| 케이스 | 조건 | 통과/전체 | 실패 어설션 |")
    print("|---|---|---|---|")
    for case_id, cond, score, detail in rows:
        safe_detail = detail.replace("|", "\\|")
        print(f"| {case_id} | {cond} | {score} | {safe_detail} |")

    any_fail = any(r[3] != "-" for r in rows)
    return 1 if any_fail else 0


if __name__ == "__main__":
    sys.exit(main())
