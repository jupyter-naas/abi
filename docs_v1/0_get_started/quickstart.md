# Quickstart

Create your first module and start building your first AI agent.

## Run the project

Before we proceed, we need to make sure you have finished installing ABI.

To do this, execute the following command in your terminal:

```bash
make
```

This will setup the environment, install the dependencies, initalize your triple store and run the supervisor agent.


## Create Your First Module

```bash
make create-module
```

This process will create a new module in the `src/custom/modules` directory with all the necessary components templates: agents, integrations, ontologies, pipelines and workflows.
It will also register your agent in the Makefile so you can run it directly with the following command:

```bash
make chat-[name]-agent
```

Now, learn how to customize your module by following the [module documentation](../modules/overview.md).

