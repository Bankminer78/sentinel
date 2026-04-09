"""Interventions — friction before hard-blocks. State machines."""
import random, time, json, httpx, base64
from sentinel import db

KINDS = {"countdown", "breathing", "typing", "negotiate", "math", "wait", "photo"}

PHRASES = [
    "I am choosing to stay focused on my goals today",
    "Every moment I resist distraction I become stronger",
    "My attention is my most valuable resource right now",
    "I will honor the commitment I made to myself today",
    "Deep work is how meaningful things get built here",
    "Short term pleasure is not worth long term regret",
    "I control my impulses they do not control me today",
    "The work I am avoiding is the work that matters most",
    "Discipline now means freedom later in my life",
    "I am the kind of person who finishes what they start",
    "Boredom is the doorway to deep creative thought today",
    "I respect my future self enough to do hard things",
    "Focus is a practice I get better at every day now",
    "The scroll will still be there when my work is done",
    "I choose intention over distraction in this moment",
]

BREATHING_PATTERNS = {
    "478": {"name": "4-7-8", "steps": [("Inhale", 4), ("Hold", 7), ("Exhale", 8)], "cycles": 3},
    "box": {"name": "Box", "steps": [("Inhale", 4), ("Hold", 4), ("Exhale", 4), ("Hold", 4)], "cycles": 4},
}

MAX_ATTEMPTS = 3


def generate_typing_challenge(length: int = 50) -> str:
    candidates = [p for p in PHRASES if len(p) >= length]
    return random.choice(candidates or PHRASES)


def generate_math_challenge() -> tuple[str, int]:
    op = random.choice(["+", "-", "*"])
    if op == "*":
        a, b = random.randint(2, 12), random.randint(2, 12)
        return (f"{a} * {b}", a * b)
    a, b = random.randint(10, 99), random.randint(10, 99)
    if op == "+":
        return (f"{a} + {b}", a + b)
    return (f"{a} - {b}", a - b)


def create_intervention(conn, kind: str, context: dict) -> dict:
    if kind not in KINDS:
        raise ValueError(f"unknown intervention kind: {kind}")
    state, prompt, expected, deadline = {}, "", None, None
    now = time.time()
    if kind == "countdown":
        dur = int(context.get("duration", 5))
        deadline = now + dur
        state = {"deadline": deadline}
        prompt = f"Hold on. {dur} seconds to cancel or let this proceed."
    elif kind == "breathing":
        pat = BREATHING_PATTERNS.get(context.get("pattern", "478"), BREATHING_PATTERNS["478"])
        total = sum(s[1] for s in pat["steps"]) * pat["cycles"]
        deadline = now + total
        state = {"pattern": pat, "deadline": deadline}
        prompt = f"Breathe with me: {pat['name']} breathing for {total} seconds."
    elif kind == "typing":
        phrase = generate_typing_challenge(int(context.get("length", 50)))
        state, expected = {"phrase": phrase}, phrase
        prompt = f"Type the following exactly: {phrase}"
    elif kind == "negotiate":
        state = {"turns": [], "granted": False, "minutes": 0}
        prompt = "Why do you need this? Be honest."
    elif kind == "math":
        problem, answer = generate_math_challenge()
        state, expected = {"problem": problem, "answer": answer}, str(answer)
        prompt = f"Solve: {problem}"
    elif kind == "wait":
        dur = int(context.get("duration", 60))
        deadline = now + dur
        state = {"deadline": deadline}
        prompt = f"Wait {dur} seconds. Do nothing."
    elif kind == "photo":
        task = context.get("task", "your committed task")
        state = {"task": task}
        prompt = f"Upload a photo proving you completed: {task}"
    iid = db.save_intervention(conn, kind, context, state)
    return {"id": iid, "kind": kind, "state": state, "prompt": prompt,
            "expected_input": expected, "deadline": deadline}


def get_intervention(conn, intervention_id: int) -> dict | None:
    return db.get_intervention_by_id(conn, intervention_id)


def submit_intervention(conn, intervention_id: int, response: str) -> dict:
    iv = db.get_intervention_by_id(conn, intervention_id)
    if not iv:
        return {"passed": False, "new_state": {}, "feedback": "not found", "remaining_attempts": 0}
    if iv["completed_at"]:
        return {"passed": bool(iv["passed"]), "new_state": iv["state"],
                "feedback": "already completed", "remaining_attempts": 0}
    kind, state = iv["kind"], iv["state"]
    attempts = (iv["attempts"] or 0) + 1
    passed, feedback = False, ""
    now = time.time()
    if kind in ("countdown", "wait", "breathing"):
        deadline = state.get("deadline", 0)
        if kind in ("countdown", "wait") and response == "cancel":
            db.update_intervention(conn, intervention_id, completed_at=now, passed=0, attempts=attempts)
            return {"passed": False, "new_state": state, "feedback": "cancelled", "remaining_attempts": 0}
        if now >= deadline:
            passed, feedback = True, "done"
        else:
            return {"passed": False, "new_state": state,
                    "feedback": f"{max(0, int(deadline - now))}s remaining",
                    "remaining_attempts": MAX_ATTEMPTS - attempts}
    elif kind == "typing":
        if response.strip() == state.get("phrase", "").strip():
            passed, feedback = True, "correct"
        else:
            feedback = "does not match"
    elif kind == "math":
        try:
            passed = int(response.strip()) == state.get("answer")
            feedback = "correct" if passed else "wrong answer"
        except (ValueError, TypeError):
            feedback = "not a number"
    elif kind == "negotiate":
        passed = bool(state.get("granted"))
        feedback = "use ai_negotiate for this kind"
    elif kind == "photo":
        passed = bool(response)
        feedback = "photo accepted" if passed else "no photo"
    db.update_intervention(conn, intervention_id, attempts=attempts, state=state)
    if passed or attempts >= MAX_ATTEMPTS:
        db.update_intervention(conn, intervention_id,
                               completed_at=now, passed=1 if passed else 0)
    return {"passed": passed, "new_state": state, "feedback": feedback,
            "remaining_attempts": max(0, MAX_ATTEMPTS - attempts)}


NEGOTIATE_PROMPT = """You are a strict accountability coach. The user has committed to blocking {domain} because {rule_text}. They want you to unblock it for {minutes} minutes. Their justification: {user_message}.
Decide: grant (with number of minutes, max 15) or deny. If their reason is genuinely productive or important, grant. If it sounds like rationalization (boredom, FOMO, 'just 5 minutes'), deny.
Respond in JSON: {{"granted": true|false, "minutes": N, "response": "your response to them"}}"""


async def ai_negotiate(conn, intervention_id: int, user_message: str, api_key: str) -> dict:
    iv = db.get_intervention_by_id(conn, intervention_id)
    if not iv or iv["kind"] != "negotiate":
        return {"response": "invalid intervention", "granted": False, "minutes": 0}
    ctx, state = iv["context"], iv["state"]
    state.setdefault("turns", []).append({"user": user_message})
    prompt = NEGOTIATE_PROMPT.format(
        domain=ctx.get("domain", "the site"),
        rule_text=ctx.get("rule_text", "you wanted to focus"),
        minutes=ctx.get("minutes", 10),
        user_message=user_message)
    from sentinel.classifier import call_gemini
    raw = await call_gemini(api_key, prompt, max_tokens=300)
    raw = raw.strip().removeprefix("```json").removeprefix("```").removesuffix("```").strip()
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError:
        parsed = {"granted": False, "minutes": 0, "response": "I can't parse that. Denied."}
    granted = bool(parsed.get("granted"))
    minutes = min(int(parsed.get("minutes", 0) or 0), 15)
    state["granted"] = granted
    state["minutes"] = minutes
    state["turns"][-1]["assistant"] = parsed.get("response", "")
    completed = time.time() if granted else None
    db.update_intervention(conn, intervention_id, state=state,
                           passed=1 if granted else 0,
                           completed_at=completed)
    return {"response": parsed.get("response", ""), "granted": granted, "minutes": minutes}


def verify_photo_proof(photo_path: str, task_description: str, api_key: str) -> bool:
    with open(photo_path, "rb") as f:
        data = base64.b64encode(f.read()).decode()
    prompt = (f"The user committed to: {task_description}. They are submitting this photo as proof "
              f"they completed it. Does this photo plausibly show task completion? "
              f"Respond with ONLY 'yes' or 'no'.")
    r = httpx.post(
        f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent?key={api_key}",
        json={"contents": [{"parts": [
            {"text": prompt},
            {"inline_data": {"mime_type": "image/jpeg", "data": data}}]}],
              "generationConfig": {"maxOutputTokens": 10, "temperature": 0}},
        timeout=30)
    r.raise_for_status()
    text = r.json()["candidates"][0]["content"]["parts"][0]["text"].strip().lower()
    return text.startswith("yes")
