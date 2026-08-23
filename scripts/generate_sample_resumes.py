from pathlib import Path

def create_simple_pdf(filename: str, title: str, summary: str, skills: str, projects: str):
    content = f"""%PDF-1.4
1 0 obj
<< /Type /Catalog /Pages 2 0 R >>
endobj
2 0 obj
<< /Type /Pages /Kids [3 0 R] /Count 1 >>
endobj
3 0 obj
<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Contents 4 0 R /Resources << /Font << /F1 5 0 R /F2 6 0 R >> >> >>
endobj
4 0 obj
<< /Length 500 >>
stream
BT
/F1 20 Tf
50 720 Td
({title}) Tj
/F2 12 Tf
0 -30 Td
(Candidate: Revanth - B.Tech CSE | Game Developer) Tj
0 -20 Td
(Email: candidate.revanth@gmail.com | GitHub: github.com/re9ant) Tj
/F1 14 Tf
0 -35 Td
(Executive Summary) Tj
/F2 10 Tf
0 -18 Td
({summary}) Tj
/F1 14 Tf
0 -35 Td
(Core Competencies & Technologies) Tj
/F2 10 Tf
0 -18 Td
({skills}) Tj
/F1 14 Tf
0 -35 Td
(Featured Projects & Experience) Tj
/F2 10 Tf
0 -18 Td
({projects}) Tj
ET
endstream
endobj
5 0 obj
<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica-Bold >>
endobj
6 0 obj
<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>
endobj
xref
0 7
0000000000 65535 f 
0000000009 00000 n 
0000000058 00000 n 
0000000115 00000 n 
0000000244 00000 n 
0000000800 00000 n 
0000000870 00000 n 
trailer
<< /Size 7 /Root 1 0 R >>
startxref
935
%%EOF"""

    target = Path("resumes") / filename
    target.parent.mkdir(parents=True, exist_ok=True)
    with open(target, "wb") as f:
        f.write(content.encode("latin1"))
    print(f"Generated {target}")

if __name__ == "__main__":
    create_simple_pdf(
        "unity_gameplay.pdf",
        "Unity Gameplay Programmer Resume",
        "Game Developer specializing in Unity, C#, 3D combat, and AI mechanics.",
        "Languages: C#, Python | Engine: Unity | Systems: NavMesh, Behavior Trees, ScriptableObjects",
        "Chronicles of the Void: Developed full combat loop, boss AI, and player controller in Unity."
    )
    create_simple_pdf(
        "unity_tools.pdf",
        "Unity Tools & UI Programmer Resume",
        "Specialized in Unity Editor Scripting, UI Toolkit, uGUI, and custom developer tooling.",
        "Skills: C#, UI Toolkit, uGUI, GraphView, Custom Inspectors, Serialization",
        "Dialogue & Quest Node Editor: Custom node-based authoring tool reducing designer setup by 50%."
    )
    create_simple_pdf(
        "backend_software_engineer.pdf",
        "Backend Software Engineer Resume",
        "Software Engineer with expertise in Python, FastAPI, relational databases, and REST APIs.",
        "Languages: Python, C#, SQL | Frameworks: FastAPI, SQLAlchemy, Redis, Docker",
        "Job Application Automation Engine: High-performance async microservice with SQLite/Excel sync."
    )
    create_simple_pdf(
        "fullstack_developer.pdf",
        "Full Stack Developer Resume",
        "Full Stack Engineer building modern web apps with TypeScript, React, and FastAPI.",
        "Tech Stack: TypeScript, React, Tailwind CSS, Alpine.js, Python, REST APIs",
        "Autonomous Application Dashboard: Reactive SPA frontend for job scraping and tracking."
    )
