"""Topics every workspace starts with.

They read the ABI upper vocabulary (``abi:Person``, ``abi:Organization``) and
enrich it with the personnel module's properties when present — every
personnel join is OPTIONAL, so a workspace without that module still lists its
people and organizations. A workspace may override any of them from the
search settings page; ``reset`` brings back the definition below.
"""

from __future__ import annotations

from naas_abi.apps.nexus.apps.api.app.services.search.topics.topics__schema import (
    SearchTopic,
    TopicSection,
)

_PREFIXES = """PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>
PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
PREFIX abi: <http://ontology.naas.ai/abi/>
PREFIX personnel: <http://ontology.naas.ai/personnel/>
"""

_ACT_PERIOD = """  OPTIONAL {
    ?act abi:occupiesTemporalRegion ?temporal .
    OPTIONAL { ?temporal abi:hasFirstInstant ?fi . ?fi personnel:instant_date ?start . }
    OPTIONAL { ?temporal abi:hasLastInstant ?li . ?li personnel:instant_date ?end . }
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
SELECT ?uri ?title (SAMPLE(?headline) AS ?subtitle) (SAMPLE(?about) AS ?snippet) (SAMPLE(?portrait) AS ?image)
WHERE {
  ?uri rdf:type abi:Person ;
       rdfs:label ?title .
  OPTIONAL {
    ?uri personnel:hasProfileSummary ?summary .
    OPTIONAL { ?summary personnel:headline_text ?headline . }
    OPTIONAL { ?summary personnel:summary_content ?about . }
  }
  OPTIONAL { ?uri personnel:hasPortrait ?p . ?p personnel:portrait_url ?portrait . }
  OPTIONAL { ?uri personnel:hasSkill ?skill . ?skill rdfs:label ?skillLabel . }
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
    header_query=_PREFIXES
    + """
SELECT ?title ?subtitle ?snippet ?image ?url ?employer ?office ?country ?serviceLine ?grade ?yearsOfExperience
WHERE {
  {{ uri }} rdfs:label ?title .
  OPTIONAL {
    {{ uri }} personnel:hasProfileSummary ?summary .
    OPTIONAL { ?summary personnel:headline_text ?subtitle . }
    OPTIONAL { ?summary personnel:summary_content ?snippet . }
    OPTIONAL { ?summary personnel:years_of_experience ?yearsOfExperience . }
    OPTIONAL { ?summary personnel:isSourcedFrom ?doc . ?doc personnel:source_url ?url . }
  }
  OPTIONAL { {{ uri }} personnel:hasPortrait ?p . ?p personnel:portrait_url ?image . }
  OPTIONAL { {{ uri }} personnel:isEmployedBy ?org . ?org rdfs:label ?employer . }
  OPTIONAL { ?sl rdf:type personnel:ServiceLine ; abi:hasMemberPart {{ uri }} ; rdfs:label ?serviceLine . }
  OPTIONAL { {{ uri }} personnel:hasGrade ?g . ?g personnel:grade_value ?grade . }
  OPTIONAL {
    {{ uri }} personnel:hasWorkLocation ?site .
    ?site personnel:office_label ?office .
    OPTIONAL { ?site personnel:country_name ?country . }
  }
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
SELECT ?title ?item ?subtitle ?snippet ?start ?end
WHERE {
  {{ uri }} personnel:hasActOfWorking ?act .
  OPTIONAL { ?act personnel:forOrganization ?item . ?item rdfs:label ?orgLabel . }
  OPTIONAL { ?act personnel:forClient ?client . ?client rdfs:label ?clientLabel . }
  OPTIONAL {
    ?act abi:realizes ?role .
    OPTIONAL { ?role personnel:hasJobPosition ?pos . ?pos personnel:job_title ?jobTitle . }
    OPTIONAL { ?role personnel:hasMission ?mission . ?mission personnel:mission_content ?snippet . }
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
  {{ uri }} personnel:hasActOfStudying ?act .
  OPTIONAL { ?act personnel:forEducationalOrganization ?item . ?item rdfs:label ?subtitle . }
  OPTIONAL { ?act personnel:hasEnrollment ?e . ?e personnel:program_name ?program . }
  OPTIONAL { ?act personnel:hasDegree ?d . ?d rdfs:label ?degree . }
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
  {{ uri }} personnel:hasSkill ?skill .
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
  {{ uri }} personnel:hasLanguageCapability ?cap .
  OPTIONAL { ?cap personnel:language_name ?name . }
  OPTIONAL { ?cap personnel:proficiency_level ?subtitle . }
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
       (CONCAT(STR(COUNT(DISTINCT ?person)), IF(COUNT(DISTINCT ?person) = 1, " person", " people")) AS ?subtitle)
WHERE {
  ?uri rdf:type abi:Organization ;
       rdfs:label ?title .
  OPTIONAL {
    ?act rdf:type personnel:ActOfWorking ; personnel:forOrganization ?uri .
    ?person personnel:hasActOfWorking ?act .
  }
  FILTER(CONTAINS(LCASE(STR(?title)), LCASE("{{ q }}")))
}
GROUP BY ?uri ?title
ORDER BY DESC(COUNT(DISTINCT ?person)) LCASE(STR(?title))
LIMIT {{ limit }}
OFFSET {{ offset }}
""",
    header_query=_PREFIXES
    + """
SELECT ?title (COUNT(DISTINCT ?employee) AS ?people) (COUNT(DISTINCT ?consultant) AS ?consultants)
WHERE {
  {{ uri }} rdfs:label ?title .
  OPTIONAL { ?a personnel:forOrganization {{ uri }} . ?employee personnel:hasActOfWorking ?a . }
  OPTIONAL { ?c personnel:forClient {{ uri }} . ?consultant personnel:hasActOfWorking ?c . }
}
GROUP BY ?title
LIMIT 1
""",
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
  ?act personnel:forOrganization {{ uri }} .
  ?item personnel:hasActOfWorking ?act ; rdfs:label ?title .
  OPTIONAL { ?act abi:realizes ?role . ?role personnel:hasJobPosition ?pos . ?pos personnel:job_title ?jobTitle . }
  OPTIONAL {
    ?act abi:occupiesTemporalRegion ?t .
    OPTIONAL { ?t abi:hasFirstInstant ?fi . ?fi personnel:instant_date ?s . }
    OPTIONAL { ?t abi:hasLastInstant ?li . ?li personnel:instant_date ?e . }
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
  ?act personnel:forClient {{ uri }} .
  ?item personnel:hasActOfWorking ?act ; rdfs:label ?title .
  OPTIONAL { ?act personnel:forOrganization ?org . ?org rdfs:label ?subtitle . }
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
