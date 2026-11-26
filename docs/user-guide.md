# User guide

## For candidates

### 1. Create an account

Open the application, choose **Create an account**, and enter your name,
e-mail address and a password. You land on the **Dashboard**, which shows the
steps to set up your profile.

### 2. Add your CV

Go to **My profile** → **My CVs**.

- Drop a file on the upload area or choose **Choose a file** (readable PDF,
  Word DOCX or plain text, up to 5 MB), or choose **Paste text instead**.
- Tick the consent box and select **Upload and process**.

The text is read, split into sections and searched for skills. Scanned PDFs
(images of text) cannot be read. You can add more than one CV; skills from
all of them form your profile.

### 3. Check your skills

The **Skills** card on My profile shows:

- **Confirmed** skills (✓): used for matching.
- **Needs review** (dashed): found in your CV but not yet confirmed. Select
  **Review now**, then confirm, reject or correct each one and save.
- **Added by you**: skills you added with **+ Add a skill**. Remove one with
  the × on its chip.

Only confirmed skills and skills you added are used. Under **Review skills and
ESCO links** you can also see which ESCO concept each skill is linked to and
choose a different suggestion if a link is wrong.

The **Languages** card lists languages found in your CV (confirm or reject
each one) and languages you add with **+ Add a language**, with an optional
level (A1–C2 or native). Remove one with the × on its chip. Languages are
compared by name with the languages a job asks for; levels are not compared,
and languages never change the order of your jobs.

The dark **Your matching profile** box shows which CVs and how many skills are
used for matching.

### 4. Add work experience (optional)

In **Work experience**, select **+ Add experience** and enter a job title, a
start month and an end month (or "present"). Pick the ESCO occupation that
fits best from the suggestions, search for another one, or choose **None of
these**. Dates found in your CV are offered under "Found in your CV"; select
**Use** to fill the form with them.

Work experience is only used to show your years of related experience next to
each job. It never changes the order of the jobs.

### 5. See your matches

Open **Jobs**. The list shows the jobs that fit your profile best, best first,
in pages of 10, 25 or 50. The bar on each job counts its required skills. If the
ad does not mark any skill as required, it counts every skill the ad mentions
("Skills mentioned in the ad: X of Y in your profile"); if no skills could be
identified, it says so and points to the original ad. The same posting published
for several locations is shown once, with all its locations. Select a job to see
its details:

- **Why this job**: a short explanation from your skills.
- **Skills you have**: the job's skills you have, and how they matched (same
  ESCO concept or same name).
- **Related skill in your profile**: job skills you do not have, but a close
  skill of yours shares an ESCO area with them.
- **Skills to develop**: the job's missing skills, marked required or preferred.
- **Languages: X of Y matched**: the languages the job asks for, ✓ in your
  profile or ○ not found in your profile (by name only). Shown on the job card
  too; not counted in the required/preferred skills.
- **Experience**: your years in related roles against the years the job asks
  for, when both are known.
- **Also required — not assessed**: qualifications, certificates and similar
  requirements the system cannot check. Languages appear here only while
  you have no confirmed language; add your languages on My profile to compare.
- **View original posting** opens the job at its source.

On jobs collected from job sites, skills marked "automatically extracted, not
reviewed" were found by the system and not checked by a person.

**Hide jobs above my experience** hides jobs whose stated minimum is above
your related experience. Jobs without a stated minimum are never hidden.

### 6. Dashboard

The Dashboard shows your setup progress, your top 3 matches, the skill that is
missing most often among your top 10 jobs ("Your skill gaps"), and the number
of live jobs with the date of the last update.

### 7. Delete data

- **A CV:** on My profile, select the bin icon next to the CV and confirm.
  Work entries taken from that CV are removed too unless you untick the box.
- **Your account:** on My profile → **Your data** → **Delete my account and
  data**, confirmed with your password. This cannot be undone.

See **Privacy** in the header for what is stored and who can see it.

## For administrators and researchers

Staff accounts are created by registering and then running
`python -m app.utils.manage_role <e-mail> admin` (or `researcher`) on the
server. Sign in again afterwards. Staff accounts have no candidate profile and
cannot see any candidate's results.

### Taxonomy page

- **Taxonomy releases:** upload an ESCO 1.2.1 English CSV ZIP, an O*NET 29.0
  TXT or 31.0 CSV ZIP, or an ESCO–O*NET mapping file, with its exact version
  and release date. The new release becomes active; a failed import leaves the
  previous one in place. **Load development sample** loads a tiny test release
  that must not be used as real data.
- **Concept search:** look up ESCO and O*NET concepts and occupations.
- **Occupation mappings:** browse ESCO–O*NET occupation mappings.
- **Taxonomy review:** skill terms whose link to a concept was not approved
  automatically. Choose the right concept, reject wrong suggestions, or replace
  an existing selection; every decision is recorded with its history. The
  default queue shows CV terms and terms of manually added jobs; use the scope
  selector for live-job terms.

After importing a new ESCO release, run
`python -m app.retrieval.cli embed-occupation-labels` on the server once.

### Jobs page

- **Add a job** by hand (title, company, location, description); its skills
  are extracted and linked like a CV's.
- Review a job's extracted skills: confirm, reject or correct them.
- Archive jobs that are no longer open.
- **Live jobs** (administrators): **Run import** fetches new postings from the
  configured public job sources and shows the result of the latest runs. It can
  also run on a schedule (see the README).

### Dashboard (administrators)

The system overview shows totals: taxonomy releases, candidate accounts and
CVs, jobs and skill reviews. It never shows one person's data or results.
