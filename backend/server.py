#!/usr/bin/env python3
"""
InternIQ v4 Backend
3 scoring modes:
  - manual  : skills + projects + activity
  - github  : github profile data (fetched by browser, scored here)
  - resume  : resume text keyword analysis
Pure Python stdlib — zero pip installs.
"""

import http.server, json, sqlite3, os, urllib.parse
from datetime import datetime

PORT     = int(os.environ.get("PORT", 8000))
DB_PATH  = os.path.join(os.path.dirname(__file__), "interniq.db")
FRONTEND = os.path.join(os.path.dirname(__file__), "..", "frontend", "public")

# ── DB ────────────────────────────────────────────────────────────────────────
def init_db():
    c = sqlite3.connect(DB_PATH)
    c.execute("""CREATE TABLE IF NOT EXISTS assessments(
        id           INTEGER PRIMARY KEY AUTOINCREMENT,
        name         TEXT,
        mode         TEXT,
        target_role  TEXT,
        final_score  INTEGER,
        badge        TEXT,
        top_skills   TEXT,
        skill_gaps   TEXT,
        roadmap      TEXT,
        extra        TEXT,
        created_at   TEXT)""")
    c.commit(); c.close()

# ── ROLE DATA ─────────────────────────────────────────────────────────────────
ROLE_REQUIRED = {
    "swe":     ["python","java","data structures","algorithms","git","system design","rest api","sql"],
    "ml":      ["python","machine learning","deep learning","tensorflow","pytorch","numpy","pandas","sql"],
    "data":    ["python","sql","pandas","numpy","data analysis","statistics","tableau","r"],
    "web":     ["javascript","react","html","css","node","rest api","git","typescript"],
    "product": ["agile","scrum","communication","problem solving","sql","analytics","user research"],
    "design":  ["figma","ux","user research","css","html","communication","prototyping"],
}

TECH_KW = {
    "python":15,"java":12,"javascript":12,"typescript":10,"c++":10,"c#":9,
    "golang":8,"rust":8,"kotlin":8,"swift":7,"php":6,"ruby":6,"scala":8,
    "react":11,"angular":9,"vue":9,"node":9,"nodejs":9,"django":10,"flask":9,
    "fastapi":8,"express":8,"html":5,"css":5,"tailwind":6,
    "machine learning":14,"deep learning":13,"tensorflow":12,"pytorch":12,
    "scikit":10,"sklearn":10,"pandas":10,"numpy":10,"matplotlib":7,
    "nlp":12,"natural language":11,"computer vision":12,"opencv":9,
    "sql":10,"mysql":9,"postgresql":9,"mongodb":9,"redis":8,"firebase":7,
    "aws":11,"gcp":10,"azure":10,"docker":11,"kubernetes":10,"git":8,
    "linux":7,"bash":6,"ci/cd":9,"devops":9,"microservices":9,
    "data structures":12,"algorithms":12,"dsa":11,"leetcode":7,
    "system design":11,"oop":8,"rest api":10,"api":7,"graphql":8,
    "agile":6,"scrum":6,"communication":5,"problem solving":7,
    "deployed":8,"production":8,"open source":7,"hackathon":7,"kaggle":6,
}

BADGE_LEVELS = [
    (85, "Internship Ready",  "You are highly competitive. Apply confidently to internship roles."),
    (70, "Strong Candidate",  "Solid profile. A few targeted improvements will make you stand out."),
    (55, "Developing",        "Good progress! Follow the roadmap below to boost your score."),
    (40, "Early Stage",       "Keep building. Consistent practice will move your score quickly."),
    (0,  "Needs Foundation",  "Start with core skills and one project. Every expert started here."),
]

def get_badge(score):
    for thr, b, m in BADGE_LEVELS:
        if score >= thr: return b, m
    return "Needs Foundation", ""

# ── MODE 1: MANUAL ────────────────────────────────────────────────────────────
def score_manual(data):
    role     = data.get("targetRole","swe")
    skills   = [s.lower() for s in data.get("skills",[])]
    projects = data.get("projects",[])
    activity = data.get("activity",{})

    # Skills score
    role_kws = ROLE_REQUIRED.get(role,[])
    matched  = [k for k in role_kws if any(k in s for s in skills)]
    sk_score = min(100, round(
        (len(matched)/max(len(role_kws),1))*60 +
        min(40, len(skills)*2.5)
    ))
    gaps = [k for k in role_kws if k not in matched]

    # Projects score
    pr_total = 0
    for p in projects:
        d = (p.get("description","")+" "+p.get("title","")).lower()
        tech = p.get("techStack",[])
        ml   = any(w in d for w in ["machine learning","ml","ai","model","neural","nlp","predict"])
        api  = any(w in d for w in ["api","rest","backend","server","endpoint"])
        db   = any(w in d for w in ["database","sql","mongodb","postgresql","mysql","firebase"])
        dep  = any(w in d for w in ["deploy","docker","cloud","aws","heroku","vercel","production"])
        auth = any(w in d for w in ["auth","login","jwt","oauth","security"])
        sig  = ml*22 + api*15 + db*13 + dep*20 + auth*10
        pr_total += min(100, sig + min(20,len(tech)*4) + min(10,(int(p.get("teamSize",1))-1)*3))
    pr_score = min(100, round((pr_total/max(len(projects),1))*0.8 + min(20,len(projects)*5))) if projects else 0

    # Activity score
    hrs  = min(int(activity.get("hoursPerWeek",0)),40)
    freq = int(activity.get("practiceFrequency",1))
    leet = min(int(activity.get("leetcodeSolved",0)),300)
    hack = min(int(activity.get("hackathons",0)),5)
    oss  = min(int(activity.get("openSource",0)),10)
    plat = len(activity.get("platforms",[]))
    ac_score = min(100, round((hrs/40)*25 + (freq/5)*20 + (leet/300)*25 + hack*5 + oss*3 + min(15,plat*5)))

    final = round(sk_score*0.40 + pr_score*0.35 + ac_score*0.25)
    badge, msg = get_badge(final)

    top_skills = [s for s in data.get("skills",[])][:10]

    roadmap = sorted([
        ("Skill coverage",    sk_score, "🏷️ Learn the missing role-required skills. Build one small project per new skill learned."),
        ("Project depth",     pr_score, "🔧 Build a full-stack project with deployment, database, and authentication on GitHub."),
        ("Coding activity",   ac_score, "⚡ Solve 2 LeetCode problems daily. Attend a hackathon. Contribute to open source."),
    ], key=lambda x:x[1])[:3]

    return {
        "mode":"manual","name":data.get("name","Student"),"role":role,
        "finalScore":final,"badge":badge,"badgeMsg":msg,
        "skillsScore":sk_score,"projectsScore":pr_score,"activityScore":ac_score,
        "skillGaps":gaps[:8],"topSkills":top_skills,
        "roadmap":[{"dim":d,"val":v,"tip":t} for d,v,t in roadmap],
        "breakdown":[
            {"label":"Skill coverage","score":sk_score,"icon":"🏷️"},
            {"label":"Project depth","score":pr_score,"icon":"🔧"},
            {"label":"Coding activity","score":ac_score,"icon":"⚡"},
        ]
    }

# ── MODE 2: GITHUB ────────────────────────────────────────────────────────────
def score_github(data):
    role   = data.get("targetRole","swe")
    gh     = data.get("githubData",{})

    repos      = int(gh.get("repos",0))
    stars      = int(gh.get("stars",0))
    followers  = int(gh.get("followers",0))
    languages  = gh.get("languages",[])
    has_readme = int(gh.get("reposWithDesc",0))
    forks_made = int(gh.get("forksCreated",0))

    repo_score  = min(30, repos*2)
    lang_score  = min(20, len(languages)*4)
    star_score  = min(15, stars*2)
    foll_score  = min(10, followers)
    desc_score  = min(10, has_readme*1.5)
    bio_score   = 5 if gh.get("bio") and gh.get("bio") != "No bio" else 0
    fork_score  = min(10, forks_made*2)
    gh_score    = min(100, round(repo_score+lang_score+star_score+foll_score+desc_score+bio_score+fork_score))

    # Map languages to skill gaps
    lang_skills = [l.lower() for l in languages]
    role_kws    = ROLE_REQUIRED.get(role,[])
    matched     = [k for k in role_kws if any(k in l for l in lang_skills)]
    gaps        = [k for k in role_kws if k not in matched]

    badge, msg = get_badge(gh_score)

    roadmap = []
    if repos < 5:
        roadmap.append({"dim":"Repository count","val":repo_score,"tip":"📂 Create more public repositories. Aim for at least 5–8 original (non-fork) projects."})
    if len(languages) < 3:
        roadmap.append({"dim":"Language diversity","val":lang_score,"tip":"💻 Add projects in languages required for your target role to show versatility."})
    if stars < 3:
        roadmap.append({"dim":"Project visibility","val":star_score,"tip":"⭐ Write detailed READMEs with screenshots. Share your projects on LinkedIn to get stars."})
    if not roadmap:
        roadmap.append({"dim":"Overall GitHub","val":gh_score,"tip":"📂 Keep committing consistently. Daily contributions signal strong work ethic to recruiters."})
    roadmap = roadmap[:3]

    return {
        "mode":"github","name":data.get("name","Student"),"role":role,
        "finalScore":gh_score,"badge":badge,"badgeMsg":msg,
        "githubScore":gh_score,
        "githubData":gh,
        "skillGaps":gaps[:8],"topSkills":languages[:10],
        "roadmap":roadmap,
        "breakdown":[
            {"label":"Repositories","score":min(100,repo_score*3),"icon":"📂"},
            {"label":"Languages","score":min(100,lang_score*5),"icon":"💻"},
            {"label":"Stars & followers","score":min(100,(star_score+foll_score)*4),"icon":"⭐"},
            {"label":"Profile quality","score":min(100,(desc_score+bio_score)*6),"icon":"📝"},
        ]
    }

# ── MODE 3: RESUME ────────────────────────────────────────────────────────────
def score_resume(data):
    role = data.get("targetRole","swe")
    text = data.get("resumeText","").lower()

    found, raw = [], 0
    for kw, pts in TECH_KW.items():
        if kw in text:
            found.append(kw); raw += pts

    role_kws   = ROLE_REQUIRED.get(role,[])
    role_match = [k for k in role_kws if k in text]
    role_pct   = len(role_match)/max(len(role_kws),1)
    gaps       = [k for k in role_kws if k not in text]

    keyword_score  = min(100, round((min(raw,130)/130)*65))
    alignment_score= round(role_pct*100)
    word_count     = len(data.get("resumeText","").split())
    length_score   = min(20, round((min(word_count,400)/400)*20))

    final = min(100, round(keyword_score*0.5 + alignment_score*0.35 + length_score*0.15))
    badge, msg = get_badge(final)

    top_skills = list(dict.fromkeys(found))[:12]

    roadmap = sorted([
        ("Keyword coverage",  keyword_score,   "📄 Add missing role-specific keywords to your resume. Use exact terms from job descriptions."),
        ("Role alignment",    alignment_score, "🎯 Tailor your resume for each role. Highlight projects that match the job requirements."),
        ("Resume completeness", length_score*5,"📝 Add more detail to your experience and projects sections. Aim for 300–500 words of content."),
    ], key=lambda x:x[1])[:3]

    return {
        "mode":"resume","name":data.get("name","Student"),"role":role,
        "finalScore":final,"badge":badge,"badgeMsg":msg,
        "keywordScore":keyword_score,"alignmentScore":alignment_score,"lengthScore":length_score*5,
        "wordCount":word_count,"roleMatch":alignment_score,
        "skillGaps":gaps[:8],"topSkills":top_skills,
        "roadmap":[{"dim":d,"val":v,"tip":t} for d,v,t in roadmap],
        "breakdown":[
            {"label":"Keyword coverage","score":keyword_score,"icon":"🔍"},
            {"label":"Role alignment","score":alignment_score,"icon":"🎯"},
            {"label":"Resume length","score":min(100,length_score*5),"icon":"📝"},
        ]
    }

# ── HTTP HANDLER ──────────────────────────────────────────────────────────────
class H(http.server.SimpleHTTPRequestHandler):
    def __init__(self,*a,**kw): super().__init__(*a,directory=FRONTEND,**kw)
    def log_message(self,f,*a): print(f"[{datetime.now().strftime('%H:%M:%S')}] {f%a}")
    def send_json(self,d,s=200):
        b=json.dumps(d,default=str).encode()
        self.send_response(s)
        self.send_header("Content-Type","application/json")
        self.send_header("Content-Length",len(b))
        self.send_header("Access-Control-Allow-Origin","*")
        self.end_headers(); self.wfile.write(b)
    def read_body(self):
        n=int(self.headers.get("Content-Length",0))
        return json.loads(self.rfile.read(n)) if n else {}
    def do_OPTIONS(self):
        self.send_response(200)
        self.send_header("Access-Control-Allow-Origin","*")
        self.send_header("Access-Control-Allow-Methods","GET,POST,OPTIONS")
        self.send_header("Access-Control-Allow-Headers","Content-Type")
        self.end_headers()
    def do_GET(self):
        p=urllib.parse.urlparse(self.path).path
        if p=="/api/results":
            con=sqlite3.connect(DB_PATH); con.row_factory=sqlite3.Row
            rows=con.execute("SELECT name,mode,target_role,final_score,badge,top_skills,created_at FROM assessments ORDER BY final_score DESC LIMIT 20").fetchall()
            con.close(); self.send_json([dict(r) for r in rows]); return
        if p=="/api/stats":
            con=sqlite3.connect(DB_PATH)
            r=con.execute("SELECT COUNT(*),ROUND(AVG(final_score),1),MAX(final_score) FROM assessments").fetchone()
            con.close(); self.send_json({"total":r[0],"avgScore":r[1] or 0,"topScore":r[2] or 0}); return
        super().do_GET()
    def do_POST(self):
        if self.path=="/api/score":
            try:
                data=self.read_body()
                mode=data.get("mode","manual")
                if   mode=="github": result=score_github(data)
                elif mode=="resume": result=score_resume(data)
                else:                result=score_manual(data)
                con=sqlite3.connect(DB_PATH)
                con.execute("""INSERT INTO assessments
                    (name,mode,target_role,final_score,badge,top_skills,skill_gaps,roadmap,extra,created_at)
                    VALUES(?,?,?,?,?,?,?,?,?,?)""",(
                    result["name"],mode,result["role"],result["finalScore"],result["badge"],
                    json.dumps(result.get("topSkills",[])),
                    json.dumps(result.get("skillGaps",[])),
                    json.dumps(result.get("roadmap",[])),
                    json.dumps({}),datetime.now().isoformat()))
                con.commit(); con.close()
                self.send_json(result)
            except Exception as e:
                import traceback; traceback.print_exc()
                self.send_json({"error":str(e)},500)
        else: self.send_json({"error":"Not found"},404)

if __name__=="__main__":
    init_db()
    print("="*52)
    print("  InternIQ v4 — Internship Readiness Engine")
    print("="*52)
    print(f"  Open  →  http://localhost:{PORT}")
    print(f"  Modes →  Manual | GitHub | Resume")
    print("  Ctrl+C to stop")
    print("="*52)
    http.server.HTTPServer(("",PORT),H).serve_forever()
