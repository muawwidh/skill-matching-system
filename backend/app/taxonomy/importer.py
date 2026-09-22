import csv
from dataclasses import dataclass, field
from hashlib import sha256
from io import StringIO
import json
from pathlib import Path
from typing import Any

from app.taxonomy.normalization import normalize_taxonomy_text


@dataclass(frozen=True)
class ConceptRecord:
    external_id: str
    preferred_label: str
    description: str
    concept_type: str
    alternative_labels: list[str] = field(default_factory=list)
    language: str = "en"
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class OccupationRecord:
    code: str
    title: str
    description: str
    external_id: str
    alternative_labels: list[str] = field(default_factory=list)
    job_zone: int | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class MappingRecord:
    esco_external_id: str
    onet_code: str
    mapping_type: str = "related"
    confidence_score: float = 1.0
    source: str = "import"


@dataclass(frozen=True)
class ParsedTaxonomy:
    concepts: list[ConceptRecord]
    occupations: list[OccupationRecord]
    mappings: list[MappingRecord]


class TaxonomyFileParser:
    aliases = {
        "external_id": ["external_id", "conceptUri", "concept_uri", "uri", "id", "Element ID"],
        "preferred_label": ["preferred_label", "preferredLabel", "preferred label", "title", "Title", "name"],
        "description": ["description", "Description", "definition", "scopeNote"],
        "concept_type": ["concept_type", "conceptType", "type", "category"],
        "alternative_labels": ["alternative_labels", "altLabels", "alt_labels", "alternative label"],
        "language": ["language", "lang"],
        "code": ["code", "Code", "O*NET-SOC Code", "onet_soc_code", "soc_code"],
        "job_zone": ["job_zone", "Job Zone"],
        "esco_external_id": ["esco_external_id", "esco_uri", "ESCO URI"],
        "onet_code": ["onet_code", "O*NET-SOC Code", "onet_soc_code"],
        "mapping_type": ["mapping_type", "mappingType"],
        "confidence_score": ["confidence_score", "confidence"],
        "source": ["source", "mapping_source"],
    }

    def parse(self, filename: str, content: bytes, source_code: str) -> ParsedTaxonomy:
        suffix = Path(filename).suffix.lower()
        text = content.decode("utf-8-sig")
        if suffix == ".json":
            payload = json.loads(text)
            return self._parse_json(payload, source_code)
        if suffix in {".csv", ".tsv", ".txt"}:
            delimiter = "\t" if suffix in {".tsv", ".txt"} else ","
            rows = list(csv.DictReader(StringIO(text), delimiter=delimiter))
            return self._parse_rows(rows, source_code)
        raise ValueError("Taxonomy imports must be JSON, CSV, TSV, or tab-delimited TXT files.")

    def checksum(self, content: bytes) -> str:
        return sha256(content).hexdigest()

    def _parse_json(self, payload: Any, source_code: str) -> ParsedTaxonomy:
        if isinstance(payload, list):
            return self._parse_rows(payload, source_code)
        concepts = [self._concept(row, source_code) for row in payload.get("concepts", [])]
        occupations = [self._occupation(row, source_code) for row in payload.get("occupations", [])]
        mappings = [self._mapping(row) for row in payload.get("mappings", [])]
        return ParsedTaxonomy(
            concepts=[record for record in concepts if record],
            occupations=[record for record in occupations if record],
            mappings=[record for record in mappings if record],
        )

    def _parse_rows(self, rows: list[dict], source_code: str) -> ParsedTaxonomy:
        if not rows:
            return ParsedTaxonomy([], [], [])
        is_mapping = bool(self._value(rows[0], "esco_external_id") and self._value(rows[0], "onet_code"))
        is_occupation = source_code == "ONET" and bool(self._value(rows[0], "code"))
        if is_mapping:
            return ParsedTaxonomy([], [], [record for row in rows if (record := self._mapping(row))])
        if is_occupation:
            return ParsedTaxonomy(
                [], [record for row in rows if (record := self._occupation(row, source_code))], []
            )
        return ParsedTaxonomy(
            [record for row in rows if (record := self._concept(row, source_code))], [], []
        )

    def _concept(self, row: dict, source_code: str) -> ConceptRecord | None:
        external_id = str(self._value(row, "external_id") or "").strip()
        preferred_label = str(self._value(row, "preferred_label") or "").strip()
        if not external_id or not preferred_label:
            return None
        return ConceptRecord(
            external_id=external_id,
            preferred_label=preferred_label,
            description=str(self._value(row, "description") or "").strip(),
            concept_type=str(self._value(row, "concept_type") or ("skill" if source_code == "ESCO" else "skill")).strip().lower(),
            alternative_labels=self._split_labels(self._value(row, "alternative_labels")),
            language=str(self._value(row, "language") or "en").strip(),
            metadata=self._metadata(row),
        )

    def _occupation(self, row: dict, source_code: str) -> OccupationRecord | None:
        code = str(self._value(row, "code") or "").strip()
        title = str(self._value(row, "preferred_label") or "").strip()
        if not code or not title:
            return None
        job_zone_value = self._value(row, "job_zone")
        try:
            job_zone = int(job_zone_value) if job_zone_value not in (None, "") else None
        except (TypeError, ValueError):
            job_zone = None
        return OccupationRecord(
            code=code,
            title=title,
            description=str(self._value(row, "description") or "").strip(),
            external_id=str(self._value(row, "external_id") or f"{source_code}:{code}").strip(),
            alternative_labels=self._split_labels(self._value(row, "alternative_labels")),
            job_zone=job_zone,
            metadata=self._metadata(row),
        )

    def _mapping(self, row: dict) -> MappingRecord | None:
        esco_external_id = str(self._value(row, "esco_external_id") or "").strip()
        onet_code = str(self._value(row, "onet_code") or "").strip()
        if not esco_external_id or not onet_code:
            return None
        try:
            confidence = float(self._value(row, "confidence_score") or 1.0)
        except (TypeError, ValueError):
            confidence = 1.0
        return MappingRecord(
            esco_external_id=esco_external_id,
            onet_code=onet_code,
            mapping_type=str(self._value(row, "mapping_type") or "related"),
            confidence_score=max(0.0, min(confidence, 1.0)),
            source=str(self._value(row, "source") or "import"),
        )

    def _value(self, row: dict, field: str) -> Any:
        for name in self.aliases[field]:
            if name in row and row[name] not in (None, ""):
                return row[name]
        return None

    @staticmethod
    def _split_labels(value: Any) -> list[str]:
        if isinstance(value, list):
            return [str(item).strip() for item in value if str(item).strip()]
        if not value:
            return []
        text = str(value)
        delimiter = "|" if "|" in text else ";"
        return [item.strip() for item in text.split(delimiter) if item.strip()]

    @staticmethod
    def _metadata(row: dict) -> dict:
        return {str(key): value for key, value in row.items() if value not in (None, "")}


def normalized_alternatives(labels: list[str]) -> list[tuple[str, str]]:
    return [(label, normalize_taxonomy_text(label)) for label in labels]
