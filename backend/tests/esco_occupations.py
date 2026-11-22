"""A tiny active ESCO release with occupations and ISCO groups, for relevant-experience tests."""
from datetime import datetime, timezone

from app.db.models import TaxonomyConcept, TaxonomyLabel, TaxonomyRelationship, TaxonomySource, TaxonomyVersion
from app.taxonomy.concept_index import clear_concept_index_cache
from app.taxonomy.occupations import clear_occupation_catalog

ISCO = {"25": "Information and communications technology professionals",
        "251": "Software and applications developers and analysts", "2511": "Systems analysts",
        "2512": "Software developers", "252": "Database and network professionals",
        "2521": "Database designers and administrators", "122": "Sales, marketing and development managers",
        "1221": "Sales and marketing managers"}
# label -> (ISCO unit group, parent occupation label or None, alternative labels)
OCCUPATIONS = {
    "software developer": ("2512", None, ["software engineer", "programmer"]),
    "data scientist": ("2511", None, []),
    "database administrator": ("2521", None, ["dba"]),
    "sales manager": ("1221", None, []),
    "cloud devops engineer": (None, "software developer", ["devops engineer"]),
}


def add_esco_occupations(db) -> dict[str, TaxonomyConcept]:
    clear_concept_index_cache()
    clear_occupation_catalog()
    from app.taxonomy.occupation_embeddings import clear_label_matrix
    clear_label_matrix()
    source = TaxonomySource(code="ESCO", name="ESCO")
    db.add(source)
    db.flush()
    version = TaxonomyVersion(source_id=source.id, version="test-1", status="active",
                              imported_at=datetime.now(timezone.utc))
    db.add(version)
    db.flush()

    def concept(label, kind, external):
        item = TaxonomyConcept(taxonomy_version_id=version.id, external_id=external, preferred_label=label,
                               normalized_label=label.lower(), concept_type=kind)
        db.add(item)
        db.flush()
        return item

    groups = {code: concept(label, "isco_group", f"http://data.europa.eu/esco/isco/C{code}")
              for code, label in ISCO.items()}
    for code, item in groups.items():
        if len(code) > 2 and code[:-1] in groups:
            db.add(TaxonomyRelationship(taxonomy_version_id=version.id, source_concept_id=item.id,
                                        target_concept_id=groups[code[:-1]].id, relationship_type="broader"))
    occupations = {}
    for label, (code, parent, alternatives) in OCCUPATIONS.items():
        occupations[label] = concept(label, "occupation", f"http://data.europa.eu/esco/occupation/{label}")
        for alternative in alternatives:
            db.add(TaxonomyLabel(concept_id=occupations[label].id, label=alternative, normalized_label=alternative))
    for label, (code, parent, _) in OCCUPATIONS.items():
        target = groups[code] if code else occupations[parent]
        db.add(TaxonomyRelationship(taxonomy_version_id=version.id, source_concept_id=occupations[label].id,
                                    target_concept_id=target.id, relationship_type="broader"))
    db.commit()
    return occupations
