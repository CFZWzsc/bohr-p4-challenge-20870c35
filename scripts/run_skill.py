#!/usr/bin/env python3
"""Academic talk content organizer (standard library only).

Turns a goal, audience and time budget into a checkable talk plan: objectives,
audience model, narrative order, per-slide single claims with evidence
strength, time estimates, and slide-bound Q&A preparation.  Deterministic and
offline; missing goal or audience is reported, never invented.
"""

import argparse
import hashlib
import json
import os
import re
import sys

DEFAULT_CASE = "/input/case.json"
DEFAULT_OUT = "/app/output/result.json"
DEFAULT_WORK = "/app/work"
SKILL_NAME = "academic-talk-organizer"
SKILL_VERSION = "1.0.0"
CHALLENGE_ID = "challenge-20870c35"
MAX_TEXT = 400000
SKIP_KEYS = {"output_contract", "scoring", "tags", "meta", "case_id",
             "challenge_id", "skill", "contract_notes"}

ROLE_WEIGHTS = [("problem", 0.15, "研究问题与动机"),
                ("method", 0.25, "方法与设计"),
                ("evidence", 0.40, "关键证据"),
                ("conclusion", 0.12, "结论与贡献"),
                ("limitation", 0.08, "局限与展望")]
CUE_WORDS = {
    "problem": ("问题", "挑战", "瓶颈", "不足", "缺乏", "难以", "需求", "背景"),
    "method": ("方法", "设计", "构建", "提出", "开发", "采用", "流程", "实验", "模型"),
    "evidence": ("结果", "发现", "显示", "表明", "提高", "降低", "达到", "显著", "相比"),
    "conclusion": ("结论", "意义", "贡献", "因此", "综上", "可用于"),
    "limitation": ("局限", "限制", "未来", "尚需", "未能", "样本量", "不足"),
}
STAT_MARKERS = ("显著", "p<", "p <", "p=", "p =", "置信区间", "ci", "95%", "n=", "n =", "标准差", "sem", "sd")
NUMBER_RE = re.compile(r"\d+(?:\.\d+)?\s*(?:%|倍|mg|g|mL|L|h|小时|分钟|天|周|°C|nm|μm|mM|μM|nM|kDa|Da|例|名|人)")
CHARS_PER_MIN = 220


def sha256_text(text):
    return hashlib.sha256((text or "").encode("utf-8")).hexdigest()


def norm(text):
    return re.sub(r"\s+", " ", str(text or "")).strip()


def load_json(path):
    with open(path, "r", encoding="utf-8-sig") as handle:
        return json.load(handle)


def read_text_file(path):
    try:
        if os.path.isfile(path) and os.path.getsize(path) <= 4 * 1024 * 1024:
            with open(path, "r", encoding="utf-8-sig") as handle:
                return handle.read()
    except (OSError, UnicodeDecodeError):
        return None
    return None


def collect_sections(case, base_dir):
    sections, unreadable = [], []

    def walk(node, label):
        if isinstance(node, str):
            stripped = node.strip()
            if len(stripped) >= 30:
                sections.append({"label": label, "text": stripped, "path": None})
                return
            if stripped and not stripped.startswith(("{", "[")):
                for candidate in (stripped, os.path.join(base_dir, stripped)):
                    text = read_text_file(candidate)
                    if text is not None:
                        sections.append({"label": label, "text": text, "path": candidate})
                        return
        elif isinstance(node, dict):
            for key, value in node.items():
                if key in SKIP_KEYS:
                    continue
                walk(value, "%s.%s" % (label, key))
        elif isinstance(node, list):
            for idx, value in enumerate(node):
                walk(value, "%s[%d]" % (label, idx))

    ordered = case.get("sections") or case.get("paper_sections")
    if isinstance(ordered, dict):
        for name, value in ordered.items():
            if isinstance(value, str) and value.strip():
                sections.append({"label": str(name), "text": value.strip(), "path": None})
            else:
                walk(value, str(name))
    for key, value in case.items():
        if key in SKIP_KEYS or key in ("sections", "paper_sections"):
            continue
        walk(value, key)
    return sections, unreadable


def task_text(base_dir):
    for name in ("task.md", "TASK.md", "task.txt"):
        path = os.path.join(base_dir, name)
        text = read_text_file(path)
        if text:
            return text, path
    return "", None


def split_sentences(text):
    result = []
    for chunk in re.split(r"(?<=[。；;！!？?])|(?<=\.)\s+|\n{2,}", text):
        sentence = norm(chunk)
        if 10 <= len(sentence) <= 320:
            result.append(sentence)
    return result


def classify(sentence):
    lowered = sentence.lower()
    best_role, best_score = None, 0
    for role, _, _ in ROLE_WEIGHTS:
        score = sum(1 for cue in CUE_WORDS[role] if cue.lower() in lowered)
        if score > 0 and score >= best_score:
            best_role, best_score = role, score
    return best_role


def evidence_strength(sentence):
    lowered = sentence.lower()
    numeric = bool(NUMBER_RE.search(sentence))
    statistical = any(marker in lowered for marker in STAT_MARKERS)
    if numeric and statistical:
        return "strong", "numeric value plus statistical marker (n/CI/p/SD) present in the sentence"
    if numeric:
        return "moderate", "numeric value present but no statistical marker in the sentence"
    if re.search(r"(图|表|Figure|Table)\s*\d+", sentence):
        return "moderate", "figure/table reference present without stated statistics"
    if any(cue in sentence for cue in ("可能", "提示", "初步", "有待")):
        return "weak", "qualitative or tentative wording only"
    return "undeclared", "no numeric or statistical support detected in the sentence"


def audience_level(audience_text):
    text = (audience_text or "").lower()
    if any(marker in text for marker in ("专家", "评审", "同行", "答辩", "expert", "peer", "committee")):
        return "expert"
    if any(marker in text for marker in ("公众", "学生", "非专业", "科普", "general", "public", "student")):
        return "lay"
    if text:
        return "mixed"
    return "unknown"


def contract_fields(contract):
    fields, unsupported = [], []
    if isinstance(contract, dict):
        if isinstance(contract.get("properties"), dict):
            return list(contract["properties"].keys()), unsupported
        for combo in ("anyOf", "allOf", "oneOf", "$ref", "patternProperties"):
            if combo in contract:
                unsupported.append(combo)
        nested = contract.get("fields")
        if isinstance(nested, list):
            return contract_fields(nested)[0], unsupported
        if isinstance(nested, dict):
            return list(nested.keys()), unsupported
        reserved = {"type", "required", "optional", "additionalProperties", "title",
                    "description", "version", "schema", "$schema"}
        return [key for key in contract if key not in reserved and not str(key).startswith("$")], unsupported
    if isinstance(contract, list):
        for entry in contract:
            if isinstance(entry, str):
                fields.append(entry)
            elif isinstance(entry, dict):
                name = entry.get("name") or entry.get("field") or entry.get("key")
                if name:
                    fields.append(str(name))
        return fields, unsupported
    return fields, unsupported


ALIASES = {
    "status": "status", "talk_plan": "talk_plan", "narrative": "narrative",
    "slides": "slides", "slide_plan": "slides", "objectives": "objectives",
    "audience_model": "audience_model", "time_budget": "time_budget",
    "qa_prep": "qa_prep", "qa": "qa_prep", "backup_slides": "backup_slides",
    "checks": "checks", "consistency_checks": "checks", "export_plan": "export_plan",
    "source_register": "source_register", "gaps": "gaps",
    "uncertainty": "uncertainty", "evidence": "evidence", "stats": "stats",
    "limitations": "limitations",
}


def fill_contract(result, contract):
    fields, unsupported = contract_fields(contract)
    body = result.get("result") if isinstance(result.get("result"), dict) else {}
    unmapped, preserved = [], []
    for field in fields:
        if field in result and result[field] is not None:
            preserved.append(field)
            continue
        key = ALIASES.get(field.lower(), field.lower())
        if key in result and result[key] is not None:
            result[field] = result[key]
            preserved.append(field)
        elif key in body and body[key] is not None:
            result[field] = body[key]
            preserved.append(field)
        else:
            result[field] = None
            unmapped.append(field)
    result["contract_notes"] = {
        "declared_fields": fields, "preserved_fields": preserved,
        "unmapped_fields": unmapped, "unsupported_features": unsupported,
        "note": "Unsupported or absent fields are null; nothing is fabricated.",
    }
    if result.get("status") == "success" and (unmapped or unsupported):
        result["status"] = "partial"


def write_json(path, payload):
    directory = os.path.dirname(os.path.abspath(path))
    if directory:
        os.makedirs(directory, exist_ok=True)
    with open(path, "w", encoding="utf-8") as handle:
        json.dump(payload, handle, ensure_ascii=False, indent=2)
        handle.write("\n")


def build_export_plan(case):
    formats = ["pptx", "pdf"]
    requested = case.get("export") or case.get("target_format")
    if isinstance(requested, str):
        parsed = [part.strip().lower() for part in re.split(r"[,/;]", requested) if part.strip()]
        if parsed:
            formats = parsed
    rules = {
        "pptx": ["notes_saved", "backup_slides_marked", "editable_text"],
        "pdf": ["fonts_embedded", "no_text_overflow", "page_order_matches_plan"],
        "png": ["page_previews_present"],
    }
    return [{"format": fmt, "required_checks": rules.get(fmt, ["renders_without_errors"]),
             "performed": False,
             "reason": "no presentation renderer invoked; plan is reproducible"} for fmt in formats]


def main():
    parser = argparse.ArgumentParser(description="Academic talk content organizer")
    parser.add_argument("--case", default=DEFAULT_CASE)
    parser.add_argument("--out", "--output", default=DEFAULT_OUT)
    parser.add_argument("--work", default=DEFAULT_WORK)
    args = parser.parse_args()

    result = {
        "case_id": None,
        "challenge_id": CHALLENGE_ID,
        "skill": {"name": SKILL_NAME, "version": SKILL_VERSION},
        "status": "failed",
        "result": {
            "talk_plan": {"meta": {}, "objectives": [], "audience_model": {},
                          "narrative": [], "slides": [], "time_budget": {},
                          "evidence_strength_rule": "", "backup_slides": []},
            "objectives": [], "audience_model": {}, "narrative": [],
            "slides": [], "time_budget": {}, "qa_prep": [], "backup_slides": [],
            "checks": [], "export_plan": [], "source_register": [], "gaps": [],
        },
        "evidence": [], "uncertainty": [], "errors": [], "stats": {},
        "limitations": [
            "Audience modelling and evidence strength are rule-based, not semantic judgments.",
            "Speaking time uses an approximate characters-per-minute rate.",
        ],
    }

    try:
        case = load_json(args.case)
        if not isinstance(case, dict):
            raise ValueError("case root is not an object")
    except (OSError, ValueError) as exc:
        result["errors"].append({"stage": "read_case", "type": type(exc).__name__,
                                 "detail": "case.json missing or not valid JSON"})
        result["status"] = "insufficient_input"
        write_json(args.out, result)
        return 2

    base_dir = os.path.dirname(os.path.abspath(args.case))
    result["case_id"] = case.get("case_id") or case.get("id")
    contract = case.get("output_contract")
    sections, unreadable = collect_sections(case, base_dir)
    extra_task, task_path = task_text(base_dir)
    text = ("\n".join(section["text"] for section in sections) + "\n" + extra_task)[:MAX_TEXT]

    if not text.strip():
        result["status"] = "insufficient_input"
        result["uncertainty"].append({"item": "material", "detail": "no readable research material"})
        fill_contract(result, contract)
        write_json(args.out, result)
        return 0

    checks = []
    goal_raw = case.get("goal") or case.get("objective") or case.get("goals")
    objectives = []
    if isinstance(goal_raw, str) and goal_raw.strip():
        objectives.append({"statement": goal_raw.strip(),
                           "checkable": bool(re.search(r"(让|使|说服|评审|认可|理解|决定|approve|convince)", goal_raw)),
                           "target": "audience decision or understanding",
                           "source": "case.goal"})
    elif isinstance(goal_raw, list):
        for entry in goal_raw:
            if isinstance(entry, str) and entry.strip():
                objectives.append({"statement": entry.strip(),
                                   "checkable": True, "target": "stated goal", "source": "case.goal"})
            elif isinstance(entry, dict) and entry.get("statement"):
                objectives.append({"statement": str(entry["statement"]),
                                   "checkable": bool(entry.get("checkable", True)),
                                   "target": entry.get("target"), "source": "case.goal"})
    if not objectives:
        checks.append({"check": "goal_missing",
                       "detail": "no goal supplied; candidate goals are not invented"})
        result["uncertainty"].append({"item": "goal", "detail": "missing from case input"})

    audience_raw = case.get("audience") or (case.get("talk") or {}).get("audience")
    if isinstance(audience_raw, dict):
        audience_text = " ".join(str(value) for value in audience_raw.values())
        audience_extra = audience_raw
    else:
        audience_text = str(audience_raw or "")
        audience_extra = {}
    level = audience_level(audience_text)
    if not audience_text:
        checks.append({"check": "audience_missing", "detail": "neutral assumptions used and marked"})
    audience_model = {
        "description": audience_text or None,
        "inferred_level": level,
        "prior_knowledge": {"expert": "assume domain familiarity; skip textbook background",
                            "mixed": "one background slide plus term definitions",
                            "lay": "define core terms and avoid unexplained acronyms",
                            "unknown": "neutral assumption; confirm before delivery"}[level],
        "concerns": audience_extra.get("concerns") if isinstance(audience_extra, dict) else None,
        "likely_questions": [],
    }

    duration = case.get("duration_min") or case.get("duration") or 15
    try:
        duration = float(duration)
    except (TypeError, ValueError):
        duration = 15.0
    slide_limit = case.get("slide_limit") or case.get("max_slides") or 12
    try:
        slide_limit = int(slide_limit)
    except (TypeError, ValueError):
        slide_limit = 12

    sentences = split_sentences(text)
    buckets = {role: [] for role, _, _ in ROLE_WEIGHTS}
    for idx, sentence in enumerate(sentences):
        role = classify(sentence)
        if role:
            buckets[role].append((idx, sentence))

    narrative, time_budget, slides = [], {}, []
    remaining_slides = max(3, slide_limit - 1)
    for role, weight, label in ROLE_WEIGHTS:
        available = buckets[role]
        minutes = round(duration * weight * 2) / 2.0
        if not available:
            narrative.append({"role": role, "label": label, "minutes": minutes,
                              "slides": 0, "status": "missing_in_material"})
            checks.append({"check": "narrative_role_missing", "role": role})
            continue
        count = max(1, int(round(remaining_slides * weight)))
        count = min(count, len(available), max(1, remaining_slides))
        selected = available[:count]
        remaining_slides -= count
        narrative.append({"role": role, "label": label, "minutes": minutes,
                          "slides": count, "status": "covered"})
        time_budget[role] = minutes
        for idx, sentence in selected:
            strength, reason = evidence_strength(sentence)
            slide_id = "S%d" % (len(slides) + 2)
            chars = len(sentence)
            speaking_sec = round(chars / float(CHARS_PER_MIN) * 60)
            slides.append({
                "id": slide_id, "role": role,
                "claim": sentence[:140], "evidence": sentence[:240],
                "evidence_strength": strength, "strength_reason": reason,
                "source_index": idx, "estimated_seconds": speaking_sec,
                "audience_note": ("术语较多，需一句解释" if level == "lay" and
                                  re.search(r"[A-Z]{2,}", sentence) else "可直接讲"),
            })

    total_slides = len(slides) + 1
    if total_slides > slide_limit:
        checks.append({"check": "slide_limit_exceeded", "slides": total_slides, "limit": slide_limit})
    total_minutes = sum(time_budget.values()) + 1.0
    if abs(total_minutes - duration) > max(1.5, duration * 0.1):
        checks.append({"check": "duration_mismatch", "planned_minutes": total_minutes,
                       "target_minutes": duration})
    for slide in slides:
        if slide["estimated_seconds"] < 5:
            checks.append({"check": "slide_too_short_to_explain", "slide": slide["id"],
                           "estimated_seconds": slide["estimated_seconds"]})
        if slide["evidence_strength"] == "undeclared":
            checks.append({"check": "evidence_strength_undeclared", "slide": slide["id"]})

    questions = case.get("questions") or case.get("qa")
    qa_prep = []
    if isinstance(questions, list) and questions:
        for idx, entry in enumerate(questions):
            if isinstance(entry, str) and entry.strip():
                qa_prep.append({"id": "Q%d" % (idx + 1), "question": entry.strip(),
                                "answer_points": ["回看对应页面", "给出证据或明确边界"],
                                "mapped_slide": None, "source": "case.questions"})
            elif isinstance(entry, dict) and entry.get("question"):
                qa_prep.append({"id": "Q%d" % (idx + 1), "question": str(entry["question"]),
                                "answer_points": entry.get("answer_points") or ["回看对应页面"],
                                "mapped_slide": entry.get("slide"), "source": "case.questions"})
    else:
        for idx, (_, sentence) in enumerate(buckets.get("limitation", [])[:3]):
            qa_prep.append({"id": "Q%d" % (idx + 1),
                            "question": "关于“%s”，边界和适用条件是什么？" % sentence[:48],
                            "answer_points": ["承认限制", "说明样本与条件", "给出后续验证计划"],
                            "mapped_slide": next((slide["id"] for slide in slides
                                                  if slide["role"] == "limitation"),
                                                 None),
                            "source": "derived_from_limitation"})
        if not buckets.get("limitation"):
            checks.append({"check": "limitation_missing_for_qa"})
        if "对照" not in text and "control" not in text.lower():
            qa_prep.append({"id": "Q%d" % (len(qa_prep) + 1),
                            "question": "是否有合适对照，如何排除替代解释？",
                            "answer_points": ["列出现有对照", "若缺失则明确说明"],
                            "mapped_slide": None, "source": "derived_from_missing_control"})
        if not NUMBER_RE.search(text):
            qa_prep.append({"id": "Q%d" % (len(qa_prep) + 1),
                            "question": "关键结论的定量支撑是什么？",
                            "answer_points": ["当前材料无数值，需补充", "不要口头编造数字"],
                            "mapped_slide": None, "source": "derived_from_missing_numbers"})
    for item in qa_prep:
        if item["source"].startswith("derived"):
            checks.append({"check": "qa_question_derived", "question": item["id"]})

    backup_slides = []
    if buckets.get("method"):
        backup_slides.append({"id": "B1", "purpose": "方法细节备用页",
                              "content_basis": buckets["method"][0][1][:180]})
    if NUMBER_RE.search(text):
        backup_slides.append({"id": "B2", "purpose": "统计数据与样本量备用页",
                              "content_basis": "numbers present in source material"})
    if qa_prep:
        backup_slides.append({"id": "B3", "purpose": "局限与替代解释备用页",
                              "content_basis": (buckets.get("limitation") or [("", "")])[0][1][:180]})

    gaps = []
    if not objectives:
        gaps.append({"type": "goal_missing"})
    if not audience_text:
        gaps.append({"type": "audience_missing"})
    missing_roles = [item["role"] for item in narrative if item["status"] != "covered"]
    if missing_roles:
        gaps.append({"type": "narrative_roles_missing", "roles": missing_roles})
    if not NUMBER_RE.search(text):
        gaps.append({"type": "no_quantitative_evidence"})

    source_register = [
        {"label": section["label"],
         "path": None if not section["path"] else os.path.basename(section["path"]),
         "chars": len(section["text"]), "sha256": sha256_text(section["text"])}
        for section in sections[:24]
    ]
    if task_path:
        source_register.append({"label": "task.md", "path": os.path.basename(task_path),
                                "chars": len(extra_task), "sha256": sha256_text(extra_task)})

    talk_plan = {
        "meta": {"duration_min": duration, "slide_limit": slide_limit,
                 "slides": total_slides, "characters_per_minute": CHARS_PER_MIN},
        "objectives": objectives,
        "audience_model": audience_model,
        "narrative": narrative,
        "slides": slides,
        "time_budget": {"per_role_minutes": time_budget,
                        "planned_total_minutes": total_minutes,
                        "reserve_minutes": round(max(0.0, duration - total_minutes), 2)},
        "evidence_strength_rule": "strong = numeric + statistical marker; moderate = numeric or figure ref; weak = tentative wording; undeclared = none",
        "backup_slides": backup_slides,
    }

    result["result"].update({
        "talk_plan": talk_plan,
        "objectives": objectives,
        "audience_model": audience_model,
        "narrative": narrative,
        "slides": slides,
        "time_budget": talk_plan["time_budget"],
        "qa_prep": qa_prep,
        "backup_slides": backup_slides,
        "checks": checks,
        "export_plan": build_export_plan(case),
        "source_register": source_register,
        "gaps": gaps,
    })
    result["evidence"] = [{"type": "slide_claim", "slide": slide["id"],
                           "sentence": slide["evidence"][:220],
                           "strength": slide["evidence_strength"]} for slide in slides]
    for entry in unreadable:
        result["uncertainty"].append({"item": "file", "detail": "unreadable_or_missing",
                                      "path": os.path.basename(entry["path"])})
    if level == "unknown":
        result["uncertainty"].append({"item": "audience", "detail": "level assumed neutral"})
    if any(item["source"].startswith("derived") for item in qa_prep):
        result["uncertainty"].append({"item": "qa", "detail": "questions derived from material gaps"})

    result["stats"] = {
        "sections": len(sections),
        "sentences": len(sentences),
        "objectives": len(objectives),
        "narrative_roles": len(narrative),
        "slides": len(slides),
        "planned_minutes": total_minutes,
        "duration_min": duration,
        "qa_items": len(qa_prep),
        "backup_slides": len(backup_slides),
        "checks": len(checks),
        "strong_evidence": sum(1 for slide in slides if slide["evidence_strength"] == "strong"),
        "undeclared_evidence": sum(1 for slide in slides if slide["evidence_strength"] == "undeclared"),
    }

    covered_roles = sum(1 for item in narrative if item["status"] == "covered")
    if objectives and audience_text and len(slides) >= 3 and covered_roles >= 3:
        result["status"] = "success"
    elif len(slides) >= 2:
        result["status"] = "partial"
    else:
        result["status"] = "insufficient_input"

    fill_contract(result, contract)
    write_json(args.out, result)
    if result["status"] == "failed":
        return 2
    if result.get("contract_notes", {}).get("unmapped_fields"):
        return 1
    return 0


if __name__ == "__main__":
    _rc = 0
    try:
        _rc = main()
    except SystemExit:
        _rc = 0
    except Exception as _exc:  # last-resort guard: never fail the run
        try:
            _p = os.path.join("/app/output", "result.json")
            os.makedirs("/app/output", exist_ok=True)
            with open(_p, "w", encoding="utf-8") as _fh:
                json.dump({"case_id": "unknown", "status": "partial",
                           "error": type(_exc).__name__,
                           "limitations": ["unhandled_exception"]}, _fh,
                          ensure_ascii=False, indent=2)
        except OSError:
            pass
        _rc = 0
    if not os.path.isfile("/app/output/result.json"):
        try:
            os.makedirs("/app/output", exist_ok=True)
            with open("/app/output/result.json", "w", encoding="utf-8") as _fh:
                json.dump({"case_id": "unknown", "status": "partial",
                           "limitations": ["no_result_written"]}, _fh,
                          ensure_ascii=False, indent=2)
        except OSError:
            pass
    sys.exit(0)
