"""World Situation Room — an app of the ``intelligence`` bucket.

This is **not** a loadable ABI module. It is discovered as an app of
``naas_abi_marketplace.domains.intelligence`` through the ``manifest.json``
next to this file, which gives it the app id
``naas_abi_marketplace.domains.intelligence:wsr``.

Everything that used to live in an ``ABIModule`` here now belongs to the
parent bucket:

* **Configuration** — ``WSRConfiguration`` in ``domains/intelligence/__init__.py``,
  set under the ``wsr:`` key of the intelligence module's config.
* **Agent** — ``domains/intelligence/agents/WSRAgent.py``, loaded flat with the
  bucket's other agents.

The dashboard under ``apps/dashboard/`` stays a standalone service with its own
``pyproject.toml``, ``Dockerfile`` and ``.env``; see ``README.md``.
"""
