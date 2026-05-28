from __future__ import annotations

import csv
import re
import xml.etree.ElementTree as ET
import zipfile
from pathlib import Path

from origin_ai_lab.models import ColumnProfile, DatasetProfile


def _is_float(value: str) -> bool:
    try:
        float(value)
    except ValueError:
        return False
    return True


def read_rows(path: Path) -> list[dict[str, str]]:
    if path.suffix.lower() == ".xlsx":
        return _read_xlsx_rows(path)
    if path.suffix.lower() == ".xls":
        raise ValueError("Legacy .xls files are not supported yet. Export to .xlsx or CSV first.")
    lines = path.read_text(encoding="utf-8-sig").splitlines()
    table = _extract_table(lines, path)
    return _records_from_table(table)


def _records_from_table(table: list[list[str]]) -> list[dict[str, str]]:
    fieldnames = table[0]
    rows: list[dict[str, str]] = []
    for values in table[1:]:
        if not any(value.strip() for value in values):
            continue
        padded = values + [""] * (len(fieldnames) - len(values))
        rows.append({fieldnames[index]: padded[index].strip() for index in range(len(fieldnames))})
    return rows


def profile_csv(path: Path) -> DatasetProfile:
    rows = read_rows(path)
    if not rows:
        return DatasetProfile(path=path, row_count=0, columns=())

    fieldnames = list(rows[0].keys())
    columns: list[ColumnProfile] = []
    for name in fieldnames:
        values = [(row.get(name) or "").strip() for row in rows]
        non_empty_values = [value for value in values if value]
        numeric_count = sum(1 for value in non_empty_values if _is_float(value))
        examples = tuple(non_empty_values[:3])
        columns.append(
            ColumnProfile(
                name=name,
                non_empty=len(non_empty_values),
                numeric=numeric_count,
                examples=examples,
            )
        )

    return DatasetProfile(path=path, row_count=len(rows), columns=tuple(columns))


def write_normalized_csv(path: Path, output_path: Path) -> Path:
    rows = read_rows(path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        output_path.write_text("", encoding="utf-8")
        return output_path

    fieldnames = list(rows[0].keys())
    with output_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)
    return output_path


def numeric_pairs(path: Path, x_column: str, y_column: str) -> list[tuple[float, float]]:
    rows = read_rows(path)
    pairs: list[tuple[float, float]] = []
    for index, row in enumerate(rows, start=2):
        try:
            pairs.append((float(row[x_column]), float(row[y_column])))
        except KeyError as exc:
            raise ValueError(f"Missing column {exc.args[0]!r}") from exc
        except ValueError as exc:
            raise ValueError(f"Non-numeric value at CSV row {index}") from exc
    return pairs


def _extract_table(lines: list[str], path: Path) -> list[list[str]]:
    parsed = [_split_line(line) for line in lines]
    return _extract_table_from_rows(parsed, path)


def _extract_table_from_rows(parsed: list[list[str]], path: Path) -> list[list[str]]:
    for index, row in enumerate(parsed):
        if not _looks_like_header(row):
            continue
        next_row = next(
            (
                candidate
                for candidate in parsed[index + 1 :]
                if len(candidate) == len(row) and _looks_like_data_row(candidate)
            ),
            None,
        )
        width = len(row)
        if next_row:
            next_data_index = parsed.index(next_row, index + 1)
            if any(
                len(candidate) == width and _looks_like_header(candidate)
                for candidate in parsed[index + 1 : next_data_index]
            ):
                continue
            data_rows = [
                candidate[:width]
                for candidate in parsed[index + 1 :]
                if len(candidate) == width and _looks_like_data_row(candidate)
            ]
            if data_rows:
                return [row] + data_rows
    raise ValueError(f"CSV-like file has no detectable header: {path}")


def _split_line(line: str) -> list[str]:
    text = line.strip()
    if not text:
        return []
    if text.startswith("#") or text.startswith("//"):
        return []
    if text.startswith("[") and text.endswith("]"):
        return []
    for delimiter in (",", "\t", ";"):
        if delimiter in text:
            return [item.strip() for item in next(csv.reader([text], delimiter=delimiter))]
    return text.split()


def _looks_like_header(row: list[str]) -> bool:
    if len(row) < 2:
        return False
    if any(not item for item in row):
        return False
    if _looks_like_unit_row(row):
        return False
    if any(not _looks_like_column_name(item) for item in row):
        return False
    if sum(1 for item in row if _is_float(item)) > 0:
        return False
    return len(set(row)) == len(row)


def _looks_like_data_row(row: list[str]) -> bool:
    if len(row) < 2:
        return False
    return sum(1 for item in row if _is_float(item)) >= 1


def _looks_like_column_name(value: str) -> bool:
    if ":" in value:
        return False
    if " " in value and not any(token in value for token in ("(", ")", "[", "]", "/", "%")):
        return False
    return True


def _looks_like_unit_row(row: list[str]) -> bool:
    units = {
        "s",
        "sec",
        "min",
        "h",
        "v",
        "mv",
        "a",
        "ma",
        "ua",
        "ohm",
        "k",
        "c",
        "deg",
        "degree",
        "counts",
        "a.u.",
        "au",
        "%",
        "percent",
        "nm",
        "cm-1",
        "1/cm",
        "mw",
        "mg",
        "g",
        "mpa",
    }
    normalized = [item.strip().lower() for item in row if item.strip()]
    return bool(normalized) and all(item in units for item in normalized)


def _read_xlsx_rows(path: Path) -> list[dict[str, str]]:
    workbook_rows = _xlsx_workbook_rows(path)
    for sheet_name, rows in workbook_rows:
        try:
            return _records_from_table(_extract_table_from_rows(rows, path))
        except ValueError:
            continue
    sheet_names = ", ".join(name for name, _ in workbook_rows) or "<none>"
    raise ValueError(f"XLSX file has no detectable data table. Sheets scanned: {sheet_names}")


def _xlsx_workbook_rows(path: Path) -> list[tuple[str, list[list[str]]]]:
    with zipfile.ZipFile(path) as archive:
        shared_strings = _xlsx_shared_strings(archive)
        sheets = _xlsx_sheet_paths(archive)
        workbook_rows: list[tuple[str, list[list[str]]]] = []
        for sheet_name, sheet_path in sheets:
            try:
                xml_bytes = archive.read(sheet_path)
            except KeyError:
                continue
            workbook_rows.append((sheet_name, _xlsx_sheet_rows(xml_bytes, shared_strings)))
    return workbook_rows


def _xlsx_shared_strings(archive: zipfile.ZipFile) -> list[str]:
    try:
        xml_bytes = archive.read("xl/sharedStrings.xml")
    except KeyError:
        return []
    root = ET.fromstring(xml_bytes)
    namespace = _xml_namespace(root.tag)
    strings: list[str] = []
    for item in root.findall(f"{namespace}si"):
        parts = [node.text or "" for node in item.iter() if node.tag.endswith("}t") or node.tag == "t"]
        strings.append("".join(parts))
    return strings


def _xlsx_sheet_paths(archive: zipfile.ZipFile) -> list[tuple[str, str]]:
    workbook = ET.fromstring(archive.read("xl/workbook.xml"))
    namespace = _xml_namespace(workbook.tag)
    rels = _xlsx_relationships(archive)
    sheets: list[tuple[str, str]] = []
    for sheet in workbook.findall(f"{namespace}sheets/{namespace}sheet"):
        name = sheet.attrib.get("name", "Sheet")
        rel_id = sheet.attrib.get("{http://schemas.openxmlformats.org/officeDocument/2006/relationships}id", "")
        target = rels.get(rel_id)
        if not target:
            continue
        if not target.startswith("xl/"):
            target = "xl/" + target.lstrip("/")
        sheets.append((name, target))
    return sheets


def _xlsx_relationships(archive: zipfile.ZipFile) -> dict[str, str]:
    root = ET.fromstring(archive.read("xl/_rels/workbook.xml.rels"))
    relationships: dict[str, str] = {}
    for rel in root:
        rel_id = rel.attrib.get("Id")
        target = rel.attrib.get("Target")
        if rel_id and target:
            relationships[rel_id] = target
    return relationships


def _xlsx_sheet_rows(xml_bytes: bytes, shared_strings: list[str]) -> list[list[str]]:
    root = ET.fromstring(xml_bytes)
    namespace = _xml_namespace(root.tag)
    rows: list[list[str]] = []
    for row in root.findall(f".//{namespace}row"):
        values_by_index: dict[int, str] = {}
        for cell in row.findall(f"{namespace}c"):
            ref = cell.attrib.get("r", "")
            column_index = _xlsx_column_index(ref)
            if column_index is None:
                column_index = len(values_by_index)
            values_by_index[column_index] = _xlsx_cell_text(cell, namespace, shared_strings)
        if not values_by_index:
            rows.append([])
            continue
        width = max(values_by_index) + 1
        rows.append([values_by_index.get(index, "").strip() for index in range(width)])
    return rows


def _xlsx_cell_text(cell: ET.Element, namespace: str, shared_strings: list[str]) -> str:
    cell_type = cell.attrib.get("t")
    if cell_type == "inlineStr":
        text_node = cell.find(f"{namespace}is/{namespace}t")
        return (text_node.text or "") if text_node is not None else ""
    value_node = cell.find(f"{namespace}v")
    value = (value_node.text or "") if value_node is not None else ""
    if cell_type == "s":
        try:
            return shared_strings[int(value)]
        except Exception:
            return value
    return value


def _xlsx_column_index(cell_ref: str) -> int | None:
    match = re.match(r"([A-Za-z]+)", cell_ref)
    if not match:
        return None
    value = 0
    for char in match.group(1).upper():
        value = value * 26 + (ord(char) - ord("A") + 1)
    return value - 1


def _xml_namespace(tag: str) -> str:
    if tag.startswith("{"):
        return tag.split("}", 1)[0] + "}"
    return ""
