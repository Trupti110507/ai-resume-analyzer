"""
AI Interview page of the Streamlit app.

A candidate chooses a role, experience level and interview type. The AI
interviewer (Emma) asks the questions out loud in a US English voice inside a
video-call style room, listens to each spoken answer, asks follow-up questions,
and at the end gives a full report:
- answer quality for every question (from the AI interviewer),
- speaking skills (from the Voice Interview Analysis Module),
- video presence: face in view, eye contact and smiling (measured in the browser;
  the video itself is never recorded or sent to the server).
"""

import base64
import os
import shutil
import tempfile

import streamlit as st
import streamlit.components.v1 as components

import database
import english_level
import interviewer
import speech_analysis
from matching import match_skills
from skill_identification import find_skills
from text_extraction import ResumeError, extract_text

HERE = os.path.dirname(os.path.abspath(__file__))


def _room_folder():
    """The interview room is one HTML file (interview_room.html); Streamlit serves it from a folder as index.html."""
    folder = os.path.join(tempfile.gettempdir(), "resume_analysis_interview_room")
    os.makedirs(folder, exist_ok=True)
    shutil.copyfile(os.path.join(HERE, "interview_room.html"), os.path.join(folder, "index.html"))
    return folder


interview_room = components.declare_component("interview_room", path=_room_folder())

STATE = "ai_interview"
MAX_ANSWER_SECONDS = 180
WEIGHTS = {"content": 0.55, "communication": 0.30, "presence": 0.15}


# ------------------------------------------------------------ the session

def start_interview(config):
    questions, used_ai = interviewer.plan_questions(config)
    name = interviewer.INTERVIEWER_NAME
    greeting = (f"Hi, I'm {name}. Thanks for joining me today. This is your interview for the {config['role']} role. "
                f"I'll ask you about {len(questions)} questions. Take your time, and answer as you would in a real interview. "
                "Let's begin. ")
    st.session_state[STATE] = {
        "config": config, "questions": questions, "ai_used": used_ai, "turns": [], "main_index": 0,
        "follow_ups": 0, "turn_id": 1, "current": {"question": questions[0], "kind": "main"},
        "say": greeting + questions[0], "done": False, "processed": [], "report": None,
    }


def transcribe_any(audio, load_local_model):
    """Speech to text: the fast free online service first, the model on this server as a backup."""
    if interviewer.api_key():
        try:
            words = interviewer.transcribe_online(audio, speech_analysis.FILLER_PROMPT)
            if words:
                return words
        except Exception:
            pass
    return speech_analysis.transcribe(audio, load_local_model())


def compact_speech(result):
    if not result:
        return None
    keys = ["duration", "word_count", "wpm", "pauses", "long_pauses", "fillers", "filler_total", "repeats",
            "unclear_words", "median_pitch", "pitch_range", "average_db", "grammar", "scores", "overall", "band",
            "suggestions"]
    return {k: result[k] for k in keys}


def process_answer(iv, value, load_local_model):
    config, current = iv["config"], iv["current"]
    answer, speech = "", None
    seconds = float(value.get("seconds") or 0)
    if not value.get("skipped") and value.get("audio_b64"):
        try:
            audio = speech_analysis.load_audio(base64.b64decode(value["audio_b64"]))
        except Exception:
            audio = None
        if audio is not None and len(audio) / speech_analysis.SAMPLE_RATE >= 1.5:
            try:
                words = transcribe_any(audio, load_local_model)
            except Exception:
                words = []          # speech could not be turned into text; treated as no answer
            answer = " ".join(w["word"] for w in words).strip()
            if words and len(audio) / speech_analysis.SAMPLE_RATE >= 3:
                speech = compact_speech(speech_analysis.analyze_speech(audio, words, find_skills(answer)))

    follow_up_allowed = current["kind"] == "main" and iv["follow_ups"] < interviewer.MAX_FOLLOW_UPS
    evaluation, used_ai = interviewer.evaluate_answer(config, current["question"], answer, follow_up_allowed)
    iv["ai_used"] = iv["ai_used"] or used_ai
    iv["turns"].append({"question": current["question"], "kind": current["kind"], "answer": answer,
                        "seconds": round(seconds, 1), "evaluation": evaluation, "speech": speech,
                        "video": value.get("video") or {"measured": False}})

    reaction = evaluation["reaction"] or "Thank you."
    if evaluation.get("follow_up") and follow_up_allowed:
        iv["follow_ups"] += 1
        iv["current"] = {"question": evaluation["follow_up"], "kind": "follow-up"}
        iv["say"] = f"{reaction} {evaluation['follow_up']}"
    else:
        iv["main_index"] += 1
        if iv["main_index"] < len(iv["questions"]):
            question = iv["questions"][iv["main_index"]]
            lead = "And here's my last question. " if iv["main_index"] == len(iv["questions"]) - 1 else ""
            iv["current"] = {"question": question, "kind": "main"}
            iv["say"] = f"{reaction} {lead}{question}"
        else:
            finish_interview(iv, closing_reaction=reaction)
            return
    iv["turn_id"] += 1


def finish_interview(iv, closing_reaction=""):
    closing = ("That brings us to the end of the interview. Thank you for your time today. "
               "Your detailed feedback report is ready below the video.")
    iv["done"] = True
    iv["turn_id"] += 1
    iv["current"] = {"question": closing, "kind": "closing"}
    iv["say"] = f"{closing_reaction} {closing}".strip()
    if iv["turns"]:
        iv["report"] = build_report(iv)
        iv["report_id"] = database.save_ai_interview(st.session_state["user_id"], iv["report"])


def build_report(iv):
    turns = iv["turns"]
    summary, used_ai = interviewer.final_summary(iv["config"], turns)

    content = sum(t["evaluation"]["score"] for t in turns) / len(turns) * 10
    spoken = [t for t in turns if t["speech"]]
    communication = (sum(t["speech"]["overall"] * t["speech"]["duration"] for t in spoken)
                     / sum(t["speech"]["duration"] for t in spoken)) if spoken else None
    measured = [t["video"] for t in turns if t["video"].get("measured")]
    if measured:
        samples = sum(v["samples"] for v in measured)
        average = {k: sum(v[k] * v["samples"] for v in measured) / samples
                   for k in ("face_visible", "looking", "smiling", "multiple_faces")}
        presence = 100 * (0.35 * average["face_visible"] + 0.5 * average["looking"]
                          + 0.15 * min(1.0, average["smiling"] * 4)) - 30 * average["multiple_faces"]
        presence = max(0.0, min(100.0, presence))
    else:
        average, presence = None, None

    job_skills = iv["config"].get("job_skills") or []
    job_fit = None
    if job_skills:
        discussed = set(find_skills(" ".join(t["answer"] for t in turns)))
        covered = [skill for skill in job_skills if skill in discussed]
        job_fit = {"required": job_skills, "covered": covered,
                   "not_covered": [skill for skill in job_skills if skill not in discussed],
                   "missing_from_resume": iv["config"].get("missing_skills") or []}

    all_answers = " ".join(t["answer"] for t in turns if t["answer"])
    rule_level = english_level.estimate(all_answers, [t["speech"] for t in turns])
    english, _ai = interviewer.assess_english(turns, rule_level)

    parts = {"content": content, "communication": communication, "presence": presence}
    available = {k: v for k, v in parts.items() if v is not None}
    overall = sum(v * WEIGHTS[k] for k, v in available.items()) / sum(WEIGHTS[k] for k in available)
    return {
        "config": {k: v for k, v in iv["config"].items() if k not in ("resume_text", "job_description")},
        "turns": turns, "job_fit": job_fit, "english": english, "summary": summary, "ai_used": iv["ai_used"] or used_ai, "video": average,
        "scores": {"content": round(content, 1), "communication": round(communication, 1) if communication is not None else None,
                   "presence": round(presence, 1) if presence is not None else None, "overall": round(overall, 1)},
    }


# -------------------------------------------------------------- the report

def percent(value):
    return f"{value * 100:.0f}%"


def show_english_level(english):
    """English level block: CEFR scale with the current level and the B2 goal, criteria, mistakes and the plan."""
    st.markdown("#### Your English level")
    level = english.get("level") if english else None
    if not level:
        st.write((english or {}).get("summary") or "Not enough speech to estimate your English level. "
                 "Give longer answers (at least a few sentences each).")
        return
    current, target = english_level.level_index(level), english_level.level_index(english_level.TARGET)
    cells = []
    for i, name in enumerate(english_level.LEVELS):
        cls = "el-cell"
        if i == current:
            cls += " el-now"
        elif i < current:
            cls += " el-past"
        if name in ("B2", "B2+"):
            cls += " el-goal"
        cells.append(f'<div class="{cls}">{name}</div>')
    st.markdown(f"""
<div class="el-wrap">
  <div class="el-head"><div class="el-level">{level}</div>
    <div><div class="el-name">{english_level.name(level)}</div><div class="el-gap">{english_level.gap_to_target(level)}</div></div></div>
  <div class="el-scale">{''.join(cells)}</div>
  <div class="el-legend"><span class="el-key el-key-now"></span>Your level <span class="el-key el-key-goal"></span>Goal: B2 or B2+</div>
</div>""", unsafe_allow_html=True)
    st.write(english.get("summary") or english_level.DESCRIPTIONS.get(level, ""))
    criteria = english.get("criteria") or {}
    if criteria:
        st.markdown(" | ".join(f"**{k}:** {v}" for k, v in criteria.items()))
    mistakes = english.get("mistakes") or []
    if mistakes:
        st.markdown("**Mistakes from your answers**")
        lines = []
        for m in mistakes:
            line = f"- You said \u201c{m['said']}\u201d"
            if m.get("better"):
                line += f" \u2192 say \u201c{m['better']}\u201d"
            if m.get("why"):
                line += f" ({m['why']})"
            lines.append(line)
        st.markdown("\n".join(lines))
    personal = english.get("tips") or []
    plan = english_level.plan_tips(level)
    goal = "B2+" if current < english_level.level_index("B2+") else english_level.LEVELS[min(current + 1, len(english_level.LEVELS) - 1)]
    if personal:
        st.markdown(f"**What to work on first**")
        st.markdown("\n".join(f"- {t}" for t in personal))
    if plan:
        st.markdown(f"**Step-by-step plan from {level} to {goal}**")
        st.markdown("\n".join(f"{i}. {t}" for i, t in enumerate([t for t in plan if t not in personal], start=1)))
    st.caption("CEFR estimate from your spoken answers"
               + (" by the AI examiner." if english.get("method") == "ai" else " using measured speech features.")
               + " Practice guidance, not an official certificate.")


def show_ai_report(report, key_prefix="live"):
    scores, summary, config = report["scores"], report["summary"], report["config"]
    st.subheader("Interview report")
    st.caption(" | ".join(x for x in [config["role"], config["level"], config["type"],
                                       "Tailored to a job description" if config.get("job_skills") else ""] if x))

    def bar(label, value):
        if value is None:
            return (f'<div class="ri-row"><span>{label}</span><span class="ri-track"></span>'
                    f'<span class="ri-num ri-na">Not measured</span></div>')
        return (f'<div class="ri-row"><span>{label}</span><span class="ri-track"><i style="width:{value:.0f}%"></i></span>'
                f'<span class="ri-num">{value:.0f}</span></div>')

    verdict = summary.get("verdict") or ""
    st.markdown(f"""
<div class="ri-band">
  <div class="ri-score"><div class="ri-big">{scores['overall']:.0f}<small>/100</small></div>
    <div class="ri-verdict">{verdict}</div></div>
  <div class="ri-bars">{bar("Answer quality", scores["content"])}{bar("Speaking skills", scores["communication"])}{bar("Video presence", scores["presence"])}</div>
</div>""", unsafe_allow_html=True)

    if summary.get("summary"):
        st.write(summary["summary"])
    left, right = st.columns(2)
    with left:
        st.markdown("**Strengths**")
        st.markdown("\n".join(f"- {s}" for s in summary.get("strengths") or []) or "-")
    with right:
        st.markdown("**To improve**")
        st.markdown("\n".join(f"- {s}" for s in summary.get("improvements") or []) or "-")

    if report.get("english") is not None:
        show_english_level(report["english"])

    fit = report.get("job_fit")
    if fit:
        st.markdown(f"**Job requirements covered in your answers: {len(fit['covered'])} of {len(fit['required'])}**")
        st.markdown("\n".join([
            f"- Discussed: {', '.join(fit['covered']) or 'none'}",
            f"- Not discussed: {', '.join(fit['not_covered']) or 'none'}",
        ] + ([f"- Required by the job but not on your resume: {', '.join(fit['missing_from_resume'])}"]
             if fit["missing_from_resume"] else [])))

    video = report.get("video")
    if video:
        st.markdown("**Video presence** (measured on your device; the video was not recorded)")
        st.markdown("\n".join([
            f"- Face visible in the camera: {percent(video['face_visible'])} of the time",
            f"- Eye contact (looking at the screen or camera): {percent(video['looking'])} of the time",
            f"- Smiling: {percent(video['smiling'])} of the time",
        ] + ([f"- Another face was in view {percent(video['multiple_faces'])} of the time"] if video["multiple_faces"] > 0.05 else [])))
    else:
        st.caption("Video presence was not measured (the face-tracking model could not load in this browser).")

    st.markdown("**Question by question**")
    for number, turn in enumerate(report["turns"], start=1):
        ev = turn["evaluation"]
        kind = " (follow-up)" if turn["kind"] == "follow-up" else ""
        with st.expander(f"{number}. {turn['question']}{kind}  |  Score {ev['score']}/10"):
            st.markdown("**Your answer**")
            st.write(turn["answer"] or "No answer was recorded.")
            if ev.get("strengths"):
                st.markdown(f"**What went well:** {ev['strengths']}")
            if ev.get("improvements"):
                st.markdown(f"**To improve:** {ev['improvements']}")
            if ev.get("better_answer"):
                st.markdown(f"**A strong answer would:** {ev['better_answer']}")
            for note in ev.get("english_notes") or []:
                st.markdown(f"**English:** \u201c{note['said']}\u201d \u2192 \u201c{note['better']}\u201d")
            sp = turn.get("speech")
            if sp:
                fillers = ", ".join(f"{k} ({v})" for k, v in sp["fillers"].items()) or "none"
                st.caption(f"Speaking: {sp['overall']:g}/100 ({sp['band']}) | pace {sp['wpm']:.0f} words/min | "
                           f"filler words: {fillers} | pronunciation clarity {sp['scores']['Pronunciation clarity']:g}")
            v = turn.get("video") or {}
            if v.get("measured"):
                st.caption(f"Video: face visible {percent(v['face_visible'])}, eye contact {percent(v['looking'])}, "
                           f"smiling {percent(v['smiling'])}")

    tips = []
    for turn in report["turns"]:
        for tip in (turn.get("speech") or {}).get("suggestions", []):
            if tip not in tips and not tip.startswith("Well spoken"):
                tips.append(tip)
    if tips:
        st.markdown("**Speaking tips**")
        st.markdown("\n".join(f"- {t}" for t in tips[:6]))

    st.download_button("Download this report", report_text(report), file_name="ai_interview_report.txt",
                       key=f"{key_prefix}_download")
    if not report.get("ai_used"):
        st.caption("Basic mode: questions and answer feedback came from the built-in rules, because the AI service was not available.")
    st.info("This is practice feedback generated automatically. It is not a hiring decision.")


def report_text(report):
    s, c = report["scores"], report["config"]
    lines = [f"AI interview report: {c['role']} ({c['level']}, {c['type']})", "",
             f"Overall score: {s['overall']} / 100   {report['summary'].get('verdict', '')}",
             f"Answer quality: {s['content']}   Speaking skills: {s['communication']}   Video presence: {s['presence']}", "",
             report["summary"].get("summary", ""), "", "Strengths:"]
    lines += [f"- {x}" for x in report["summary"].get("strengths") or []]
    lines += ["", "To improve:"] + [f"- {x}" for x in report["summary"].get("improvements") or []]
    english = report.get("english") or {}
    if english.get("level"):
        lines += ["", f"English level (CEFR estimate): {english['level']} ({english_level.name(english['level'])}). "
                  + english_level.gap_to_target(english["level"]), english.get("summary", "")]
        lines += [f"- Tip: {t}" for t in (english.get("tips") or []) + english_level.plan_tips(english["level"])]
    for n, t in enumerate(report["turns"], start=1):
        ev = t["evaluation"]
        lines += ["", f"Question {n}: {t['question']}", f"Answer: {t['answer'] or '(no answer)'}",
                  f"Score: {ev['score']}/10", f"What went well: {ev.get('strengths', '')}",
                  f"To improve: {ev.get('improvements', '')}", f"A strong answer would: {ev.get('better_answer', '')}"]
    return "\n".join(lines)


# ---------------------------------------------------------------- the page

SAMPLES = os.path.join(HERE, "samples")


def use_sample_job():
    with open(os.path.join(SAMPLES, "sample_job_description.txt"), encoding="utf-8") as f:
        st.session_state["ai_role"] = "Junior Python Developer"
        st.session_state["ai_jd"] = f.read()
    st.session_state["ai_sample_resume"] = True


def show_setup():
    st.write("Practise a full video interview for the job you want. Emma, the AI interviewer, asks the questions "
             "out loud, listens to your answers, follows up like a real interviewer, and gives you a detailed report.")
    if interviewer.api_key():
        st.caption("AI interviewer connected. Questions are written for your role, job description and resume.")
    else:
        st.warning("Basic mode: no AI key is set, so questions come from a built-in list and feedback from rules. "
                   "Add a free Groq key in the app settings to switch on the AI interviewer (see README).")

    form_column, guide_column = st.columns([3, 2], gap="large")
    with form_column:
        st.button("Fill in the sample job and resume", on_click=use_sample_job, type="tertiary")
        with st.form("ai_interview_setup", border=False):
            role = st.text_input("Job title", key="ai_role", max_chars=120,
                                 placeholder="For example: Python Developer, Staff Nurse, Sales Executive")
            job_description = st.text_area(
                "Job description (optional)", key="ai_jd", height=180,
                placeholder="Paste the job advert. Emma will ask about its duties and required skills.")
            resume = st.file_uploader("Your resume (optional, PDF or DOCX)", type=["pdf", "docx"])
            if st.session_state.get("ai_sample_resume"):
                st.caption("If you don't upload a resume, the sample resume (sample_resume.pdf) is used.")
            left, right = st.columns(2)
            level = left.selectbox("Your experience", interviewer.LEVELS)
            kind = right.selectbox("Interview type", interviewer.TYPES)
            count = st.slider("Main questions", 3, 8, 5, help="Emma may add up to two follow-up questions.")
            start = st.form_submit_button("Start interview", type="primary", use_container_width=False)

    with guide_column:
        st.markdown("**Before you start**")
        st.markdown(
            "- Use Chrome or Edge on a laptop or desktop.\n"
            "- Sit in a quiet, well-lit room, facing the camera.\n"
            "- Use headphones or speakers so you hear Emma clearly.\n"
            "- Allow about 10 to 20 minutes.")
        st.markdown("**Your report covers**")
        st.markdown(
            "- Answer quality for every question, with what a strong answer includes\n"
            "- Speaking: pronunciation, fluency, pace, tone and English\n"
            "- Video presence: eye contact, face in view and smiling\n"
            "- How well your answers covered the job's requirements")
        st.caption("Your video stays on your device. Only your spoken answers are sent for analysis.")

    if start:
        if not role.strip():
            st.error("Enter the job title you are preparing for.")
            return
        resume_text, resume_skills = "", []
        name, data = None, None
        if resume is not None:
            name, data = resume.name, resume.getvalue()
        elif st.session_state.get("ai_sample_resume"):
            name = "sample_resume.pdf"
            with open(os.path.join(SAMPLES, name), "rb") as f:
                data = f.read()
        if data is not None:
            try:
                _kind, resume_text = extract_text(name, data)
                resume_skills = find_skills(resume_text)
            except ResumeError as error:
                st.error(f"{name}: {error}")
                return
        job_description = (job_description or "").strip()[:20000]
        job_skills = find_skills(job_description) if job_description else []
        missing = match_skills(resume_skills, job_skills)[1] if (job_skills and resume_text) else []
        config = {"role": role.strip(), "level": level, "type": kind, "count": count,
                  "resume_text": resume_text, "resume_skills": resume_skills,
                  "job_description": job_description, "job_skills": job_skills, "missing_skills": missing}
        with st.spinner("Emma is preparing your interview..."):
            start_interview(config)
        st.rerun()


def show_ai_interview_page(user, load_local_model):
    st.header("AI interview")
    iv = st.session_state.get(STATE)
    if iv is None:
        show_setup()
        return

    config = iv["config"]
    total = len(iv["questions"])
    index = min(iv["main_index"] + 1, total)
    if iv["done"]:
        label = "Interview complete"
    elif iv["current"]["kind"] == "follow-up":
        label = f"Follow-up to question {index} of {total}"
    else:
        label = f"Question {index} of {total}"

    value = interview_room(
        turn_id=iv["turn_id"], say=iv["say"], question=iv["current"]["question"], label=label,
        role=config["role"], q_index=index, q_total=total,
        mode="end" if iv["done"] else "ask", max_seconds=MAX_ANSWER_SECONDS,
        interviewer_name=interviewer.INTERVIEWER_NAME, key="interview_room", default=None)

    if (isinstance(value, dict) and not iv["done"] and value.get("turn_id") == iv["turn_id"]
            and value.get("turn_id") not in iv["processed"]):
        iv["processed"].append(value["turn_id"])
        if value.get("end"):
            if iv["turns"]:
                with st.spinner("Emma is writing your report..."):
                    finish_interview(iv)
            else:
                st.session_state.pop(STATE, None)
        else:
            with st.spinner("Emma is listening to your answer..."):
                process_answer(iv, value, load_local_model)
        st.rerun()

    if not iv["done"]:
        st.caption("After Emma asks a question, answer out loud and click \u201cI've finished my answer\u201d. "
                   "Each answer can be up to 3 minutes.")
    elif iv.get("report"):
        show_ai_report(iv["report"])

    if iv["done"] and st.button("Start a new interview", type="primary"):
        st.session_state.pop(STATE, None)
        st.rerun()


def show_ai_history(user):
    rows = database.list_ai_interviews(user["user_id"])
    if not rows:
        return False
    st.subheader("AI interviews")
    for row in rows:
        with st.expander(f"{row['analyzed_at'][:16]} | {row['role']}: {row['overall_score']:g} / 100"):
            show_ai_report(row["details"], key_prefix=f"history_{row['ai_interview_id']}")
            if st.button("Delete this interview", key=f"delete_ai_{row['ai_interview_id']}"):
                database.delete_ai_interview(row["ai_interview_id"], user["user_id"])
                st.rerun()
    return True
