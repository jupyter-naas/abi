from pydantic import Field, create_model

from abi import logger

from .GenericWorkflow import GenericWorkflow


def templatable_queries():
    from src import services

    results = services.triple_store_service.query("""
        PREFIX intentMapping: <http://ontology.naas.ai/intentMapping/>
        PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
        SELECT ?query ?label ?description ?sparqlTemplate ?hasArgument
        WHERE {
            ?query a intentMapping:TemplatableSparqlQuery ;
                intentMapping:intentDescription ?description ;
                intentMapping:sparqlTemplate ?sparqlTemplate ;
                intentMapping:hasArgument ?hasArgument ;
                rdfs:label ?label .
        }
    """)

    queries = {}

    for result in results:
        query, label, description, sparqlTemplate, hasArgument = result
        queries[query] = {
            "label": label,
            "description": description,
            "sparqlTemplate": sparqlTemplate,
            "hasArgument": [hasArgument]
            if (query not in queries or queries[query].get("hasArgument") is None)
            else queries[query].get("hasArgument") + [hasArgument],
        }

    arguments = {}
    for templatableQuery in queries:
        for argument in queries[templatableQuery].get("hasArgument"):
            q = (
                """
                PREFIX intentMapping: <http://ontology.naas.ai/intentMapping/>
                
                SELECT ?argument ?name ?description ?validationPattern ?validationFormat
                WHERE {
                    BIND(<"""
                + str(argument)
                + """> AS ?argument)
                    ?argument a intentMapping:QueryArgument ;
                        intentMapping:argumentName ?name ;
                        intentMapping:argumentDescription ?description ;
                        intentMapping:validationPattern ?validationPattern ;
                        intentMapping:validationFormat ?validationFormat .
                }
            """
            )
            logger.debug(f"Query: {q}")
            results = services.triple_store_service.query(q)

            for result in results:
                argument, name, description, validationPattern, validationFormat = (
                    result
                )

                arguments[argument] = {
                    "name": name,
                    "description": description,
                    "validationPattern": validationPattern,
                    "validationFormat": validationFormat,
                }
    return queries, arguments


def load_workflows():
    workflows = []

    queries, arguments = templatable_queries()

    # Now for each query, we need to create a Pydantic BaseModel based on the arguments
    for _query in queries:
        query = queries[_query]

        # Arguments Model with validation patterns
        arguments_model = create_model(
            f"{str(query['label']).capitalize()}Arguments",
            **{
                str(arguments[argument]["name"]): (
                    str,
                    Field(
                        ...,
                        description=str(arguments[argument]["description"]),
                        pattern=str(arguments[argument]["validationPattern"]),
                        # You could also add additional metadata from validationFormat if needed
                        example=str(arguments[argument]["validationFormat"]),
                    ),
                )
                for argument in query.get("hasArgument")
            },
        )

        p = GenericWorkflow[arguments_model](
            str(query["label"]),
            str(query["description"]),
            str(query["sparqlTemplate"]),
            arguments_model,
        )
        workflows.append(p)

    return workflows
