#!/usr/bin/env python3
# read/md2pdf.py
from __future__ import annotations

import sys
from pathlib import Path
from typing import Optional

import markdown
from weasyprint import HTML


class GeneratePDF:
    @staticmethod
    def md_text_to_pdf(md_text: str, pdf_path: Path, title: str = "") -> Path:
        """直接用 md 文字產出 PDF（推薦給你現在的匯出流程）。"""
        html_body = markdown.markdown(
            md_text,
            extensions=["extra", "codehilite", "toc"],
        )

        html = f"""<!DOCTYPE html>
<html lang="zh-Hant">
<head>
<meta charset="utf-8">
<style>
  body {{ font-family: "Noto Serif CJK TC", serif; margin:1cm; }}
  pre {{ background:#f5f5f5; padding:.5em; overflow:auto; }}
  h1,h2,h3 {{ border-bottom:1px solid #ddd; padding-bottom:.3em; }}
</style>
</head>
<body>
{f"<h1>{title}</h1>" if title else ""}
{html_body}
</body>
</html>"""

        pdf_path.parent.mkdir(parents=True, exist_ok=True)
        HTML(string=html).write_pdf(str(pdf_path))
        return pdf_path

    @staticmethod
    def md_file_to_pdf(md_file: Path, pdf_file: Path) -> Path:
        """用 md 檔案產 pdf（保留你原本需求）。"""
        md_text = md_file.read_text(encoding="utf-8")
        return GeneratePDF.md_text_to_pdf(md_text, pdf_file, title=md_file.stem)

    @staticmethod
    def generate_pdf(md_dir: Optional[str] = None, pdf_dir: Optional[str] = None) -> None:
        """CLI 兼容（你原本的功能），可把整個資料夾的 md 轉 pdf。"""
        script_dir = Path(__file__).resolve().parent
        project_root = script_dir.parent

        md_dir_path = Path(md_dir) if md_dir else project_root / "MD"
        pdf_dir_path = Path(pdf_dir) if pdf_dir else project_root / "PDF"
        pdf_dir_path.mkdir(parents=True, exist_ok=True)

        if len(sys.argv) > 1:
            files_to_convert = sys.argv[1:]
        else:
            files_to_convert = [p.name for p in md_dir_path.glob("*.md")]

        for fname in files_to_convert:
            md_file = md_dir_path / fname
            if not md_file.exists():
                print(f"⚠ 找不到：{md_file}")
                continue

            pdf_file = pdf_dir_path / f"{md_file.stem}.pdf"
            GeneratePDF.md_file_to_pdf(md_file, pdf_file)
            print(f"→ 已輸出：{pdf_file.name}")


if __name__ == "__main__":
    GeneratePDF.generate_pdf()
