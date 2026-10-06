"""Topics every workspace starts with.

They read the ABI upper vocabulary (``abi:Person``, ``abi:Organization``) and
enrich it with what the intelligence modules add to it, all in the ``abi:``
namespace: the people module (profile summary, portrait, skills, language
capabilities, certifications, and the acts of working, studying and
certification), the organizations module (website, industry, parent
organization) and, for an employer's own records, the personnel module
(``abi:isEmployedBy``). Every such join is OPTIONAL, so a workspace without
those modules still lists its people and organizations. A workspace may
override any of them from the search settings page; ``reset`` brings back the
definition below.
"""

from __future__ import annotations

from naas_abi.apps.nexus.apps.api.app.services.search.topics.topics__schema import (
    SearchTopic,
    TopicResultRowDef,
    TopicSection,
)

_PREFIXES = """PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>
PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
PREFIX abi: <http://ontology.naas.ai/abi/>
"""


def _act_period(start: str = "start", end: str = "end") -> str:
    """Bind ``?<start>``/``?<end>`` to the dates bounding ``?act``'s temporal region."""
    return f"""  OPTIONAL {{
    ?act abi:occupiesTemporalRegion ?temporal .
    OPTIONAL {{ ?temporal abi:hasFirstInstant ?fi . ?fi abi:instant_date ?{start} . }}
    OPTIONAL {{ ?temporal abi:hasLastInstant ?li . ?li abi:instant_date ?{end} . }}
  }}"""


_ACT_PERIOD = _act_period()

PERSON = SearchTopic(
    id="person",
    label="Person",
    plural_label="People",
    description="People in the workspace graphs: name, headline, skills, experience and education.",
    icon="Users",
    class_iri="http://ontology.naas.ai/abi/Person",
    order=10,
    source="builtin",
    results_query=_PREFIXES
    + """
# The snippet says why a person matched when the card cannot show it (a client, a
# school, a skill, a summary, a mission); otherwise it is their summary, since a
# match on the name or headline is visible as it is. An empty query searched
# nothing, so there is nothing to explain: no snippet.
SELECT ?uri ?title (SAMPLE(?headline) AS ?subtitle)
       (COALESCE(SAMPLE(?why), SAMPLE(?about)) AS ?snippet)
WHERE {
  {
    # Every text a person is known by, weighted by how much a match on it says:
    # the name first, then the headline, the organizations, roles and skills, and
    # last the free text of a summary or a mission.
    SELECT ?uri (MIN(?weight) AS ?rank) (SAMPLE(?found) AS ?evidence)
    WHERE {
      ?uri rdf:type abi:Person .
      {
        { ?uri rdfs:label ?text . BIND(0 AS ?weight) }
        UNION { ?uri abi:hasProfileSummary/abi:headline_text ?text . BIND(1 AS ?weight) }
        UNION {
          # No snippet: the card's Organization row already names the employer.
          ?uri abi:worksFor|abi:isEmployedBy ?organization . ?organization rdfs:label ?text .
          BIND(2 AS ?weight)
        }
        UNION {
          # No snippet: the card's Organization row names the organization.
          ?uri abi:hasActOfWorking/abi:forOrganization ?organization . ?organization rdfs:label ?text .
          BIND(2 AS ?weight)
        }
        UNION {
          ?uri abi:hasActOfWorking/abi:forClient ?client . ?client rdfs:label ?text .
          BIND(2 AS ?weight) BIND(CONCAT("Client: ", ?text) AS ?found)
        }
        UNION {
          ?uri abi:hasActOfStudying/abi:forEducationalOrganization ?school . ?school rdfs:label ?text .
          BIND(3 AS ?weight) BIND(CONCAT("Education: ", ?text) AS ?found)
        }
        UNION {
          # No snippet: the card's Role row shows the title.
          ?uri abi:hasActOfWorking/abi:realizes/abi:job_title ?text .
          BIND(3 AS ?weight)
        }
        UNION {
          ?uri abi:hasSkill ?skill . ?skill rdfs:label ?text .
          BIND(3 AS ?weight) BIND(CONCAT("Skill: ", ?text) AS ?found)
        }
        UNION {
          ?uri abi:hasProfileSummary/abi:summary_content ?text .
          BIND(4 AS ?weight) BIND(?text AS ?found)
        }
        UNION {
          ?uri abi:hasActOfWorking/abi:realizes/abi:hasMission ?mission .
          { ?mission rdfs:label ?text } UNION { ?mission abi:mission_content ?text } UNION { ?mission abi:mission_context ?text }
          BIND(5 AS ?weight) BIND(CONCAT("Mission: ", ?text) AS ?found)
        }
      }
      FILTER(CONTAINS(LCASE(STR(?text)), LCASE("{{ q }}")))
    }
    GROUP BY ?uri
  }
  ?uri rdfs:label ?title .
  # Why the person matched, when the card cannot show it: only for a query, and
  # not for a match on the name or headline (visible as it is).
  BIND(IF(STRLEN("{{ q }}") > 0 && ?rank > 1, ?evidence, ?none) AS ?why)
  OPTIONAL {
    ?uri abi:hasProfileSummary ?summary .
    OPTIONAL { ?summary abi:headline_text ?headline . }
    # The summary stands in for an explanation, so not for an empty query either.
    OPTIONAL { ?summary abi:summary_content ?about . FILTER(STRLEN("{{ q }}") > 0) }
  }
}
GROUP BY ?uri ?title ?rank
ORDER BY ?rank LCASE(STR(?title))
LIMIT {{ limit }}
OFFSET {{ offset }}
""",
    detail_label="Profile",
    image_query=_PREFIXES
    + """
SELECT ?uri ?image
WHERE {
  VALUES ?uri { {{ uris }} }
  ?uri abi:hasPortrait ?p .
  ?p abi:portrait_url ?image .
}
""",
    result_rows=(
        TopicResultRowDef(
            id="organization",
            label="Organization",
            query=_PREFIXES
            + """
SELECT DISTINCT ?uri ?value
WHERE {
  VALUES ?uri { {{ uris }} }
  # The current organization: the employer, or else the organization of a role
  # still open (no last instant), for a person the source gives no employer.
  {
    ?uri abi:worksFor|abi:isEmployedBy ?org .
  } UNION {
    ?uri abi:hasActOfWorking ?act .
    ?act abi:forOrganization ?org .
    FILTER NOT EXISTS { ?act abi:occupiesTemporalRegion ?t . ?t abi:hasLastInstant ?li . }
    FILTER NOT EXISTS { ?uri abi:worksFor|abi:isEmployedBy ?employer . }
  }
  ?org rdfs:label ?value .
}
""",
        ),
        TopicResultRowDef(
            id="role",
            label="Role",
            query=_PREFIXES
            + """
SELECT DISTINCT ?uri ?value
WHERE {
  VALUES ?uri { {{ uris }} }
  ?uri abi:hasActOfWorking ?act .
  ?act abi:realizes ?role .
  ?role abi:job_title ?value .
  # Current roles only: an act whose period has a last instant is past experience.
  FILTER NOT EXISTS { ?act abi:occupiesTemporalRegion ?t . ?t abi:hasLastInstant ?li . }
}
""",
        ),
        TopicResultRowDef(
            id="location",
            label="Location",
            query=_PREFIXES
            + """
SELECT DISTINCT ?uri ?value
WHERE {
  VALUES ?uri { {{ uris }} }
  ?uri abi:hasWorkLocation ?site .
  OPTIONAL { ?site abi:office_label ?office . }
  OPTIONAL { ?site abi:city_name ?city . }
  OPTIONAL { ?site abi:country_name ?country . }
  BIND(COALESCE(?office, ?city, ?country) AS ?value)
  FILTER(BOUND(?value))
}
""",
        ),
        TopicResultRowDef(
            id="linkedin",
            label="LinkedIn",
            query=_PREFIXES
            + """
SELECT DISTINCT ?uri ?value
WHERE {
  VALUES ?uri { {{ uris }} }
  ?uri abi:linkedin_url ?value .
}
""",
        ),
    ),
    header_query=_PREFIXES
    + """
SELECT ?title ?subtitle ?snippet ?image ?url ?employer ?yearsOfExperience ?linkedin
WHERE {
  {{ uri }} rdfs:label ?title .
  OPTIONAL { {{ uri }} abi:linkedin_url ?linkedin . }
  OPTIONAL {
    {{ uri }} abi:hasProfileSummary ?summary .
    OPTIONAL { ?summary abi:headline_text ?subtitle . }
    OPTIONAL { ?summary abi:summary_content ?snippet . }
    OPTIONAL { ?summary abi:years_of_experience ?yearsOfExperience . }
    OPTIONAL { ?summary abi:isSourcedFrom ?doc . ?doc abi:source_url ?url . }
  }
  OPTIONAL { {{ uri }} abi:hasPortrait ?p . ?p abi:portrait_url ?image . }
  OPTIONAL { {{ uri }} abi:worksFor|abi:isEmployedBy ?org . ?org rdfs:label ?employer . }
}
LIMIT 1
""",
    sections=(
        TopicSection(
            id="experience",
            label="Experience",
            empty_text="No experience recorded.",
            link_topic="organization",
            query=_PREFIXES
            + """
SELECT ?title ?item ?subtitle ?snippet ?start ?end ?tags
       ?group ?group_item ?group_image ?client ?client_item ?client_image
WHERE {
  {{ uri }} abi:hasActOfWorking ?act .
  OPTIONAL {
    # The skills and languages this experience developed, one chip each.
    SELECT ?act (GROUP_CONCAT(DISTINCT ?quality; separator="\\n") AS ?tags)
    WHERE {
      {{ uri }} abi:hasActOfWorking ?act .
      {
        ?act abi:developsSkill ?skill .
        OPTIONAL { ?skill rdfs:label ?skillLabel . }
        OPTIONAL { ?skill abi:skill_name ?skillName . }
        BIND(COALESCE(?skillLabel, ?skillName) AS ?quality)
      } UNION {
        ?act abi:developsLanguageCapability ?cap .
        OPTIONAL { ?cap abi:language_name ?language . }
        OPTIONAL { ?cap rdfs:label ?capLabel . }
        OPTIONAL { ?cap abi:proficiency_level ?level . }
        BIND(COALESCE(?language, ?capLabel) AS ?name)
        BIND(IF(BOUND(?level), CONCAT(?name, " (", ?level, ")"), ?name) AS ?quality)
      }
      FILTER(BOUND(?quality))
    }
    GROUP BY ?act
  }
  # Roles are grouped under their employer; the client, when the employer staffed
  # the person there, is its own line. Each with its logo (organizations module).
  OPTIONAL {
    ?act abi:forOrganization ?item . ?item rdfs:label ?orgLabel .
    OPTIONAL { ?item abi:hasLogo ?groupLogo . ?groupLogo abi:logo_url ?group_image . }
  }
  OPTIONAL {
    ?act abi:forClient ?client_item . ?client_item rdfs:label ?client .
    OPTIONAL { ?client_item abi:hasLogo ?clientLogo . ?clientLogo abi:logo_url ?client_image . }
  }
  OPTIONAL { ?act abi:occursIn ?site . ?site rdfs:label ?siteLabel . }
  OPTIONAL {
    ?act abi:realizes ?role .
    OPTIONAL { ?role abi:job_title ?jobTitle . }
    OPTIONAL {
      ?role abi:hasMission ?mission .
      OPTIONAL { ?mission abi:mission_content ?missionContent . }
      OPTIONAL { ?mission abi:mission_context ?missionContext . }
      OPTIONAL { ?mission rdfs:label ?missionLabel . }
    }
  }
  OPTIONAL { ?act rdfs:label ?actLabel . }
"""
            + _ACT_PERIOD
            + """
  BIND(COALESCE(?jobTitle, ?actLabel, "Role") AS ?title)
  # A mission's label is its opening sentence. When the content does not start
  # with it, the label names the mission (a project) and goes in the subtitle.
  BIND(COALESCE(
    IF(STRSTARTS(STR(?missionContent), STR(?missionLabel)), "", CONCAT(" · ", ?missionLabel)),
    ""
  ) AS ?missionName)
  BIND(?orgLabel AS ?group)
  BIND(?item AS ?group_item)
  BIND(CONCAT(?missionName, COALESCE(CONCAT(" · ", ?siteLabel), "")) AS ?line)
  BIND(IF(STRSTARTS(?line, " · "), SUBSTR(?line, 4), ?line) AS ?subtitle)
  # The situation the mission answered, then what was done, one line each.
  BIND(COALESCE(?missionContent, ?missionLabel) AS ?body)
  BIND(COALESCE(CONCAT(?missionContext, "\\n", ?body), ?body, ?missionContext) AS ?snippet)
}
ORDER BY DESC(?start)
LIMIT {{ limit }}
""",
        ),
        TopicSection(
            id="education",
            label="Education",
            empty_text="No education recorded.",
            link_topic="organization",
            query=_PREFIXES
            + """
SELECT ?title ?item ?subtitle ?start ?end
WHERE {
  {{ uri }} abi:hasActOfStudying ?act .
  OPTIONAL { ?act abi:forEducationalOrganization ?item . ?item rdfs:label ?subtitle . }
  OPTIONAL {
    ?act abi:hasEnrollment ?e .
    OPTIONAL { ?e abi:program_name ?program . }
    OPTIONAL { ?e abi:enrollment_date ?enrolled . }
    OPTIONAL { ?e abi:completion_date ?completed . }
  }
  OPTIONAL { ?act abi:hasDegree ?d . ?d rdfs:label ?degree . }
  OPTIONAL { ?act rdfs:label ?actLabel . }
"""
            + _act_period("periodStart", "periodEnd")
            + """
  BIND(COALESCE(?degree, ?program, ?actLabel, "Studies") AS ?title)
  BIND(COALESCE(?periodStart, ?enrolled) AS ?start)
  BIND(COALESCE(?periodEnd, ?completed) AS ?end)
}
ORDER BY DESC(?start)
LIMIT {{ limit }}
""",
        ),
        TopicSection(
            id="skills",
            label="Skills",
            empty_text="No skills recorded.",
            query=_PREFIXES
            + """
SELECT DISTINCT ?title
WHERE {
  {{ uri }} abi:hasSkill ?skill .
  OPTIONAL { ?skill rdfs:label ?skillLabel . }
  OPTIONAL { ?skill abi:skill_name ?skillName . }
  BIND(COALESCE(?skillLabel, ?skillName) AS ?title)
  FILTER(BOUND(?title))
}
ORDER BY LCASE(STR(?title))
LIMIT {{ limit }}
""",
        ),
        TopicSection(
            id="languages",
            label="Languages",
            empty_text="No languages recorded.",
            query=_PREFIXES
            + """
SELECT ?title ?subtitle
WHERE {
  {{ uri }} abi:hasLanguageCapability ?cap .
  OPTIONAL { ?cap abi:language_name ?name . }
  OPTIONAL { ?cap abi:ofLanguage ?language . ?language rdfs:label ?languageLabel . }
  OPTIONAL { ?cap abi:proficiency_level ?subtitle . }
  BIND(COALESCE(?name, ?languageLabel, "Language") AS ?title)
}
LIMIT {{ limit }}
""",
        ),
        TopicSection(
            id="certifications",
            label="Certifications",
            empty_text="No certifications recorded.",
            link_topic="organization",
            query=_PREFIXES
            + """
SELECT ?title ?item ?subtitle ?start ?end ?url
WHERE {
  {{ uri }} abi:hasCertification ?cert .
  OPTIONAL { ?cert abi:certification_name ?name . }
  OPTIONAL { ?cert rdfs:label ?certLabel . }
  # The issuer is stated on the certification, or as the certifying body of
  # the act of certification that awarded it.
  OPTIONAL { ?cert abi:issuedByOrganization ?issuer . ?issuer rdfs:label ?issuerLabel . }
  OPTIONAL {
    ?act abi:hasAwardedCertification ?cert ; abi:forCertifyingOrganization ?certifier .
    ?certifier rdfs:label ?certifierLabel .
  }
  BIND(COALESCE(?issuer, ?certifier) AS ?item)
  BIND(COALESCE(?issuerLabel, ?certifierLabel) AS ?subtitle)
  OPTIONAL { ?cert abi:issue_date ?start . }
  OPTIONAL { ?cert abi:expiry_date ?end . }
  OPTIONAL { ?cert abi:credential_url ?url . }
  BIND(COALESCE(?name, ?certLabel, "Certification") AS ?title)
}
ORDER BY DESC(?start) LCASE(STR(?title))
LIMIT {{ limit }}
""",
        ),
    ),
)

ORGANIZATION = SearchTopic(
    id="organization",
    label="Organization",
    plural_label="Organizations",
    description="Organizations in the workspace graphs, with the people who worked for, with, or studied at them.",
    icon="Building2",
    class_iri="http://ontology.naas.ai/abi/Organization",
    order=20,
    source="builtin",
    results_query=_PREFIXES
    + """
SELECT ?uri ?title
WHERE {
  ?uri rdf:type abi:Organization ;
       rdfs:label ?title .
  OPTIONAL {
    ?act rdf:type abi:ActOfWorking ; abi:forOrganization ?uri .
    ?person abi:hasActOfWorking ?act .
  }
  FILTER(CONTAINS(LCASE(STR(?title)), LCASE("{{ q }}")))
}
GROUP BY ?uri ?title
ORDER BY DESC(COUNT(DISTINCT ?person)) LCASE(STR(?title))
LIMIT {{ limit }}
OFFSET {{ offset }}
""",
    detail_label="Profile",
    # The organizations module's abi:Logo (OrganizationLogoPipeline).
    image_query=_PREFIXES
    + """
SELECT ?uri ?image
WHERE {
  VALUES ?uri { {{ uris }} }
  ?uri abi:hasLogo ?l .
  ?l abi:logo_url ?image .
}
""",
    result_rows=(
        TopicResultRowDef(
            id="website",
            label="Website",
            query=_PREFIXES
            + """
SELECT DISTINCT ?uri ?value
WHERE {
  VALUES ?uri { {{ uris }} }
  ?uri abi:hasWebsite ?w .
  ?w abi:website_url ?value .
}
""",
        ),
        TopicResultRowDef(
            id="people",
            label="People",
            query=_PREFIXES
            + """
SELECT ?uri (STR(COUNT(DISTINCT ?person)) AS ?value)
WHERE {
  VALUES ?uri { {{ uris }} }
  ?act abi:forOrganization ?uri .
  ?person abi:hasActOfWorking ?act .
}
GROUP BY ?uri
""",
        ),
        TopicResultRowDef(
            id="consultants",
            label="Consultants",
            query=_PREFIXES
            + """
SELECT ?uri (STR(COUNT(DISTINCT ?person)) AS ?value)
WHERE {
  VALUES ?uri { {{ uris }} }
  ?act abi:forClient ?uri .
  ?person abi:hasActOfWorking ?act .
}
GROUP BY ?uri
""",
        ),
        TopicResultRowDef(
            id="alumni",
            label="Alumni",
            query=_PREFIXES
            + """
SELECT ?uri (STR(COUNT(DISTINCT ?person)) AS ?value)
WHERE {
  VALUES ?uri { {{ uris }} }
  ?act abi:forEducationalOrganization ?uri .
  ?person abi:hasActOfStudying ?act .
}
GROUP BY ?uri
""",
        ),
    ),
    header_query=_PREFIXES
    + """
SELECT ?title (COUNT(DISTINCT ?employee) AS ?people) (SAMPLE(?industryLabel) AS ?industry)
       (SAMPLE(?parentLabel) AS ?parentOrganization) (SAMPLE(?website) AS ?url)
       (SAMPLE(?logo) AS ?image)
WHERE {
  {{ uri }} rdfs:label ?title .
  OPTIONAL { {{ uri }} abi:hasLogo ?l . ?l abi:logo_url ?logo . }
  OPTIONAL { ?a abi:forOrganization {{ uri }} . ?employee abi:hasActOfWorking ?a . }
  OPTIONAL { {{ uri }} abi:hasIndustry ?i . ?i rdfs:label ?industryLabel . }
  OPTIONAL { {{ uri }} abi:hasParentOrganization ?parent . ?parent rdfs:label ?parentLabel . }
  OPTIONAL { {{ uri }} abi:hasWebsite ?w . ?w abi:website_url ?website . }
}
GROUP BY ?title
LIMIT 1
""",
    # Consultants is a detail fact rather than a header variable, so a
    # workspace can rewrite or drop it in Settings → Search.
    detail_facts=(
        TopicResultRowDef(
            id="consultants",
            label="Consultants",
            query=_PREFIXES
            + """
SELECT ?uri (STR(COUNT(DISTINCT ?person)) AS ?value)
WHERE {
  VALUES ?uri { {{ uris }} }
  ?act abi:forClient ?uri .
  ?person abi:hasActOfWorking ?act .
}
GROUP BY ?uri
""",
        ),
    ),
    sections=(
        TopicSection(
            id="people",
            label="People",
            empty_text="Nobody recorded as working for this organization.",
            link_topic="person",
            query=_PREFIXES
            + """
SELECT ?title ?item (SAMPLE(?jobTitle) AS ?subtitle) (MIN(?s) AS ?start) (MAX(?e) AS ?end)
WHERE {
  ?act abi:forOrganization {{ uri }} .
  ?item abi:hasActOfWorking ?act ; rdfs:label ?title .
  OPTIONAL { ?act abi:realizes ?role . ?role abi:job_title ?jobTitle . }
  OPTIONAL {
    ?act abi:occupiesTemporalRegion ?t .
    OPTIONAL { ?t abi:hasFirstInstant ?fi . ?fi abi:instant_date ?s . }
    OPTIONAL { ?t abi:hasLastInstant ?li . ?li abi:instant_date ?e . }
  }
}
GROUP BY ?item ?title
ORDER BY LCASE(STR(?title))
LIMIT {{ limit }}
""",
        ),
        TopicSection(
            id="engagements",
            label="Engagements as client",
            empty_text="No engagements recorded with this organization as client.",
            link_topic="person",
            query=_PREFIXES
            + """
SELECT ?title ?item ?subtitle ?start ?end
WHERE {
  ?act abi:forClient {{ uri }} .
  ?item abi:hasActOfWorking ?act ; rdfs:label ?title .
  OPTIONAL { ?act abi:forOrganization ?org . ?org rdfs:label ?subtitle . }
"""
            + _ACT_PERIOD
            + """
}
ORDER BY DESC(?start)
LIMIT {{ limit }}
""",
        ),
        TopicSection(
            id="alumni",
            label="Alumni",
            empty_text="Nobody recorded as having studied at this organization.",
            link_topic="person",
            query=_PREFIXES
            + """
SELECT ?title ?item (SAMPLE(?studies) AS ?subtitle) (MIN(?s) AS ?start) (MAX(?e) AS ?end)
WHERE {
  ?act abi:forEducationalOrganization {{ uri }} .
  ?item abi:hasActOfStudying ?act ; rdfs:label ?title .
  OPTIONAL { ?act abi:hasDegree ?d . ?d rdfs:label ?degree . }
  OPTIONAL { ?act abi:hasEnrollment ?en . ?en abi:program_name ?program . }
  BIND(COALESCE(?degree, ?program) AS ?studies)
"""
            + _act_period("s", "e")
            + """
}
GROUP BY ?item ?title
ORDER BY LCASE(STR(?title))
LIMIT {{ limit }}
""",
        ),
        TopicSection(
            id="certified",
            label="Certified people",
            empty_text="No certifications recorded as issued by this organization.",
            link_topic="person",
            query=_PREFIXES
            + """
SELECT ?title ?item (GROUP_CONCAT(DISTINCT ?certName; separator="\\n") AS ?tags)
WHERE {
  { ?cert abi:issuedByOrganization {{ uri }} . }
  UNION
  { ?act abi:forCertifyingOrganization {{ uri }} ; abi:hasAwardedCertification ?cert . }
  ?item abi:hasCertification ?cert ; rdfs:label ?title .
  OPTIONAL { ?cert abi:certification_name ?name . }
  OPTIONAL { ?cert rdfs:label ?certLabel . }
  BIND(COALESCE(?name, ?certLabel) AS ?certName)
}
GROUP BY ?item ?title
ORDER BY LCASE(STR(?title))
LIMIT {{ limit }}
""",
        ),
    ),
)

BUILTIN_TOPICS: dict[str, SearchTopic] = {t.id: t for t in (PERSON, ORGANIZATION)}
