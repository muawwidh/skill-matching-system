"""Strict, version-pinned package adapters. No network access during import."""
import csv
import json
from dataclasses import dataclass, field
from decimal import Decimal, InvalidOperation
from hashlib import sha256
from io import BytesIO, StringIO
from pathlib import PurePosixPath
import stat
from zipfile import BadZipFile, ZipFile

from app.taxonomy.importer import ConceptRecord, OccupationRecord, ParsedTaxonomy


@dataclass(frozen=True)
class ArchiveLimits:
    upload: int = 128 * 1024 * 1024
    total: int = 512 * 1024 * 1024
    member: int = 128 * 1024 * 1024
    count: int = 128


LIMITS = ArchiveLimits()


def read_archive(content: bytes, limits: ArchiveLimits = LIMITS) -> dict[str, bytes]:
    if len(content) > limits.upload:
        raise ValueError("Taxonomy upload exceeds compressed/upload byte limit.")
    result: dict[str, bytes] = {}
    total = 0
    try:
        with ZipFile(BytesIO(content)) as archive:
            members = archive.infolist()
            if len(members) > limits.count:
                raise ValueError("Archive exceeds member count limit.")
            if sum(item.file_size for item in members) > limits.total:
                raise ValueError("Archive exceeds uncompressed byte limit.")
            for item in members:
                path = PurePosixPath(item.filename)
                if (path.is_absolute() or ".." in path.parts or "\\" in item.filename
                        or ":" in item.filename or stat.S_ISLNK(item.external_attr >> 16)
                        or item.flag_bits & 1):
                    raise ValueError(f"Unsafe archive member: {item.filename}")
                if item.is_dir():
                    continue
                if item.file_size > limits.member:
                    raise ValueError(f"Archive member exceeds byte limit: {item.filename}")
                if path.name in result:
                    raise ValueError(f"Ambiguous duplicate archive filename: {path.name}")
                data = bytearray()
                with archive.open(item) as stream:
                    while chunk := stream.read(64 * 1024):
                        total += len(chunk)
                        if total > limits.total or len(data) + len(chunk) > limits.member:
                            raise ValueError("Archive exceeds runtime uncompressed byte limits.")
                        data.extend(chunk)
                result[path.name] = bytes(data)
    except (BadZipFile, RuntimeError, NotImplementedError) as exc:
        raise ValueError(f"Invalid taxonomy ZIP: {exc}") from exc
    return result


ESCO_HEADERS = {
    "skills_en.csv": "conceptType conceptUri skillType reuseLevel preferredLabel altLabels hiddenLabels status modifiedDate scopeNote definition inScheme description",
    "occupations_en.csv": "conceptType conceptUri iscoGroup preferredLabel altLabels hiddenLabels status modifiedDate regulatedProfessionNote scopeNote definition inScheme description code naceCode",
    "skillGroups_en.csv": "conceptType conceptUri preferredLabel altLabels hiddenLabels status modifiedDate scopeNote inScheme description code",
    "ISCOGroups_en.csv": "conceptType conceptUri code preferredLabel status altLabels inScheme description",
    "broaderRelationsSkillPillar_en.csv": "conceptType conceptUri conceptLabel broaderType broaderUri broaderLabel",
    "broaderRelationsOccPillar_en.csv": "conceptType conceptUri conceptLabel broaderType broaderUri broaderLabel",
    "occupationSkillRelations_en.csv": "occupationUri occupationLabel relationType skillType skillUri skillLabel",
    "skillSkillRelations_en.csv": "originalSkillUri originalSkillType relationType relatedSkillType relatedSkillUri",
}
# Core columns are mandatory; all additional columns are retained verbatim.
ESCO_REQUIRED = ESCO_HEADERS

SOC = "O*NET-SOC Code"
RATING = [SOC, "Element ID", "Element Name", "Scale ID", "Data Value", "N", "Standard Error",
          "Lower CI Bound", "Upper CI Bound", "Recommend Suppress", "Not Relevant", "Date", "Domain Source"]
ONET_HEADERS = {
    "Occupation Data.txt": [SOC, "Title", "Description"],
    "Content Model Reference.txt": ["Element ID", "Element Name", "Description"],
    "Scales Reference.txt": ["Scale ID", "Scale Name", "Minimum", "Maximum"],
    **{name + ".txt": RATING for name in ("Skills", "Knowledge", "Abilities", "Work Activities")},
    "Task Statements.txt": [SOC, "Task ID", "Task", "Task Type", "Incumbents Responding", "Date", "Domain Source"],
    "Task Ratings.txt": [SOC, "Task ID", "Scale ID", "Category", "Data Value", "N", "Standard Error", "Lower CI Bound", "Upper CI Bound", "Recommend Suppress", "Date", "Domain Source"],
    "Task Categories.txt": ["Scale ID", "Category", "Category Description"],
    "Technology Skills.txt": [SOC, "Example", "Commodity Code", "Commodity Title", "Hot Technology", "In Demand"],
    "Tools Used.txt": [SOC, "Example", "Commodity Code", "Commodity Title"],
    "Education, Training, and Experience.txt": [SOC, "Element ID", "Element Name", "Scale ID", "Category", "Data Value", "N", "Standard Error", "Lower CI Bound", "Upper CI Bound", "Recommend Suppress", "Date", "Domain Source"],
    "Education, Training, and Experience Categories.txt": ["Element ID", "Element Name", "Scale ID", "Category", "Category Description"],
    "Alternate Titles.txt": [SOC, "Alternate Title", "Short Title", "Source(s)"],
    "Job Zones.txt": [SOC, "Job Zone", "Date", "Domain Source"],
    "Job Zone Reference.txt": ["Job Zone", "Name", "Experience", "Education", "Job Training", "Examples", "SVP Range"],
}
ONET_OPTIONAL = {"Alternate Titles.txt", "Job Zones.txt", "Job Zone Reference.txt"}


@dataclass
class Package:
    taxonomy: ParsedTaxonomy
    relationships: list[dict] = field(default_factory=list)
    records: list[dict] = field(default_factory=list)
    report: dict = field(default_factory=dict)


def rows(data: bytes, filename: str, headers: list[str], delimiter: str) -> list[dict[str, str]]:
    reader = csv.DictReader(StringIO(data.decode("utf-8-sig"), newline=""), delimiter=delimiter, strict=True)
    if not reader.fieldnames or len(set(reader.fieldnames)) != len(reader.fieldnames):
        raise ValueError(f"{filename}: missing or duplicate headers")
    missing = set(headers) - set(reader.fieldnames)
    if missing:
        raise ValueError(f"{filename}: missing required columns {sorted(missing)}")
    result = []
    for index, row in enumerate(reader, 2):
        if None in row or any(value is None for value in row.values()):
            raise ValueError(f"{filename}:{index}: malformed column count")
        result.append(row)
    return result


def required(row: dict, key: str, filename: str) -> str:
    value = row.get(key, "").strip()
    if not value:
        raise ValueError(f"{filename}: empty {key}")
    return value


def number(value: str, context: str) -> Decimal | None:
    if value in {"", "n/a"}:
        return None
    try:
        result = Decimal(value)
        if not result.is_finite():
            raise InvalidOperation
        return result
    except InvalidOperation as exc:
        raise ValueError(f"{context}: invalid numeric value {value!r}") from exc


class OfficialPackageParser:
    def parse(self, content: bytes, source: str, version: str) -> Package:
        if (source, version) == ("ONET", "31.0"):
            from app.taxonomy.onet_31 import parse_onet_31

            return parse_onet_31(read_archive(content), sha256(content).hexdigest())
        expected = {"ESCO": "1.2.1", "ONET": "29.0"}
        if version != expected.get(source):
            raise ValueError(f"Supported package contract: {source} {expected.get(source)} only")
        files = read_archive(content)
        if source == "ONET" and "Read Me.txt" in files:
            if not files["Read Me.txt"].decode("utf-8-sig").startswith("O*NET 29.0 Database"):
                raise ValueError("O*NET Read Me.txt disagrees with the 29.0 contract")
        contract = ESCO_REQUIRED if source == "ESCO" else ONET_HEADERS
        optional = set() if source == "ESCO" else ONET_OPTIONAL
        missing = set(contract) - optional - files.keys()
        if missing:
            raise ValueError(f"Missing required package files: {sorted(missing)}")
        if source == "ONET" and "Job Zones.txt" in files and "Job Zone Reference.txt" not in files:
            raise ValueError("Job Zones.txt requires Job Zone Reference.txt")
        tables = {
            name: rows(files[name], name, headers.split() if isinstance(headers, str) else headers,
                       "," if source == "ESCO" else "\t")
            for name, headers in contract.items() if name in files
        }
        package = self._esco(tables) if source == "ESCO" else self._onet(tables)
        package.report = {
            "contract": f"{source}-{version}" + ("-en-csv" if source == "ESCO" else "-txt"),
            "sha256": sha256(content).hexdigest(),
            "member_sha256": {name: sha256(data).hexdigest() for name, data in sorted(files.items())},
            "datasets": {name: {"input": len(table), "inserted": 0, "merged_duplicate_rows": 0} for name, table in tables.items()},
            "skipped_files": sorted(files.keys() - contract.keys()),
            "missing_optional_files": sorted(optional - files.keys()),
            "unresolved_references": [],
            "relationships_resolved": len(package.relationships),
        }
        for concept in package.taxonomy.concepts:
            duplicates = len(concept.metadata.get("source_rows", [])) - 1
            if duplicates > 0:
                package.report["datasets"][concept.metadata["dataset"]]["merged_duplicate_rows"] += duplicates
        return package

    def _esco(self, tables: dict[str, list[dict]]) -> Package:
        concepts = {}
        for filename, kind in (("skills_en.csv", "skill"), ("occupations_en.csv", "occupation"),
                               ("skillGroups_en.csv", "skill_group"), ("ISCOGroups_en.csv", "isco_group")):
            for row in tables[filename]:
                uri = required(row, "conceptUri", filename)
                if not uri.startswith("http://data.europa.eu/esco/"):
                    raise ValueError(f"{filename}: invalid ESCO URI {uri}")
                if uri in concepts:
                    previous = concepts[uri].metadata
                    differences = {key for key in row if row[key] != previous["source"].get(key)}
                    if previous["dataset"] != filename or differences - {"modifiedDate"}:
                        raise ValueError(f"Conflicting ESCO concept URI {uri}")
                    previous.setdefault("source_rows", [previous["source"]]).append(row)
                    continue
                concepts[uri] = ConceptRecord(
                    uri, required(row, "preferredLabel", filename), row.get("description", ""),
                    ("knowledge" if row.get("skillType") == "knowledge" else kind),
                    row.get("altLabels", "").splitlines(), metadata={"dataset": filename, "source": row},
                )
        relationships = []
        seen = set()
        for filename, source_key, target_key in (
            ("broaderRelationsSkillPillar_en.csv", "conceptUri", "broaderUri"),
            ("broaderRelationsOccPillar_en.csv", "conceptUri", "broaderUri"),
            ("occupationSkillRelations_en.csv", "occupationUri", "skillUri"),
            ("skillSkillRelations_en.csv", "originalSkillUri", "relatedSkillUri"),
        ):
            for row in tables[filename]:
                source, target = required(row, source_key, filename), required(row, target_key, filename)
                if source not in concepts or target not in concepts:
                    raise ValueError(f"{filename}: unresolved relationship {source} -> {target}")
                kind = row.get("relationType", "broader")
                if "relationType" in row and kind not in {"essential", "optional"}:
                    raise ValueError(f"{filename}: unsupported relationType {kind!r}")
                key = (source, target, kind)
                if key in seen:
                    raise ValueError(f"{filename}: duplicate relationship {key}")
                seen.add(key)
                relationships.append({"source": source, "target": target, "relationship_type": kind,
                                      "metadata_json": {"dataset": filename, "source": row}})
        return Package(ParsedTaxonomy(list(concepts.values()), [], []), relationships)

    def _onet(self, tables: dict[str, list[dict]]) -> Package:
        def index(filename: str, fields: tuple[str, ...]) -> dict[tuple, dict]:
            result = {}
            for row in tables.get(filename, []):
                key = tuple(required(row, key, filename) for key in fields)
                if key in result:
                    raise ValueError(f"{filename}: duplicate identifier {key}")
                result[key] = row
            return result

        occupations = index("Occupation Data.txt", (SOC,))
        elements = index("Content Model Reference.txt", ("Element ID",))
        scales = index("Scales Reference.txt", ("Scale ID",))
        tasks = index("Task Statements.txt", (SOC, "Task ID"))
        categories = index("Education, Training, and Experience Categories.txt", ("Element ID", "Scale ID", "Category"))
        task_categories = index("Task Categories.txt", ("Scale ID", "Category"))
        zones = index("Job Zone Reference.txt", ("Job Zone",))
        titles: dict[str, list[str]] = {}
        job_zones = {}
        records = []
        seen = set()
        for filename, table in tables.items():
            for row in table:
                if filename in {"Skills.txt", "Knowledge.txt", "Abilities.txt", "Work Activities.txt", "Education, Training, and Experience.txt"}:
                    for key in (SOC, "Element ID", "Element Name", "Scale ID", "Data Value"):
                        required(row, key, filename)
                if filename == "Task Ratings.txt":
                    for key in (SOC, "Task ID", "Scale ID", "Data Value"):
                        required(row, key, filename)
                if filename in {"Technology Skills.txt", "Tools Used.txt"}:
                    for key in (SOC, "Example", "Commodity Code", "Commodity Title"):
                        required(row, key, filename)
                code, element, scale = row.get(SOC, ""), row.get("Element ID", ""), row.get("Scale ID", "")
                task, category = row.get("Task ID", ""), row.get("Category", "")
                if SOC in row and (code,) not in occupations:
                    raise ValueError(f"{filename}: unresolved occupation {code}")
                if element and (element,) not in elements:
                    raise ValueError(f"{filename}: unresolved element {element}")
                if scale and (scale,) not in scales:
                    raise ValueError(f"{filename}: unresolved scale {scale}")
                if task and (code, task) not in tasks:
                    raise ValueError(f"{filename}: unresolved task {task}")
                if filename == "Education, Training, and Experience.txt" and category not in {"", "n/a"} and (element, scale, category) not in categories:
                    raise ValueError(f"{filename}: unresolved category {category}")
                if filename == "Task Ratings.txt" and category not in {"", "n/a"} and (scale, category) not in task_categories:
                    raise ValueError(f"{filename}: unresolved task category {category}")
                if filename == "Alternate Titles.txt":
                    titles.setdefault(code, []).append(required(row, "Alternate Title", filename))
                if filename == "Job Zones.txt":
                    zone = required(row, "Job Zone", filename)
                    if (zone,) not in zones or zone not in {"1", "2", "3", "4", "5"} or code in job_zones:
                        raise ValueError(f"{filename}: invalid/duplicate job zone {zone}")
                    job_zones[code] = int(zone)
                for key in ("Data Value", "Minimum", "Maximum", "N", "Standard Error", "Lower CI Bound", "Upper CI Bound", "Incumbents Responding"):
                    if key in row:
                        number(row[key], f"{filename}/{key}")
                value = number(row.get("Data Value", ""), filename)
                if value is not None and scale:
                    bounds = scales[(scale,)]
                    lo, hi = number(bounds["Minimum"], filename), number(bounds["Maximum"], filename)
                    if lo is not None and value < lo or hi is not None and value > hi:
                        raise ValueError(f"{filename}: value outside scale {scale}")
                identity = [code, element, scale, task, category, row.get("Example", ""),
                            row.get("Commodity Code", ""), row.get("Alternate Title", ""),
                            row.get("Short Title", ""), row.get("Source(s)", ""), row.get("Job Zone", "")]
                key = sha256(json.dumps(identity, ensure_ascii=True).encode()).hexdigest()
                if (filename, key) in seen:
                    raise ValueError(f"{filename}: duplicate record identity")
                seen.add((filename, key))
                records.append({"dataset": filename, "record_key": key, "occupation_code": code or None,
                                "element_id": element, "scale_id": scale, "task_id": task, "category": category,
                                "numeric_value": value, "source_data": row})
        concepts = []
        for (element,), row in elements.items():
            kind = next((kind for prefix, kind in (("2.A", "skill"), ("2.B", "skill"), ("2.C", "knowledge"),
                        ("1.A", "ability"), ("4.A", "work_activity")) if element.startswith(prefix + ".")), None)
            if kind:
                concepts.append(ConceptRecord(element, row["Element Name"], row["Description"], kind,
                                              metadata={"dataset": "Content Model Reference.txt", "source": row}))
        occupation_records = [OccupationRecord(code, required(row, "Title", "Occupation Data.txt"),
            row["Description"], f"ONET:{code}", titles.get(code, []), job_zones.get(code), row)
            for (code,), row in occupations.items()]
        return Package(ParsedTaxonomy(concepts, occupation_records, []), records=records)
