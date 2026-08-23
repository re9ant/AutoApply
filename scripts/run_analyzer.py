import argparse
import asyncio
import os
import sys
from pathlib import Path

# Force UTF-8 standard output for Windows terminal support
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

# Add project root to sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from app.services.application_service import application_service

console = Console(force_terminal=True, legacy_windows=False)

SAMPLE_UNITY_GAMEPLAY_JD = """Unity Gameplay Programmer - Phoenix Interactive
Location: Remote (US / Global)
Employment Type: Full-time

About the Role:
Phoenix Interactive is crafting a high-octane 3D action roguelite title built in Unity. We are seeking a talented Gameplay Programmer to bring our player character abilities, enemy combat behaviors, and core game systems to life.

Key Responsibilities:
• Implement dynamic third-person player character mechanics, fluid combat combos, and responsive animation integration.
• Collaborate with game designers to prototype and refine modular gameplay abilities using C# and ScriptableObjects.
• Build scalable enemy AI behaviors (Behavior Trees, state machines, and NavMesh navigation).
• Author clean UI screens and custom developer tools/inspectors using Unity UI Toolkit and uGUI.
• Profile and optimize CPU/memory usage to maintain 60 FPS performance.

Qualifications:
• Strong programming proficiency in C# with solid understanding of object-oriented architecture and design patterns.
• 1+ years of experience in game development with Unity (gameplay systems, physics, math, and UI).
• Hands-on experience developing combat mechanics, character controllers, or enemy AI.
• Bachelor's degree in Computer Science, Game Engineering, or equivalent practical experience.
• Familiarity with Git version control and modern team development pipelines.

Nice to Have:
• Experience with custom Unity Editor tooling / GraphView.
• Basic knowledge of HLSL/ShaderLab or Unity Universal Render Pipeline (URP).
• Shipped or completed playable indie/game jam projects.

Apply at: https://careers.phoenixinteractive.example.com/jobs/gameplay-programmer
"""


async def main():
    parser = argparse.ArgumentParser(description="Analyze a Game Developer Job Description and synchronize tracking.")
    parser.add_argument("--file", type=str, help="Path to a text file containing the job description")
    parser.add_argument("--url", type=str, default="https://careers.phoenixinteractive.example.com/jobs/gameplay-programmer", help="Application URL")
    parser.add_argument("--sample", action="store_true", help="Use built-in sample Unity Gameplay Programmer JD")

    args = parser.parse_args()

    if args.file:
        with open(args.file, "r", encoding="utf-8") as f:
            jd_text = f.read()
    else:
        jd_text = SAMPLE_UNITY_GAMEPLAY_JD

    console.print(Panel.fit("[bold green]Autonomous Game Dev Job Application Agent - JD Analyzer & Scorer[/bold green]"))

    console.print("\n[bold cyan]1. Processing Job Posting...[/bold cyan]")
    app_record, score = await application_service.process_job_posting(
        raw_jd_text=jd_text,
        application_url=args.url,
        source="Phoenix Careers"
    )

    # Output Results Table
    summary_table = Table(title="[bold yellow]Job Analysis & Match Score Report[/bold yellow]")
    summary_table.add_column("Field", style="bold white")
    summary_table.add_column("Result", style="cyan")

    summary_table.add_row("Application ID", app_record.application_id)
    summary_table.add_row("Company", app_record.company)
    summary_table.add_row("Job Title", app_record.job_title)
    summary_table.add_row("Location", app_record.location or "Unknown")
    summary_table.add_row("Match Score", f"[bold green]{score.total_score:.1f}%[/bold green]")
    summary_table.add_row("Decision Status", f"[bold magenta]{app_record.status.value}[/bold magenta]")
    summary_table.add_row("Recommended Resume", f"[bold yellow]{score.recommended_resume_filename}[/bold yellow]")

    console.print(summary_table)

    # Category Scores Breakdown
    category_table = Table(title="[bold yellow]Category Scoring Breakdown[/bold yellow]")
    category_table.add_column("Category", style="bold white")
    category_table.add_column("Points", justify="right", style="green")
    category_table.add_column("Max", justify="right", style="dim")
    category_table.add_column("Evaluation Notes", style="white")

    for cat_name, cat in score.category_scores.items():
        category_table.add_row(
            cat_name,
            f"{cat.awarded_points:.1f}",
            f"{cat.max_points:.1f}",
            cat.reason
        )

    console.print(category_table)

    # Strengths & Gaps
    if score.key_strengths:
        console.print("\n[bold green][+] Key Candidate Strengths:[/bold green]")
        for s in score.key_strengths:
            console.print(f"  * {s}")

    if score.key_gaps:
        console.print("\n[bold red][!] Gaps / Missing Requirements:[/bold red]")
        for g in score.key_gaps:
            console.print(f"  * {g}")

    console.print("\n[bold green][+] Excel Workbook Synchronized successfully at 'data/tracker.xlsx'![/bold green]\n")


if __name__ == "__main__":
    asyncio.run(main())
