import os, re, json, time, requests
from groq import Groq

client = Groq(api_key=os.environ["GROQ_API_KEY"])
MODEL = "openai/gpt-oss-20b"
PROFILE = "Student interested in AI/ML and GenAI, open to online events, prefers beginner-friendly and good prizes."

def fetch_devpost(pages=6):
    events = []
    for p in range(1, pages + 1):
        r = requests.get(
            "https://devpost.com/api/hackathons",
            params={"page": p, "status[]": ["open", "upcoming"]},
            headers={"User-Agent": "Mozilla/5.0"},
            timeout=20,
        )
        r.raise_for_status()
        items = r.json().get("hackathons", [])
        if not items:
            break
        events += items
    return events

def clean(e):
    prize = re.sub(r"<[^>]+>", "", e.get("prize_amount") or "").strip()
    loc = e["displayed_location"]["location"]
    return {
        "title": e["title"],
        "link": e["url"],
        "location": loc,
        "online": loc.lower() == "online",
        "deadline": e["submission_period_dates"],
        "time_left": e["time_left_to_submission"],
        "prize": prize or "N/A",
        "themes": [t["name"] for t in e["themes"]],
        "organizer": e["organization_name"],
        "registrations": e["registrations_count"],
        "invite_only": e["invite_only"],
    }

def rank_batch(batch):
    lines = "\n".join(
        f"{i}|{e['title']}|{', '.join(e['themes'])}|{e['prize']}|{e['time_left']}"
        for i, e in enumerate(batch)
    )
    prompt = f"""Profile: {PROFILE}
Score each hackathon 0-10 for relevance to this profile.
Return ONLY a JSON list like [{{"i":0,"score":8,"reason":"short reason"}}].

{lines}"""
    r = client.chat.completions.create(
        model=MODEL,
        messages=[{"role": "user", "content": prompt}],
        max_tokens=3000,
    )
    text = r.choices[0].message.content
    return json.loads(re.search(r"\[.*\]", text, re.S).group())

events = [clean(e) for e in fetch_devpost() if not e["invite_only"]]

for start in range(0, len(events), 15):
    batch = events[start:start + 15]
    try:
        for s in rank_batch(batch):
            batch[s["i"]]["score"] = s["score"]
            batch[s["i"]]["reason"] = s["reason"]
    except Exception as ex:
        print("Batch failed:", start, type(ex).__name__, ex)
    time.sleep(3)

ranked = sorted(events, key=lambda e: e.get("score", 0), reverse=True)
with open("data.json", "w") as f:
    json.dump(ranked, f, indent=2)
print("Saved", len(ranked), "events")
