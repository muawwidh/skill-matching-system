# Taxonomy Integration

Phase 4 stores ESCO and O*NET releases locally so document processing and matching do not depend on
live external API calls. Each import records its source, version, release date, original filename,
checksum, import time, and whether it is a bundled development sample.

## Import Flow

1. An administrator or researcher uploads an official JSON, CSV, TSV, or tab-delimited TXT release.
2. The importer maps common ESCO and O*NET column names into normalized concept records.
3. Concepts, alternative labels, O*NET-SOC occupations, and release metadata are stored locally.
4. A new release becomes active and the previous release from the same source becomes inactive.
5. ESCO-O*NET occupation mappings are imported after both source releases are available.

The files under `data/sample` exercise the same importer but are marked as sample data. They are not
the production taxonomy and should not replace official releases.

## Linking Strategy

Extracted candidate and job terms are linked in this order:

1. Exact preferred-label match: confidence 1.00.
2. Exact alternative-label match: confidence 0.98.
3. RapidFuzz label similarity: accepted from 0.70 and scaled below exact-match confidence.

The top five candidates are stored. A top result at or above 0.95 is automatically approved. Other
results remain pending for administrator or researcher review. Human corrections are stored with the
reviewer and approval time so the decision remains auditable.

## Updating Releases

Import the new official release under its published version. Existing extracted terms can be linked
again through `POST /taxonomy/link`; reprocessing a CV or job also reruns linking automatically. Match
and model phases can consume approved concept IDs without depending on labels that may change between
taxonomy versions.
