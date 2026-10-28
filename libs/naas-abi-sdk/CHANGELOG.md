# CHANGELOG

<!-- version list -->

## v0.2.0 (2026-10-26)

### Bug Fixes

- Review findings of the durable workflows task
  ([`f2d12d8`](https://github.com/jupyter-naas/abi/commit/f2d12d8a8e61352e4f06eea466a48ac643a24a3c))

- **remote-modules**: Close review findings on processes and ontologies
  ([`b5312b0`](https://github.com/jupyter-naas/abi/commit/b5312b0ea30719c8a1075c499b98f0ed3efe0548))

- **sdk**: Bound a process's deadline, and answer every describe and cancellation
  ([`e42d345`](https://github.com/jupyter-naas/abi/commit/e42d345f74e3b6b8ca8a206cd9a84f256f46c1b4))

- **sdk**: Type the Workflow/Pipeline bridge's class arguments
  ([`83bf949`](https://github.com/jupyter-naas/abi/commit/83bf9494d08fd3a5777dbfae379be5138a81a46f))

- **sdk**: Workflow review fixes
  ([`9e876b1`](https://github.com/jupyter-naas/abi/commit/9e876b168e63af7cc9457b91b3564335cb6df1e1))

- **workflows**: A parent that times out or fails for good cancels its children
  ([`f4e2cfc`](https://github.com/jupyter-naas/abi/commit/f4e2cfcbd02054f88abec4e242e74e4d826b9138))

- **workflows**: One result encoding for engine and SDK classes
  ([`118b159`](https://github.com/jupyter-naas/abi/commit/118b1590f7936312f80b7c550a8769c3e4566ffc))

### Build System

- **sdk**: Add the workflows extra to uv.lock
  ([`7edd21d`](https://github.com/jupyter-naas/abi/commit/7edd21d8399b23951ed69f7eddd32b88984c9c2c))

### Documentation

- Decisions in AGENTS.md instead of the removed ADR tree
  ([`07369f6`](https://github.com/jupyter-naas/abi/commit/07369f6ade0083273ef6101c832e1b58bafb600f))

- **sdk**: Record remote workflows, pipelines and ontologies, and smoke them
  ([`c4816c4`](https://github.com/jupyter-naas/abi/commit/c4816c486390102ed118dffab3c3c97b0144ef6a))

### Features

- **cli**: SDK workflow, pipeline and integration scaffolds in remote modules
  ([`f970c2e`](https://github.com/jupyter-naas/abi/commit/f970c2e9331d6691953d37d4bed8e0ae2048e9e6))

- **sdk**: Build_processes() so an agent built in on_initialized gets workflow and pipeline tools
  ([`01c8d74`](https://github.com/jupyter-naas/abi/commit/01c8d744b6b2c04e96fec8c290755b945233747e))

- **sdk**: Durable workflows on the jobs runtime
  ([`479b06b`](https://github.com/jupyter-naas/abi/commit/479b06b483a909124154e5a563592e8466bc3a80))

- **sdk**: Run remote workflows and pipelines as jobs
  ([`290dc66`](https://github.com/jupyter-naas/abi/commit/290dc66602b1f303c5cd3fc051f04b9572235d29))

- **sdk**: Serve remote workflows and pipelines over NATS
  ([`bed4846`](https://github.com/jupyter-naas/abi/commit/bed48466bfb474023976c8f644cbe7bc2b1d5c59))

- **sdk**: Workflows, pipelines and integrations in remote modules
  ([`e3b6602`](https://github.com/jupyter-naas/abi/commit/e3b6602dc40f191894f2185755b9bcb39c60a50b))

- **triple-store**: Load remote module ontologies into the schema graph
  ([`90b1795`](https://github.com/jupyter-naas/abi/commit/90b179511f642035796cc36a4aea3ef16bcc6466))

### Refactoring

- Commit staged changes for various libs and apps
  ([`3c52466`](https://github.com/jupyter-naas/abi/commit/3c5246681dfe4a341e18c43897439f1e8989e676))

- **workflows**: Core's sync workflows reuse the SDK's declaration
  ([`dcfd468`](https://github.com/jupyter-naas/abi/commit/dcfd4684a3e12ce6fa03c6b75973ae04410d2be7))

### Testing

- **sdk**: Workflow-class tests skip where the workflows extra is missing
  ([`7d9a313`](https://github.com/jupyter-naas/abi/commit/7d9a313bb4833561cf96cb66568f39d5b8bc5648))


## v0.1.1 (2026-10-21)

### Bug Fixes

- **cli**: Keep docs/reference; stop copying into docs/site
  ([#1380](https://github.com/jupyter-naas/abi/pull/1380),
  [`2a96b60`](https://github.com/jupyter-naas/abi/commit/2a96b603a9fde09b9a02b5a29dd154a7be3f19d2))

### Documentation

- Drop Zen naming from docs pointers ([#1380](https://github.com/jupyter-naas/abi/pull/1380),
  [`2a96b60`](https://github.com/jupyter-naas/abi/commit/2a96b603a9fde09b9a02b5a29dd154a7be3f19d2))

- Fix NATS deep link (no .md in docs.naas.ai URL)
  ([#1380](https://github.com/jupyter-naas/abi/pull/1380),
  [`2a96b60`](https://github.com/jupyter-naas/abi/commit/2a96b603a9fde09b9a02b5a29dd154a7be3f19d2))

- Remove narrative docs from ABI; point to docs.naas.ai
  ([#1380](https://github.com/jupyter-naas/abi/pull/1380),
  [`2a96b60`](https://github.com/jupyter-naas/abi/commit/2a96b603a9fde09b9a02b5a29dd154a7be3f19d2))

- Remove narrative docs; point to docs.naas.ai
  ([#1380](https://github.com/jupyter-naas/abi/pull/1380),
  [`2a96b60`](https://github.com/jupyter-naas/abi/commit/2a96b603a9fde09b9a02b5a29dd154a7be3f19d2))

- Retarget package README and CLI links to docs.naas.ai
  ([#1380](https://github.com/jupyter-naas/abi/pull/1380),
  [`2a96b60`](https://github.com/jupyter-naas/abi/commit/2a96b603a9fde09b9a02b5a29dd154a7be3f19d2))


## v0.1.0 (2026-10-20)

- Initial Release
