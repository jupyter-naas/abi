"""Topics every workspace starts with.

They read the ABI upper vocabulary (``abi:Person``, ``abi:Organization``) and
enrich it with the people intelligence module's properties (``people:``) and,
for an employer's own records (service line, grade), the personnel module's
(``personnel:``) when present — every such join is OPTIONAL, so a workspace
without those modules still lists its people and organizations. A workspace may override any of them from the
search settings page; ``reset`` brings back the definition below.
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

_ACT_PERIOD = """  OPTIONAL {
    ?act abi:occupiesTemporalRegion ?temporal .
    OPTIONAL { ?temporal abi:hasFirstInstant ?fi . ?fi abi:instant_date ?start . }
    OPTIONAL { ?temporal abi:hasLastInstant ?li . ?li abi:instant_date ?end . }
  }"""

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
SELECT ?uri ?title (SAMPLE(?headline) AS ?subtitle) (SAMPLE(?about) AS ?snippet)
WHERE {
  ?uri rdf:type abi:Person ;
       rdfs:label ?title .
  OPTIONAL {
    ?uri abi:hasProfileSummary ?summary .
    OPTIONAL { ?summary abi:headline_text ?headline . }
    OPTIONAL { ?summary abi:summary_content ?about . }
  }
  OPTIONAL { ?uri abi:hasSkill ?skill . ?skill rdfs:label ?skillLabel . }
  FILTER(
    CONTAINS(LCASE(STR(?title)), LCASE("{{ q }}"))
    || (BOUND(?headline) && CONTAINS(LCASE(STR(?headline)), LCASE("{{ q }}")))
    || (BOUND(?skillLabel) && CONTAINS(LCASE(STR(?skillLabel)), LCASE("{{ q }}")))
  )
}
GROUP BY ?uri ?title
ORDER BY LCASE(STR(?title))
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
  ?uri abi:worksFor|abi:isEmployedBy ?org .
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
  OPTIONAL { ?site abi:country_name ?country . }
  BIND(COALESCE(?office, ?country) AS ?value)
  FILTER(BOUND(?value))
}
""",
        ),
    ),
    header_query=_PREFIXES
    + """
SELECT ?title ?subtitle ?snippet ?image ?url ?employer ?yearsOfExperience
WHERE {
  {{ uri }} rdfs:label ?title .
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
  OPTIONAL { ?act abi:forOrganization ?item . ?item rdfs:label ?orgLabel . }
  OPTIONAL { ?act abi:forClient ?client . ?client rdfs:label ?clientLabel . }
  OPTIONAL {
    ?act abi:realizes ?role .
    OPTIONAL { ?role abi:job_title ?jobTitle . }
    OPTIONAL { ?role abi:hasMission ?mission . ?mission abi:mission_content ?snippet . }
  }
  OPTIONAL { ?act rdfs:label ?actLabel . }
"""
            + _ACT_PERIOD
            + """
  BIND(COALESCE(?jobTitle, ?actLabel, "Role") AS ?title)
  BIND(IF(BOUND(?clientLabel), CONCAT(COALESCE(?orgLabel, ""), " · client: ", ?clientLabel), ?orgLabel) AS ?subtitle)
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
  OPTIONAL { ?act abi:hasEnrollment ?e . ?e abi:program_name ?program . }
  OPTIONAL { ?act abi:hasDegree ?d . ?d rdfs:label ?degree . }
  OPTIONAL { ?act rdfs:label ?actLabel . }
"""
            + _ACT_PERIOD
            + """
  BIND(COALESCE(?degree, ?program, ?actLabel, "Studies") AS ?title)
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
  ?skill rdfs:label ?title .
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
  OPTIONAL { ?cap abi:proficiency_level ?subtitle . }
  BIND(COALESCE(?name, "Language") AS ?title)
}
LIMIT {{ limit }}
""",
        ),
    ),
)

ORGANIZATION = SearchTopic(
    id="organization",
    label="Organization",
    plural_label="Organizations",
    description="Organizations in the workspace graphs, with the people who worked for or with them.",
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
    result_rows=(
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
    ),
    header_query=_PREFIXES
    + """
SELECT ?title (COUNT(DISTINCT ?employee) AS ?people)
WHERE {
  {{ uri }} rdfs:label ?title .
  OPTIONAL { ?a abi:forOrganization {{ uri }} . ?employee abi:hasActOfWorking ?a . }
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
    ),
)

BUILTIN_TOPICS: dict[str, SearchTopic] = {t.id: t for t in (PERSON, ORGANIZATION)}
