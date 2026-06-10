from __future__ import annotations

import argparse
import re
import subprocess
from dataclasses import dataclass
from pathlib import Path

import pymupdf


SYNC_INPUT_RE = re.compile(r"^Input:(?P<input>.+)$", re.MULTILINE)
SYNC_LINE_RE = re.compile(r"^Line:(?P<line>\d+)$", re.MULTILINE)
SECTION_RE = re.compile(r"\\(section|subsection|subsubsection)\{(.+?)\}")


@dataclass
class SyncLocation:
    file_path: Path | None
    line: int | None


def run_synctex(main_pdf: Path, page: int, x: float, y: float) -> SyncLocation:
    result = subprocess.run(
        [
            "synctex",
            "edit",
            "-o",
            f"{page}:{x:.3f}:{y:.3f}:{main_pdf}",
        ],
        check=False,
        capture_output=True,
        text=True,
    )
    output = result.stdout
    input_match = SYNC_INPUT_RE.search(output)
    line_match = SYNC_LINE_RE.search(output)
    file_path = Path(input_match.group("input")) if input_match else None
    line = int(line_match.group("line")) if line_match else None
    return SyncLocation(file_path=file_path, line=line)


def read_lines(file_path: Path) -> list[str]:
    return file_path.read_text(encoding="utf-8").splitlines()


def nearest_heading(lines: list[str], line_number: int) -> str:
    if line_number <= 0:
        return "sin localizar"
    best = "sin localizar"
    for index in range(min(line_number, len(lines))):
        line = lines[index]
        match = SECTION_RE.search(line)
        if match:
            level = match.group(1)
            title = match.group(2)
            best = f"{level}: {title}"
    return best


def infer_main_tex_context(lines: list[str], line_number: int) -> str:
    if line_number is None or line_number <= 0:
        return "sin localizar"
    current = lines[line_number - 1].strip() if line_number <= len(lines) else ""
    if "\\includepdf" in current:
        return "portada"
    begin_abstract = next((idx + 1 for idx, text in enumerate(lines) if "\\begin{abstract}" in text), None)
    end_abstract = next((idx + 1 for idx, text in enumerate(lines) if "\\end{abstract}" in text), None)
    if begin_abstract and end_abstract and begin_abstract <= line_number <= end_abstract:
        if "\\keywords{" in current:
            return "resumen / palabras clave"
        return "abstract"
    return nearest_heading(lines, line_number)


def line_excerpt(lines: list[str], line_number: int | None) -> str:
    if line_number is None or line_number <= 0 or line_number > len(lines):
        return ""
    return lines[line_number - 1].strip()


def escape_md(text: str) -> str:
    return text.replace("`", "\\`").strip()


def build_report(pdf_path: Path, main_pdf: Path, output_path: Path) -> None:
    doc = pymupdf.open(pdf_path)
    entries: list[str] = []
    annotation_count = 0

    for page_index in range(doc.page_count):
        page = doc.load_page(page_index)
        page_number = page_index + 1
        for annot in page.annots() or []:
            annotation_count += 1
            info = annot.info or {}
            comment = (info.get("content") or "").strip()
            rect = annot.rect
            x = (rect.x0 + rect.x1) / 2
            y = (rect.y0 + rect.y1) / 2
            sync = run_synctex(main_pdf, page_number, x, y)

            apartado = "sin localizar"
            file_label = "no localizado"
            line_label = "no localizada"
            point = ""
            note = ""

            if sync.file_path and sync.line:
                lines = read_lines(sync.file_path)
                if sync.file_path.name == "main.tex":
                    apartado = infer_main_tex_context(lines, sync.line)
                else:
                    apartado = nearest_heading(lines, sync.line)
                file_label = str(sync.file_path)
                line_label = str(sync.line)
                point = line_excerpt(lines, sync.line)
                if point in {"\\end{tikzpicture}}", "\\end{figure}", "\\begin{figure}[H]"}:
                    note = "La anotacion cae sobre un bloque de figura; el punto exacto debe entenderse como anclaje aproximado dentro del bloque grafico."

            title = comment if comment else f"Anotacion sin texto explicito en pagina {page_number}"
            title = title.splitlines()[0]
            title = title[:110] + ("..." if len(title) > 110 else "")

            block = [
                f"### {annotation_count}. {escape_md(title)}",
                "",
                f"- Pagina del PDF: {page_number}",
                f"- Tipo: {annot.type[1]}",
                f"- Apartado: {escape_md(apartado)}",
                f"- Archivo `.tex`: `{escape_md(file_label)}`",
                f"- Linea: {line_label}",
                f"- Punto exacto o mas cercano: `{escape_md(point)}`" if point else "- Punto exacto o mas cercano: no recuperable",
                f"- Coordenadas PDF: x={x:.2f}, y={y:.2f}",
                f"- Comentario: \"{escape_md(comment)}\"" if comment else "- Comentario: sin texto explicito en el objeto de anotacion",
            ]
            if note:
                block.append(f"- Observacion: {note}")
            entries.append("\n".join(block))

    header = [
        "# Anotaciones del PDF revisado",
        "",
        f"Fuente analizada: `{pdf_path}`.",
        "",
        "Las anotaciones se han extraido del propio PDF con PyMuPDF y se han cruzado con `synctex` sobre `memoria/main.pdf` para localizar el `.tex` de origen.",
        "Cuando una anotacion cae sobre una figura, una portada PDF o un bloque de maquetacion, la linea indicada debe entenderse como el anclaje mas cercano recuperable.",
        "",
        "## Resumen",
        "",
        f"Se han encontrado {annotation_count} anotaciones visibles reales en el PDF.",
        "",
        "## Detalle de anotaciones",
        "",
    ]
    output = "\n".join(header + entries) + "\n"
    output_path.write_text(output, encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--pdf", type=Path, required=True)
    parser.add_argument("--main-pdf", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    build_report(args.pdf, args.main_pdf, args.output)


if __name__ == "__main__":
    main()