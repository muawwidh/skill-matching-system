# Privacy Decisions

The application is decision support only and must not be used as an automatic hiring decision system.

Phase 1 privacy controls:

- Secure password hashing.
- Refresh tokens are stored only as hashes.
- Role-aware dependencies are available for protected routes.
- Candidate-facing copy states that unrelated personal attributes must not affect matching.
- Phase 2 requires explicit candidate consent before CV paste or upload processing.
- Uploaded files are parsed into text and are not written to persistent file storage in this baseline.

Future phases must add explicit CV-processing consent, data deletion, retention controls, audit logs,
and exclusion of age, gender, religion, nationality, marital status, photographs, and other unrelated
personal attributes from matching.
