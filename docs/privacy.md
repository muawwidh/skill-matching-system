# Privacy Decisions

The application is decision support only and must not be used as an automatic hiring decision system.

## Controls in place

- Secure password hashing. Refresh tokens are stored only as hashes.
- Role-aware dependencies protect administrative routes.
- Candidate-facing copy states that unrelated personal attributes must not affect matching. Matching uses
  approved skills only; age, gender, religion, nationality, marital status and photographs are not inputs.
- Explicit consent is required before a pasted or uploaded CV is processed.
- Uploaded files are parsed into text and are not written to persistent file storage.
- Candidates can delete their own account and all data derived from it, confirmed with their password (D047).
- Job rankings and skill coverage are visible only to the candidate they belong to; administrators and
  researchers see aggregate counts only, with no per-candidate ranking view (D037).

## Work entries (relevant experience, D060)

Candidates can enter their work history on the CVs page: a job title, a start month, an end month or
"present", and optionally an ESCO occupation they choose. No employer, location or other detail is asked
for or stored. Dates found in a CV are only offered to pre-fill the form; nothing is saved until the
candidate adds the entry. Entries are visible to the candidate only and can be edited or deleted at any
time. Staff accounts cannot read or use them.

## Deleting a CV

A candidate can delete any of their CVs on the CVs page, after a confirmation. This removes the CV text and
its sections, the skills extracted from it with their review decisions, and their taxonomy link suggestions
and selected links. Skills the candidate added by hand belong to the profile and stay until the candidate
removes them in skill review. Work entries also belong to the profile and stay until the candidate
deletes them. The matching profile is rebuilt from the remaining CVs and manual skills
(D041, D046). Taxonomy review events for that CV's skills are retained; they hold concept labels and
reviewer IDs, not CV text.

## Deleting the account

A candidate can delete their account on the Dashboard ("Delete my account and data"), confirmed with their
password (`POST /auth/delete-account`, D047). This deletes:

- the account, its role assignments and refresh tokens;
- the candidate profile and all CVs, CV sections and extracted terms;
- all candidate skills, extracted and manual, with their review decisions;
- all work entries (D060);
- taxonomy link suggestions, selected links and taxonomy review events for the candidate's skills;
- the profile embedding;
- processing logs that refer to the profile or its CVs.

Nothing that identifies the account is kept. Data outside the candidate's own records is unchanged (jobs,
taxonomy releases, other candidates). Database backups made before the deletion still contain the data
until they are rotated; there is no automatic backup expiry in this project.

Administrator and researcher accounts cannot be deleted this way: their review decisions are attributed to
them and they are removed by an administrator.

## Not yet in place

- Retention periods and automatic expiry of inactive accounts.
- An export of a candidate's own data.
