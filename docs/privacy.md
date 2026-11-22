# Privacy and data protection

SkillGap processes CVs, which contain personal data. This document lists the
measures taken with the General Data Protection Regulation (GDPR) in mind. It
describes the software; an organisation running it remains the controller and
is responsible for its own privacy notice, records and legal review.

## Purpose and legal basis

- **Purpose.** Career guidance for the candidate: which jobs fit their skills
  and which skills they lack. Results are not shared with employers and are
  not used to select or reject anyone (no automated decision with legal or
  similar effect, Art. 22).
- **Consent.** A CV is processed only after the candidate ticks the consent
  box at upload or paste. Consent can be withdrawn at any time by deleting the
  CV or the account.

## Data minimisation

| Data | Stored | Not stored |
| --- | --- | --- |
| Account | Name, e-mail address, password as a bcrypt hash | — |
| CV | Extracted text, sections, found skills with the sentence they came from | The uploaded file itself (read in memory only) |
| Skills | Found and hand-added skills, the candidate's review decisions, ESCO links | — |
| Work experience (optional) | Job title, start and end month, chosen ESCO occupation | Employer, location, description, references |
| Settings | The Jobs page experience filter | — |
| Matching | One embedding vector of the confirmed skills | Rankings and explanations (computed when viewed, never stored) |

**Not used for matching:** age, gender, religion, nationality, marital status,
photographs or any other personal characteristic. Only confirmed skills feed
the ranking. Years of experience never affect the ranking, because they
correlate with age; they are only shown next to a job and, if the candidate
chooses, used to hide jobs above their experience.

## Access and confidentiality

- Each candidate sees only their own CVs, skills, work entries and results.
- Rankings and explanations can only be requested by the candidate they
  belong to; administrator and researcher accounts cannot request them.
- The administrator overview shows totals only, never one person's data.
- Staff who review taxonomy links may see single skill terms found in CVs,
  without the candidate's name or the CV text.
- Passwords are hashed with bcrypt; refresh tokens are stored only as hashes,
  expire after 7 days and are revoked on sign-out; access tokens expire after
  30 minutes.
- The embedding model runs locally; CV content is never sent to an external
  service. Taxonomies are local copies; no external lookups happen during
  matching.

## Rights of the candidate

| Right | How it is supported |
| --- | --- |
| Access (Art. 15) | All stored CV text, sections, skills, work entries and links are visible on My profile |
| Rectification (Art. 16) | Skills, ESCO links and work entries can be corrected or removed at any time |
| Erasure (Art. 17) | Deleting a CV removes its text, sections, found skills, review decisions and links, and by default the work entries taken from it. Deleting the account (password confirmation) removes the account, all CVs, skills, work entries, settings, the embedding, review events for the candidate's skills and processing logs about them, in one transaction |
| Withdraw consent (Art. 7) | Delete the CV or the account |
| Data portability (Art. 20) | **Not implemented**: there is no export of a candidate's data |

Backups made before a deletion still contain the data until they are
replaced; backup rotation is the operator's responsibility.

## Job postings

Live jobs are taken only from public job APIs. Before a posting is stored,
e-mail addresses, phone numbers and contact names after a contact cue
("Recruiter:", "reach out to", ...) are removed. Each job keeps a link to the
original posting.

## Not in place

- Data export for candidates.
- Retention periods and automatic deletion of inactive accounts.
- Automatic backup expiry.
- A data protection impact assessment, which an operator should carry out
  before using the system with real candidates.
