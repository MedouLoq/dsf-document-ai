"""Capture README screenshots from the running app (demo mode, synthetic data only).

    DEMO_MODE=true OUTPUT_FOLDER=/tmp/dsf_demo_out python app.py &
    python dashboard.py --output samples/demo_batch --port 5001 &
    python scripts/screenshots.py
"""
import html
import sys
from pathlib import Path

from openpyxl import load_workbook
from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "docs" / "screenshots"
APP = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:5055"
DASH = sys.argv[2] if len(sys.argv) > 2 else "http://127.0.0.1:5056"


def sheet_to_html(path: Path, sheet: str, max_rows: int = 40) -> str:
    ws = load_workbook(path)[sheet]
    rows = []
    for r, row in enumerate(ws.iter_rows(max_row=max_rows), 1):
        cells = []
        for c in row:
            v = c.value
            if isinstance(v, (int, float)):
                txt = f"{v:,.0f}".replace(",", " ") if float(v).is_integer() else f"{v:,.3f}"
                align = "right"
            else:
                txt, align = html.escape(str(v) if v is not None else ""), "left"
            fill = c.fill.fgColor.rgb if c.fill and c.fill.fill_type == "solid" else None
            bg = f"background:#{fill[-6:]};" if isinstance(fill, str) else ""
            color = "color:#c00;" if isinstance(v, (int, float)) and v < 0 else ""
            color = "color:#fff;" if fill and str(fill).endswith("2E7D32") else color
            weight = "font-weight:600;" if c.font and c.font.b else ""
            cells.append(f'<td style="{bg}{color}{weight}text-align:{align}">{txt}</td>')
        rows.append(f"<tr><th>{r}</th>{''.join(cells)}</tr>")
    return f"""<html><head><style>
      body{{margin:0;font:12px Arial,sans-serif;background:#fff}}
      .bar{{background:#217346;color:#fff;padding:6px 12px;font-weight:600}}
      table{{border-collapse:collapse}} td,th{{border:1px solid #d4d4d4;padding:3px 8px;white-space:nowrap}}
      th{{background:#f3f3f3;color:#666;font-weight:400}}
      .tabs span{{display:inline-block;padding:4px 14px;border:1px solid #ccc;border-top:none;background:#f3f3f3}}
      .tabs span.on{{background:#fff;font-weight:600;color:#217346}}
    </style></head><body><div class="bar">{path.name} — {html.escape(sheet)}</div>
    <table>{''.join(rows)}</table>
    <div class="tabs">{''.join(f'<span class="{"on" if s == sheet else ""}">{html.escape(s)}</span>' for s in load_workbook(path).sheetnames)}</div>
    </body></html>"""


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page(viewport={"width": 1100, "height": 900}, device_scale_factor=2)

        # 1. Liasse fiscale: upload the synthetic PDF
        page.goto(APP + "/")
        page.set_input_files("#fileInput", str(ROOT / "samples" / "synthetic_liasse.pdf"))
        page.click("#extractBtn")
        page.wait_for_selector("#resultCard.visible", timeout=30000)
        page.wait_for_timeout(400)
        page.screenshot(path=OUT / "liasse_result.png", full_page=True)

        # 2. Handwritten forms: upload both synthetic scans
        page.goto(APP + "/forms")
        page.set_input_files("#fileInput", [str(ROOT / "samples" / f"synthetic_form_{i}.jpg") for i in (1, 2)])
        page.wait_for_selector(".results.visible", timeout=30000)
        page.evaluate("document.querySelectorAll('.section').forEach((s,i)=>{ if(![1,2].includes(i)) s.classList.add('collapsed') })")
        page.wait_for_timeout(300)
        page.screenshot(path=OUT / "forms_result.png", clip={"x": 0, "y": 0, "width": 1100, "height": 1250}, full_page=True)

        # 3. Batch dashboard (synthetic progress file)
        page.set_viewport_size({"width": 1000, "height": 760})
        page.goto(DASH + "/")
        page.wait_for_timeout(1200)
        page.screenshot(path=OUT / "batch_dashboard.png", full_page=True)

        # 4. Generated Excel files, rendered from the real output workbooks
        page.set_viewport_size({"width": 1000, "height": 700})
        for xlsx, sheet, name, rows in [
            (ROOT / "samples" / "synthetic_liasse.xlsx", "Bilan", "excel_bilan.png", 30),
            (ROOT / "samples" / "synthetic_liasse.xlsx", "Compte de Résultat", "excel_compte_resultat.png", 32),
        ]:
            page.set_content(sheet_to_html(xlsx, sheet, rows))
            page.screenshot(path=OUT / name, full_page=True)
        browser.close()
    print("Saved:", *sorted(p.name for p in OUT.iterdir()), sep="\n  ")


if __name__ == "__main__":
    main()
