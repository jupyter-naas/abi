from .TemplatableSparqlQuery import load_workflows
from abi import logger

workflows = []
tools = []


def get_workflows():
    return workflows


def get_tools(tool_names: list[str] = []):
    if len(tool_names) == 0:
        return tools
    else:
        return [tool for tool in tools if tool.name in tool_names]


def on_initialized():
    logger.debug("Loading Intent Mapping workflows")
    w = load_workflows()
    workflows.extend(w)
    [tools.extend(workflow.as_tools()) for workflow in w]
    logger.debug(f"Intent Mapping workflows loaded: {len(workflows)}")
    for tool in tools:
        logger.debug(f"Tool: {tool.name}")
