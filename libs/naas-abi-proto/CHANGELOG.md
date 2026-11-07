# CHANGELOG

<!-- version list -->

## v0.3.0 (2026-11-07)

### Bug Fixes

- A host token names its host, and discovery accepts it from that host only
  ([`f557785`](https://github.com/jupyter-naas/abi/commit/f557785bb242b714fe39d9d724de580aff23e34e))

- Creating a repository never hands over one that exists
  ([`f4fdb93`](https://github.com/jupyter-naas/abi/commit/f4fdb93269d3137c4afc3eab84a8fbcf1595cef1))

- Hosts never hold a caller's token; the secret endpoint is an allowlist; no key in logs
  ([`98cefb3`](https://github.com/jupyter-naas/abi/commit/98cefb3be5f00c9b85f90de18d211f0b535abe99))

- Invitations review round 1: owner invites, shared grants, rollbacks, bindings and sign-in claim
  ([`3f2116c`](https://github.com/jupyter-naas/abi/commit/3f2116ca915296bd8ab4b942b82fb069da66d2f4))

- **iam**: Keep the permission branch's grant checks where module scopes meet them
  ([`2d98530`](https://github.com/jupyter-naas/abi/commit/2d98530ccb7aa2c2c120f0795428d7d0f5c134b9))

- **iam**: No role widens on a stale catalog; old feature policies stay until moved
  ([`ebdefa5`](https://github.com/jupyter-naas/abi/commit/ebdefa5a1463d34d40e74a4d8a6425c31aa5be47))

- **iam, nexus**: Review round 1 of the builder, IAM side
  ([`b1c86ef`](https://github.com/jupyter-naas/abi/commit/b1c86eff29b97e6cc6fd245c3c931d32f2e10696))

- **iam, nexus**: The attach list is IAM's, and whether a policy is known is one read
  ([`951a92d`](https://github.com/jupyter-naas/abi/commit/951a92d770d217f682663461fb57f4814a7662ab))

- **idp**: The admin app administers for the engine's accounts only
  ([`7f2ad73`](https://github.com/jupyter-naas/abi/commit/7f2ad73763800ee498603b0222120651544ab1b1))

### Build System

- **release**: Release naas-abi-proto and naas-abi-sdk with the other packages
  ([`81b8de1`](https://github.com/jupyter-naas/abi/commit/81b8de17475907d0141f8a81915bf8925b706d45))

### Documentation

- Caller identity in CallContext (RFC §10 as built, ADR, AGENTS)
  ([`3703ceb`](https://github.com/jupyter-naas/abi/commit/3703cebf44e32d21378eb14eac1adc10fb55d9af))

### Features

- Discovery and the model registry check the caller's policy
  ([`636b1ac`](https://github.com/jupyter-naas/abi/commit/636b1ac463cde0a23fa06c1a424d2426d91153f3))

- **core**: Engine tokens, service keys, module manifests and broker confinement
  ([`5427041`](https://github.com/jupyter-naas/abi/commit/54270410aee2bcba731e258f8008492060e50140))

- **core**: IAM over NATS and the SDK, configured and loaded first
  ([`bff3bf6`](https://github.com/jupyter-naas/abi/commit/bff3bf6c0dfc7458cdf6ee671d61f08c3b292a9e))

- **core**: Identity over NATS, in every engine, tested against Zitadel
  ([`33c1bca`](https://github.com/jupyter-naas/abi/commit/33c1bca64dc89807d5a50a8f798ecfbe012376d5))

- **core**: Source control and coding environments authorize; bug (b) fixed
  ([`0c57b78`](https://github.com/jupyter-naas/abi/commit/0c57b786e7c8cc47467358a58e59fba5b88c0ccc))

- **core**: Token exchange, personal and link keys, and revoking a principal's tokens
  ([`d9c698e`](https://github.com/jupyter-naas/abi/commit/d9c698ece1efd46de4464726058a909d0916203e))

- **core,sdk**: A delegated token carries the user; the on-behalf-of header is gone
  ([`2826428`](https://github.com/jupyter-naas/abi/commit/282642841efbb4646e7815a45b7b3b462f64a073))

- **iam**: Authorize_declared, the SDK's declared catalogs and require_action
  ([`e967e72`](https://github.com/jupyter-naas/abi/commit/e967e72d025cded4377488de08099319eff47d45))

- **iam**: Catalogs flag what the roles leave out; core generates no feature policy
  ([`5665f0e`](https://github.com/jupyter-naas/abi/commit/5665f0ed164917404d9a0015e132c86c947769b7))

- **iam**: Grant only what you hold
  ([`5f39192`](https://github.com/jupyter-naas/abi/commit/5f3919264b2788f2f91c04d3b57c01d9af50f060))

- **iam**: Module scopes, and catalogs modules declare
  ([`cf8bb87`](https://github.com/jupyter-naas/abi/commit/cf8bb87d9eaa5271b15ef216385454920615e0d8))

- **iam**: Organisation and workspace sets bound users' module scopes and features
  ([`d162b0f`](https://github.com/jupyter-naas/abi/commit/d162b0fe50426c09856b6c76b6df8844902d3724))

- **iam**: Pending grants for invitees and IdP group bindings
  ([`c7cc263`](https://github.com/jupyter-naas/abi/commit/c7cc2630d96ac5e64d430686314f314092cd0879))

- **iam**: Policies and groups owned by an organisation or a workspace
  ([`c575aad`](https://github.com/jupyter-naas/abi/commit/c575aad2effaa1f31bebb55eafdf018558c23d4b))

- **iam**: Resource names are container paths
  ([`bcce809`](https://github.com/jupyter-naas/abi/commit/bcce809bd35b037056e72456b42594d852c2b872))

- **iam**: Sets removed; no built-in role holds a module scope
  ([`84633ff`](https://github.com/jupyter-naas/abi/commit/84633ff9b12598155200da3286b50d89e9fcdbb8))

- **iam**: Sub-policies, a policy narrowed by its parent read live
  ([`ac30519`](https://github.com/jupyter-naas/abi/commit/ac30519d7cdd6ac3d6dfd2fa910155c191f2942d))

- **iam, nexus**: What a sub-policy of a parent may grant
  ([`27e23ee`](https://github.com/jupyter-naas/abi/commit/27e23eecaf4a77302e4f5c4647bcf65f8a423905))

- **iam, sdk, proto**: A principal's groups, and a search for principals
  ([`5669096`](https://github.com/jupyter-naas/abi/commit/566909670c9fe3d4eca2ad94bfd636023f83eb50))

- **iam, sdk, proto**: Catalogs name their publisher, listing as the caller
  ([`12901ca`](https://github.com/jupyter-naas/abi/commit/12901cab9049c6e5203c0f13bb92c10ce9294772))

- **identity**: Change and delete a person at their identity provider
  ([`ce6acad`](https://github.com/jupyter-naas/abi/commit/ce6acadb8d6be20b15a2b7df7bd477c9370be4b3))

- **identity**: The provisioning port, with an adapter per provider setting
  ([`32a29e9`](https://github.com/jupyter-naas/abi/commit/32a29e99aed9cdb942c7be3e32fe20e695c67da9))

- **nats**: Discovery declares and authorizes module apps
  ([`51614e6`](https://github.com/jupyter-naas/abi/commit/51614e668540da621f386a1cc7d166c6c893173e))

- **sdk**: App bodies stream between Nexus and the module
  ([`fadf80f`](https://github.com/jupyter-naas/abi/commit/fadf80fcfd8ef5ed0597fb7716d1dcb22f6cd662))

- **sdk**: Cut module rollouts over without dropping in-flight work
  ([`a9559d9`](https://github.com/jupyter-naas/abi/commit/a9559d9239a6fdff8261a16df0e52426c3b31d1f))


## v0.2.0 (2026-10-26)

### Features

- **discovery**: Declare and authorize remote workflows and pipelines
  ([`c695729`](https://github.com/jupyter-naas/abi/commit/c695729215aa1bc644c4d30bbeff687e796fbb17))

- **proto**: Job kind, schemas and trigger input in discovery descriptors
  ([`a2bd861`](https://github.com/jupyter-naas/abi/commit/a2bd8616501174f8f7fadf42f71e560c88585209))

- **triple-store**: Load remote module ontologies into the schema graph
  ([`90b1795`](https://github.com/jupyter-naas/abi/commit/90b179511f642035796cc36a4aea3ef16bcc6466))


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
