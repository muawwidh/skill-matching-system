# Database ERD

Phases 1 and 2 create the authentication and document processing foundation.

```mermaid
erDiagram
  USERS ||--o{ REFRESH_TOKENS : owns
  USERS }o--o{ ROLES : has
  USERS ||--o| CANDIDATE_PROFILES : owns
  CANDIDATE_PROFILES ||--o{ CV_DOCUMENTS : owns
  CV_DOCUMENTS ||--o{ CV_SECTIONS : contains
  CV_DOCUMENTS ||--o{ EXTRACTED_CANDIDATE_TERMS : produces
  CANDIDATE_PROFILES ||--o{ CANDIDATE_SKILLS : reviews
  JOBS ||--o{ JOB_SECTIONS : contains
  JOBS ||--o{ EXTRACTED_JOB_TERMS : produces
  JOBS ||--o{ JOB_SKILLS : reviews

  USERS {
    uuid id PK
    string email
    string full_name
    string hashed_password
    string status
    string source
    datetime created_at
    datetime updated_at
  }

  ROLES {
    uuid id PK
    string name
    string description
    datetime created_at
    datetime updated_at
  }

  REFRESH_TOKENS {
    uuid id PK
    uuid user_id FK
    string token_hash
    datetime expires_at
    datetime revoked_at
    datetime created_at
    datetime updated_at
  }

  CANDIDATE_PROFILES {
    uuid id PK
    uuid user_id FK
    string headline
    text summary
    boolean consent_to_process_cv
    string status
    string source
  }

  CV_DOCUMENTS {
    uuid id PK
    uuid candidate_profile_id FK
    string original_filename
    string content_type
    string source
    string status
    text raw_text
    text cleaned_text
    integer size_bytes
  }

  CV_SECTIONS {
    uuid id PK
    uuid cv_document_id FK
    string section_type
    string heading
    text content
  }

  JOBS {
    uuid id PK
    string title
    string company
    string location
    string employment_type
    text description
    text cleaned_description
    string status
  }

  JOB_SECTIONS {
    uuid id PK
    uuid job_id FK
    string section_type
    string heading
    text content
  }

  EXTRACTED_CANDIDATE_TERMS {
    uuid id PK
    uuid cv_document_id FK
    string raw_text
    string normalized_text
    string term_type
    string source_section
    text evidence_sentence
    string extraction_method
    float confidence_score
  }

  CANDIDATE_SKILLS {
    uuid id PK
    uuid candidate_profile_id FK
    uuid extracted_term_id FK
    string raw_text
    string normalized_text
    string skill_type
    text evidence_sentence
    float confidence_score
    string review_status
  }

  EXTRACTED_JOB_TERMS {
    uuid id PK
    uuid job_id FK
    string raw_text
    string normalized_text
    string term_type
    string source_section
    text evidence_sentence
    string requirement_type
  }

  JOB_SKILLS {
    uuid id PK
    uuid job_id FK
    uuid extracted_term_id FK
    string raw_text
    string normalized_text
    string skill_type
    string requirement_type
    string review_status
  }
```

Taxonomy, matching, and evaluation tables are reserved for the later phases described in the source
requirements.
