from src.core.templatablesparqlquery.workflows.TemplatableSparqlQuery import load_workflows

workflows: list = []
tools: list = []
loaded = False

def requirements():
    return True


def get_workflows():
    return workflows


def get_tools(tool_names: list[str] = []):
    global loaded
    if not loaded:
        load_tools()
        loaded = True

    if len(tool_names) == 0:
        return tools
    else:
        return [tool for tool in tools if tool.name in tool_names]


def load_tools():
    # logger.debug("Loading Intent Mapping workflows")
    w = load_workflows()
    workflows.extend(w)
    [tools.extend(workflow.as_tools()) for workflow in w]
    # logger.debug(f"Tools from intentmapping loaded: {len(tools)}")
    # tool_names = sorted([tool.name for tool in tools])
    # logger.debug(tool_names)
