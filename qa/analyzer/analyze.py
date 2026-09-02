"""diff-analyzer + reporter: compare engine output against the reference model.

Reads the RESULT lines the C harness printed and the expectations the case
generator attached, then reports every row where the two disagree. A mismatch
is reported as a *finding*, not a verdict: the engine and the spec-derived
model can disagree because the engine is wrong, because the documented rule is
wrong, or because the case setup does not mean what it looks like. Deciding
which is a human's call, so the report carries the full condition row.
"""

import argparse
import collections
import json
import pathlib
import sys

# Severity is assigned by which part of the outcome disagrees. A wrong
# multiplier silently changes damage; a wrong verb is only cosmetic.
SEVERITY_ORDER = {"high": 0, "medium": 1, "low": 2}


def parse_results(path):
    """Read `RESULT <id> <brand> <slay> <verb>` lines into a dict."""
    results = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.startswith("RESULT "):
            continue
        parts = line.split()
        if len(parts) < 6:
            # Malformed line; record it so the case shows up as missing
            # rather than being silently treated as a pass.
            continue
        cid, brand, slay = parts[1], parts[2], parts[3]
        # Slay verbs can be multi-word ("fiercely smite"), so the verb is
        # everything between the slay code and the trailing multiplier.
        verb = " ".join(parts[4:-1])
        multiplier = parts[-1]
        try:
            multiplier = int(multiplier)
        except ValueError:
            multiplier = None
        results[cid] = {
            "brand_used": None if brand == "-" else brand,
            "slay_used": None if slay == "-" else slay,
            "verb": None if verb == "-" else verb,
            "multiplier": multiplier,
        }
    return results


def classify(diffs):
    """Rank a mismatch by what it would do to a real game."""
    if "brand_used" in diffs or "slay_used" in diffs:
        # The wrong modifier was chosen, so the damage multiplier is wrong.
        return "high"
    if "multiplier" in diffs:
        # Right modifier, wrong damage -- silent in play, so still high.
        return "high"
    if "verb" in diffs:
        return "low"
    return "medium"


def compare(cases, results):
    findings = []
    missing = []

    for case in cases:
        cid = case["id"]
        actual = results.get(cid)
        if actual is None:
            missing.append(cid)
            continue

        expected = case["expected"]
        diffs = {}
        for field in ("brand_used", "slay_used", "verb", "multiplier"):
            if expected.get(field) != actual.get(field):
                diffs[field] = {"expected": expected.get(field),
                                "actual": actual.get(field)}

        if diffs:
            findings.append({
                "id": cid,
                "severity": classify(diffs),
                "conditions": {k: case[k] for k in (
                    "brand", "slay", "mon_resists", "mon_vulnerable",
                    "mon_matches_slay", "o_combat", "range")},
                "diffs": diffs,
                "expected_multiplier": expected.get("multiplier"),
                "actual_multiplier": actual.get("multiplier"),
            })

    findings.sort(key=lambda f: (SEVERITY_ORDER[f["severity"]], f["id"]))
    return findings, missing


def render_markdown(cases, findings, missing):
    total = len(cases)
    passed = total - len(findings) - len(missing)
    by_sev = collections.Counter(f["severity"] for f in findings)

    out = []
    out.append("# Angband QA 회귀 리포트 — brand/slay 상호작용")
    out.append("")
    out.append("## 요약")
    out.append("")
    out.append("| 항목 | 값 |")
    out.append("|---|---|")
    out.append(f"| 총 케이스 | {total} |")
    out.append(f"| 일치 | {passed} |")
    out.append(f"| 불일치 | {len(findings)} |")
    out.append(f"| 미실행 | {len(missing)} |")
    out.append(f"| 심각도 high | {by_sev.get('high', 0)} |")
    out.append(f"| 심각도 low | {by_sev.get('low', 0)} |")
    out.append("")

    if missing:
        out.append("## 미실행 케이스")
        out.append("")
        out.append("엔진이 결과를 내지 않은 케이스 — 하네스 렌더링 문제일 수 있음.")
        out.append("")
        for cid in missing[:20]:
            out.append(f"- `{cid}`")
        if len(missing) > 20:
            out.append(f"- … 외 {len(missing) - 20}건")
        out.append("")

    if not findings:
        out.append("## 결과")
        out.append("")
        out.append("참조 모델과 엔진 동작이 **전 케이스 일치**. "
                   "문서화된 규칙 6개가 구현과 어긋나는 지점은 발견되지 않음.")
        out.append("")
    else:
        out.append("## 불일치 상세")
        out.append("")
        out.append("| 케이스 | 심각도 | brand | slay | 저항 | 취약 | 슬레이일치 "
                   "| O-combat | 원거리 | 항목 | 기대 | 실제 |")
        out.append("|---|---|---|---|---|---|---|---|---|---|---|---|")
        for f in findings:
            c = f["conditions"]
            for field, d in f["diffs"].items():
                out.append(
                    f"| `{f['id']}` | {f['severity']} | {c['brand']} | "
                    f"{c['slay']} | {c['mon_resists']} | "
                    f"{c['mon_vulnerable']} | {c['mon_matches_slay']} | "
                    f"{c['o_combat']} | {c['range']} | {field} | "
                    f"`{d['expected']}` | `{d['actual']}` |")
        out.append("")
        out.append("> 불일치는 버그 확정이 아니라 **검토 대상**이다. "
                   "엔진 버그 / 문서화된 규칙의 오류 / 케이스 설정 오류 "
                   "세 가지 가능성을 사람이 판정한다.")
        out.append("")

    return "\n".join(out)


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--cases", required=True)
    ap.add_argument("--results", required=True)
    ap.add_argument("--report", required=True, help="markdown report path")
    ap.add_argument("--json-out", help="optional machine-readable findings")
    args = ap.parse_args()

    cases = json.loads(pathlib.Path(args.cases).read_text(encoding="utf-8"))
    results = parse_results(pathlib.Path(args.results))
    findings, missing = compare(cases, results)

    report = pathlib.Path(args.report)
    report.parent.mkdir(parents=True, exist_ok=True)
    report.write_text(render_markdown(cases, findings, missing) + "\n",
                      encoding="utf-8")

    if args.json_out:
        jo = pathlib.Path(args.json_out)
        jo.parent.mkdir(parents=True, exist_ok=True)
        jo.write_text(json.dumps(
            {"findings": findings, "missing": missing}, indent=2,
            ensure_ascii=False) + "\n", encoding="utf-8")

    print(f"cases={len(cases)} mismatches={len(findings)} "
          f"missing={len(missing)} -> {report}")

    # Non-zero exit so CI can gate on regressions.
    return 1 if (findings or missing) else 0


if __name__ == "__main__":
    sys.exit(main())
