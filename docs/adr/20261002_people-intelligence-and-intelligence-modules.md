# People intelligence apart from personnel; intelligence modules

Status: Accepted

Date: 2026-10-02

## Context

`domains/personnel/` (S1) held two jobs. One was what an organization records about its own staff: the employee role, job position, employment record and contract, remuneration, grade, service line, and the workforce cockpit. The other was what can be known about **any** person from what is published about them: acts of working and studying at any employer, certifications, skills, languages, interests, recommendations, the published profile, and People Search over all of it.

The staff system files modules by the question they answer. S1 asks *who is in the organization, and what is their status?*; S2 asks *what is true about the world outside us?* A candidate's career, a client CFO's certifications or a competitor partner's education are S2 facts, and so is the public career of your own staff. Keeping them in S1 forced HR classes into every career record: `personnel:ActOfWorking` was an Act of Employment that realized an `EmployeeRole` under an `EmploymentContract` even for a job at another company, and a public team page could only be imported as `EmployeeRole` + `JobPosition` + `isEmployedBy`.

`intelligence/` also mixed filing styles: `organizations` was a loadable module nested under the bucket's `ontologies/` folder (so `onto2py` wrote its class stubs a level up), and `wsr` was a bucket app whose credentials and agent lived on the bucket module.

## Decision

**Intelligence modules.** `intelligence/modules/` holds loadable modules, each with its own `ABIModule`, following `operations/modules/*`: `organizations`, `people` and `wsr`. WSR gets its own configuration (the former `WSRConfiguration`, now `ABIModule.Configuration`), carries `WSRAgent`, and its dashboard manifest moves to `apps/dashboard/` (app id `naas_abi_marketplace.domains.intelligence.modules.wsr:dashboard`).

**People intelligence.** `intelligence/modules/people` owns the generic person vocabulary under a new namespace, `http://ontology.naas.ai/people/` (`people:`), its named graph `http://ontology.naas.ai/graph/people`, and datastore path `intelligence/people`:

- processes `ActOfWorking` (a CCO Planned Act only), `ActOfStudying`, `ActOfCertification`, `ActOfProfiling` (formerly `ActOfPersonnelProfiling`);
- `OccupationRole` (≡ CCO Occupation Role, with `job_title`) as what an act of working realizes; `Mission`, `Skill`, `LanguageCapability`, `Interest`, `Certification`, `Recommendation`, `ProfileSummary`, `Portrait`, `ProfileDocument`, `StudentRole`, `EnrollmentRecord`, `AcademicDegree`;
- `people:employment_type` - the engagement type a source publishes - and `people:worksFor`, a convenience edge for "a source says they work there";
- the pipelines, the demo sources, People Search (`apps/people`, mounted at `/api/people`, dataset namespace `people`), `PeopleAgent`, and the 7-bucket person graph page (`apps/people/graph_page/`) with its payload builder.

**Personnel specializes, never redefines.** `personnel/` keeps only the internal records, as subclasses or relations of people classes:

- `personnel:ActOfEmployment` ⊑ `people:ActOfWorking`, CCO Act of Employment; realizes `personnel:EmployeeRole` ⊑ `people:OccupationRole`; concretizes `personnel:EmploymentContract` (`hasContract`, `contract_type`);
- `JobPosition`, `JobDescription`, `EmploymentRecord`, `EmploymentStatus`, `Remuneration`, `Grade`, `ServiceLine`, `isEmployedBy`;
- the HR queries (roster, positions, headcount), `ActOfEmploymentPipeline`, `PersonnelProfilePipeline` (employer, service line, grade), the cockpit.

`PersonnelOntology` imports `PeopleOntology`; personnel code imports people code; the cockpit embeds people's graph page (served at `/api/personnel-cockpit/graph-page/`). Nothing in the people module imports, queries or names a personnel IRI. Grade and service line stay internal: People Search no longer shows them, and its default facet is country.

**Same individual, two graphs.** An act of working is minted once (`act_of_working_uri`, people namespace) and written to the people graph. When it is also an act of employment, the personnel module types the same IRI `personnel:ActOfEmployment`, types its occupation role `personnel:EmployeeRole`, and writes the position, contract and remuneration to the personnel graph, together with each person's identity triples so HR queries read one graph.

## Consequences

Every former `personnel:` IRI for a generic term is now `people:`, and module paths change (`domains.personnel.pipelines` → `domains.intelligence.modules.people.pipelines`, `domains.personnel.apps.people` → `domains.intelligence.modules.people.apps.people`, `domains.intelligence.ontologies.organizations` → `domains.intelligence.modules.organizations`). Graphs and datasets built before this change must be rebuilt: a triple store holding the old `…/graph/personnel` career data keeps it under the old IRIs until it is regenerated. The Nexus built-in search topics read `people:` (with `personnel:` only for service line, grade and `isEmployedBy`); a workspace that overrode a topic from the search settings page keeps its override and must reset or edit it. This supersedes the `domains/personnel/apps/people/` path in `20261001_nexus-search-topics.md`.

`ActOfWorkingPipeline` and the source loaders accept `contract_type` as an alias of `employment_type`, so existing source files load unchanged. A configuration that enabled the intelligence bucket for WSR must add `naas_abi_marketplace.domains.intelligence.modules.wsr` with the credentials moved off the `wsr:` block; one that used organizations' ontologies enables `…intelligence.modules.organizations`, since the bucket no longer loads them.

The cockpit's own `css/app.css` still carries the graph page rules for its shell, and `graph_page/graph-page.css` carries them for People Search: a style change to the graph page is made in both until the cockpit links the people stylesheet.
