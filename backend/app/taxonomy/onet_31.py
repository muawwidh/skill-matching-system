"""O*NET 31.0 CSV only. Source rows are CC BY 4.0, National Center for O*NET Development."""
import json
from hashlib import sha256
from pathlib import Path

from app.taxonomy.importer import ConceptRecord, OccupationRecord, ParsedTaxonomy
from app.taxonomy.packages import Package, number, required, rows

MANIFEST = json.loads(Path(__file__).with_name("onet_31_manifest.json").read_text())
SOC = "O*NET-SOC Code"


def record_key(filename: str, row: dict[str, str]) -> str:
    values = [row[column] for column in MANIFEST["datasets"][filename]["identity"]]
    return sha256(json.dumps(values, ensure_ascii=True).encode()).hexdigest()


def parse_onet_31(files: dict[str, bytes], checksum: str) -> Package:
    missing = (set(MANIFEST["datasets"]) | set(MANIFEST["required_metadata"])) - files.keys()
    if missing:
        raise ValueError(f"ONET-31.0-csv: missing required files {sorted(missing)}")
    if files["Read Me.txt"].decode("utf-8-sig").partition("\n")[0].rstrip("\r") != "O*NET 31.0 Database":
        raise ValueError("Read Me.txt disagrees with the ONET-31.0-csv contract")
    tables = {name: rows(files[name], name, spec["headers"], ",")
              for name, spec in MANIFEST["datasets"].items()}

    def index(name: str, columns: tuple[str, ...]) -> dict:
        result = {}
        for row in tables[name]:
            key = tuple(required(row, column, name) for column in columns)
            if key in result:
                raise ValueError(f"{name}: duplicate identifier {key}")
            result[key] = row
        return result

    occupations = index("occupation_data.csv", (SOC,))
    elements = index("content_model_reference.csv", ("Element ID",))
    scales = index("scales_reference.csv", ("Scale ID",))
    tasks = index("task_statements.csv", (SOC, "Task ID"))
    zones = index("job_zone_reference.csv", ("Job Zone",))
    categories = {name: index(name, ("Element ID", "Scale ID", "Category")) for name in (
        "education_categories.csv", "training_and_experience_categories.csv", "work_context_categories.csv")}
    task_categories = index("task_categories.csv", ("Scale ID", "Category"))
    for row in scales.values():
        lo, hi = number(row["Minimum"], "Minimum"), number(row["Maximum"], "Maximum")
        if lo is None or hi is None or lo > hi:
            raise ValueError("scales_reference.csv: invalid bounds")

    records, relationships = [], []
    titles, job_zones, resolutions = {}, {}, {}
    for filename, table in tables.items():
        seen = set()
        endpoint_columns = [column for column in MANIFEST["datasets"][filename]["headers"]
                            if column.endswith("Element ID")]
        for row in table:
            for column, value in row.items():
                reference = (elements if column.endswith("Element ID") else
                             occupations if column.endswith(SOC) else scales if column == "Scale ID" else None)
                if reference is not None and (value,) not in reference:
                    raise ValueError(f"{filename}: unresolved {column} {value!r}")
            code = row.get(SOC, "")
            task = row.get("Task ID", "")
            if task and (code, task) not in tasks:
                raise ValueError(f"{filename}: unresolved task {task}")
            if filename == "emerging_tasks.csv" and row["Original Task ID"] not in {"", "n/a"}:
                if (code, row["Original Task ID"]) not in tasks:
                    raise ValueError(f"{filename}: unresolved original task")
            category = row.get("Category", "")
            category_file = {"education.csv": "education_categories.csv",
                "training_and_experience.csv": "training_and_experience_categories.csv",
                "work_context.csv": "work_context_categories.csv"}.get(filename)
            if category_file and category not in {"", "n/a"}:
                if (row["Element ID"], row["Scale ID"], category) not in categories[category_file]:
                    raise ValueError(f"{filename}: unresolved category {category}")
            if filename == "task_ratings.csv" and category not in {"", "n/a"}:
                if (row["Scale ID"], category) not in task_categories:
                    raise ValueError(f"{filename}: unresolved task category")
            for column in ("Data Value", "Minimum", "Maximum", "N", "Standard Error", "Lower CI Bound",
                           "Upper CI Bound", "Incumbents Responding", "Anchor Value", "Percent", "Index"):
                if column in row:
                    number(row[column], f"{filename}/{column}")
            value = number(row.get("Data Value", ""), filename)
            scale = row.get("Scale ID", "")
            if "Data Value" in row and value is None:
                raise ValueError(f"{filename}: missing Data Value")
            if value is not None:
                bounds = scales[(scale,)]
                if not number(bounds["Minimum"], filename) <= value <= number(bounds["Maximum"], filename):
                    raise ValueError(f"{filename}: value outside scale {scale}")
            if filename == "job_zones.csv":
                zone = row["Job Zone"]
                if (zone,) not in zones or zone not in {"2", "3", "4", "5"}:
                    raise ValueError(f"{filename}: unresolved job zone {zone}")
                job_zones[code] = int(zone)
            if filename == "job_titles.csv":
                titles.setdefault(code, []).append(required(row, "Job Title", filename))
            key = record_key(filename, row)
            if key in seen:
                raise ValueError(f"{filename}: duplicate record identity")
            seen.add(key)
            records.append(dict(dataset=filename, record_key=key, occupation_code=code or None,
                element_id=row.get("Element ID", ""), scale_id=scale, task_id=task, category=category,
                numeric_value=value, source_data=row))
            # Binary element links have the direction explicitly named by the CSV columns.
            # Triples and task links remain complete, validated structured source records.
            if len(endpoint_columns) >= 2 or filename in {"tasks_to_dwas.csv", "related_occupations.csv"}:
                resolutions[filename] = resolutions.get(filename, 0) + 1
            if len(endpoint_columns) == 2 or filename == "related_occupations.csv":
                source, target = (tuple(row[c] for c in endpoint_columns) if len(endpoint_columns) == 2 else
                                  (f"ONET:{code}", f"ONET:{row['Related O*NET-SOC Code']}"))
                relationships.append(dict(source=source, target=target,
                    relationship_type=filename.removesuffix(".csv"),
                    metadata_json={"dataset": filename, "source": row}))

    concepts = []
    for (element,), row in elements.items():
        kind = next((kind for prefix, kind in (("2.A.", "skill"), ("2.B.", "skill"),
            ("2.C.", "knowledge"), ("1.A.", "ability"), ("4.A.", "work_activity"),
            ("2.E.", "software_skill")) if element.startswith(prefix)), "content_element")
        concepts.append(ConceptRecord(element, required(row, "Element Name", "content_model_reference.csv"),
            row["Description"], kind, metadata={"dataset": "content_model_reference.csv", "source": row}))
    occupation_records = [OccupationRecord(code, required(row, "Title", "occupation_data.csv"),
        row["Description"], f"ONET:{code}", titles.get(code, []), job_zones.get(code), row)
        for (code,), row in occupations.items()]
    package = Package(ParsedTaxonomy(concepts, occupation_records, []), relationships, records)
    package.report = dict(contract="ONET-31.0-csv", sha256=checksum,
        member_sha256={name: sha256(data).hexdigest() for name, data in sorted(files.items())},
        datasets={name: dict(input=len(table), inserted=0, merged_duplicate_rows=0) for name, table in tables.items()},
        imported_datasets=sorted(tables), skipped_files=sorted(files.keys() - tables.keys()),
        skipped_reasons={name: "release metadata validated; not a data table" if name == "Read Me.txt"
                         else "outside pinned manifest" for name in files.keys() - tables.keys()},
        unresolved_references=[], relationships_resolved=len(relationships),
        relationship_source_rows_resolved=resolutions, missing_optional_files=[],
        attribution="O*NET 31.0 Database, National Center for O*NET Development, CC BY 4.0",
        license_url="https://www.onetcenter.org/license_db.html")
    return package
