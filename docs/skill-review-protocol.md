# Skill Review Protocol

Rules for reviewers (administrators and researchers) who approve, reject or
correct extracted job skills, and for candidates reviewing their own CV skills.
Review decisions are stored and are never overwritten by re-extraction
(D039).

## Job skill requirement type

Extraction sets `requirement_type` from the section heading (D038):
- requirements and qualifications sections give `required`;
- preferred, desirable, nice-to-have and bonus sections give `preferred`;
- all other text gives `unknown`, which matching counts as preferred (D036).

A reviewer may correct that type. When the sentence wording and the heading
disagree, **the sentence wording beats the heading**:
- A skill introduced as *familiarity with*, *exposure to*, *… is a plus*,
  *… is considered an advantage*, *… is an asset*, *nice to have* or
  *desirable* is `preferred`, even under a Requirements or Qualifications
  heading.
- A skill stated as *must*, *required* or *essential* is `required`, even under
  a heading that gives `unknown`.

Example (2026-11-18): under the "Your Profile" heading of one job,
"Familiarity with Python frameworks such as Django, Flask, or FastAPI is
considered an advantage" and "Exposure to cloud technologies (Azure, AWS, GCP),
Docker, or CI/CD tools is considered an advantage". Extraction v3 gives
`required`; the reviewed value stays `preferred`.

## Status

- **Approve** only text that names a skill, tool, qualification or
  requirement of the role in that sentence.
- **Reject** matches inside unrelated text: benefits, application
  instructions, links or document names, company programmes (for example
  "Agile Hybrid Working Framework (PDF)"), or a word used in another sense.
- **Correct** the text or type instead of rejecting it when the occurrence is
  right but its span or type is wrong. Corrected spans are kept on
  re-extraction (D039 edited-span guard).
- Changing the requirement type or status keeps the occurrence's taxonomy
  links and review history.
