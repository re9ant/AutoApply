import sys
from pathlib import Path

# Force UTF-8 standard output for Windows terminal support
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

# Add project root to sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.services.excel_tracker import excel_tracker
from rich.console import Console
from rich.table import Table

console = Console(force_terminal=True, legacy_windows=False)


def main():
    console.print("[bold cyan]=== Excel Application Tracker Inspection ===[/bold cyan]\n")
    info = excel_tracker.inspect_workbook()

    table = Table(title="Workbook Metadata")
    table.add_column("Property", style="bold yellow")
    table.add_column("Value", style="green")

    table.add_row("File Path", info["file_path"])
    table.add_row("Active Sheet", info["active_sheet"])
    table.add_row("All Sheets", ", ".join(info["sheet_names"]))
    table.add_row("Total Data Rows", str(info["total_rows"]))
    table.add_row("Detected Headers", f"{len(info['headers'])} columns")

    console.print(table)
    console.print("\n[bold]Headers:[/bold]", ", ".join(info["headers"]))


if __name__ == "__main__":
    main()
