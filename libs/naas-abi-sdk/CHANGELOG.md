# CHANGELOG

<!-- version list -->

## v0.3.0 (2026-11-07)

### Bug Fixes

- A host token names its host, and discovery accepts it from that host only
  ([`f557785`](https://github.com/jupyter-naas/abi/commit/f557785bb242b714fe39d9d724de580aff23e34e))

- Creating a repository never hands over one that exists
  ([`f4fdb93`](https://github.com/jupyter-naas/abi/commit/f4fdb93269d3137c4afc3eab84a8fbcf1595cef1))

- Default manifests grant no admin action; repository ids are plain segments
  ([`c4e8b4f`](https://github.com/jupyter-naas/abi/commit/c4e8b4f72d8583d781adab95bcac902db35477c4))

- Final review round 2
  ([`0eb6cbc`](https://github.com/jupyter-naas/abi/commit/0eb6cbcda98886dc204581e4c91a779407c85f5f))

- Hosts never hold a caller's token; the secret endpoint is an allowlist; no key in logs
  ([`98cefb3`](https://github.com/jupyter-naas/abi/commit/98cefb3be5f00c9b85f90de18d211f0b535abe99))

- Modules on service keys meet the caller checks and kernel catalogs
  ([`872a0d2`](https://github.com/jupyter-naas/abi/commit/872a0d2edd99b1a0dfc2bbae1b772ebd0a747280))

- Platform secrets, fail-closed seals, grants by action and short broker lifetimes
  ([`e5085d0`](https://github.com/jupyter-naas/abi/commit/e5085d09747193155c4b798e4cae5935503b80bf))

- Review round 1 of delegated tokens and API keys
  ([`8fa83a5`](https://github.com/jupyter-naas/abi/commit/8fa83a517556fd85a59ee074efb9a60fa6d5953f))

- The permission scenario end to end in abi dev up
  ([`80146d4`](https://github.com/jupyter-naas/abi/commit/80146d44c8223ac98a9a1c84620276762eafd3ec))

- **core**: Close IAM attachment escalations and a fail-open token scope
  ([`3714748`](https://github.com/jupyter-naas/abi/commit/371474864a149c906b943d6e4446efe9bf775f45))

- **core**: Make check is green: identity_at on the IdentityIAM Protocol, mypy and test guards for
  naas_abi_idp
  ([`c815326`](https://github.com/jupyter-naas/abi/commit/c81532608c17b93d038d0b02b1297b4f45b80912))

- **core**: The call context copy carries the delegation check
  ([`8527c02`](https://github.com/jupyter-naas/abi/commit/8527c024b64d74bfbf624d5d7c4a4029533c47e8))

- **deps**: Install naas-abi-proto and naas-abi-sdk wherever they are imported
  ([`f7685c4`](https://github.com/jupyter-naas/abi/commit/f7685c44230cc7ec34bdbcdbdbb6374d91e4405f))

- **discovery**: Let a rollout change jobs, agents and models
  ([`fdc0f15`](https://github.com/jupyter-naas/abi/commit/fdc0f15eb8ecb6d249864140ca5f9d3a70564505))

- **iam**: Grant only what you hold, review round 1
  ([`77b7bfd`](https://github.com/jupyter-naas/abi/commit/77b7bfda89f2b80d09abe2ea28515864c7266b65))

- **iam**: Keep the permission branch's grant checks where module scopes meet them
  ([`2d98530`](https://github.com/jupyter-naas/abi/commit/2d98530ccb7aa2c2c120f0795428d7d0f5c134b9))

- **iam, core**: Review round 1 of publishers and listing
  ([`8ff2900`](https://github.com/jupyter-naas/abi/commit/8ff29009763ff3cb894ab239972d1b63a35d3b4e))

- **iam, nexus**: Review round 1 of the builder, IAM side
  ([`b1c86ef`](https://github.com/jupyter-naas/abi/commit/b1c86eff29b97e6cc6fd245c3c931d32f2e10696))

- **iam, nexus**: The attach list is IAM's, and whether a policy is known is one read
  ([`951a92d`](https://github.com/jupyter-naas/abi/commit/951a92d770d217f682663461fb57f4814a7662ab))

- **idp**: The admin app administers for the engine's accounts only
  ([`7f2ad73`](https://github.com/jupyter-naas/abi/commit/7f2ad73763800ee498603b0222120651544ab1b1))

- **jobs**: A trigger refused on a retry keeps its run's history and tells waiters
  ([`e84d8a9`](https://github.com/jupyter-naas/abi/commit/e84d8a975f8cf1ef37648cfca9dc28021979d227))

- **jobs**: Keep schedules across restarts and finish runs nothing will retry
  ([`a431fe3`](https://github.com/jupyter-naas/abi/commit/a431fe3cb24a18aee0239eabb081621e3cbe37d5))

- **nats**: End the no-responders retry before the caller's deadline
  ([`32e1099`](https://github.com/jupyter-naas/abi/commit/32e1099ba923fc49e857f5f1957a386bfde8225a))

- **nats**: Retry a transfer open through an engine handover
  ([`47e5e86`](https://github.com/jupyter-naas/abi/commit/47e5e86f2be01785e134a7acb9267b342fc75e69))

- **nexus**: Remote app grants stay narrow, short and out of the logs
  ([`c6064b9`](https://github.com/jupyter-naas/abi/commit/c6064b9721489c157d8f122f6bf37a79f220aceb))

- **nexus**: Remote module apps run sandboxed, under a grant
  ([`2e773d6`](https://github.com/jupyter-naas/abi/commit/2e773d635ba9940604815a14c90812b7adfc16c8))

- **sdk**: Keep the instance id when a discovery lease is lost
  ([`db98a9d`](https://github.com/jupyter-naas/abi/commit/db98a9dd7230a1cdac7c859cac206ce4c0e7bc13))

- **sdk**: Keep triggers for a rollout's new jobs until its host starts
  ([`280068e`](https://github.com/jupyter-naas/abi/commit/280068ee61bf570066d44c3c33d2754b5db0a910))

- **sdk**: Let the deadline bound unstreamed agent runs
  ([`e7428d1`](https://github.com/jupyter-naas/abi/commit/e7428d1cd20f4ba88d0fc0172d76b95782494288))

- **workflows**: A run for a user keeps its bookkeeping the module's own
  ([`2b73462`](https://github.com/jupyter-naas/abi/commit/2b73462fb3fae3eb65b1b061a0525e965c4b5392))

### Build System

- **release**: Release naas-abi-proto and naas-abi-sdk with the other packages
  ([`81b8de1`](https://github.com/jupyter-naas/abi/commit/81b8de17475907d0141f8a81915bf8925b706d45))

### Chores

- Leave the formatting of files this work touches as it was
  ([`f9222f7`](https://github.com/jupyter-naas/abi/commit/f9222f71f465bae2767990c6670218147d7f9079))

### Continuous Integration

- Run every broker suite and fail when nats-server is missing
  ([`31e2049`](https://github.com/jupyter-naas/abi/commit/31e2049b5e950cea4d7c3233edf436b9d22ab92f))

### Documentation

- Caller identity in CallContext (RFC §10 as built, ADR, AGENTS)
  ([`3703ceb`](https://github.com/jupyter-naas/abi/commit/3703cebf44e32d21378eb14eac1adc10fb55d9af))

- IAM service guide, Service Map row, transitional bootstrap ADR
  ([`eb1ce46`](https://github.com/jupyter-naas/abi/commit/eb1ce4612857f4452499d4f27b411682cbb5118c))

- Module scopes, declared catalogs and the upgrade note
  ([`d739301`](https://github.com/jupyter-naas/abi/commit/d73930148c9312a6624717408c80305fce3f0a20))

- Say what things are, not which task built them: stale task numbers and
  ([`c815326`](https://github.com/jupyter-naas/abi/commit/c81532608c17b93d038d0b02b1297b4f45b80912))

### Features

- Discovery and the model registry check the caller's policy
  ([`636b1ac`](https://github.com/jupyter-naas/abi/commit/636b1ac463cde0a23fa06c1a424d2426d91153f3))

- The built-in IdP is served at /idp and read over NATS
  ([`f2f666a`](https://github.com/jupyter-naas/abi/commit/f2f666a6205c96f49b29af7fdb4384ab9fb4f793))

- **cli**: Remote module apps are served through Nexus
  ([`e4b8c0d`](https://github.com/jupyter-naas/abi/commit/e4b8c0d18ca3858c936ddc964fb75602fd69a117))

- **core**: Every kernel call carries a verified CallContext
  ([`c58683b`](https://github.com/jupyter-naas/abi/commit/c58683bfb1e72d4f1c2f34709c33fb62432925ef))

- **core**: IAM over NATS and the SDK, configured and loaded first
  ([`bff3bf6`](https://github.com/jupyter-naas/abi/commit/bff3bf6c0dfc7458cdf6ee671d61f08c3b292a9e))

- **core**: Identity over NATS, in every engine, tested against Zitadel
  ([`33c1bca`](https://github.com/jupyter-naas/abi/commit/33c1bca64dc89807d5a50a8f798ecfbe012376d5))

- **core**: Token exchange, personal and link keys, and revoking a principal's tokens
  ([`d9c698e`](https://github.com/jupyter-naas/abi/commit/d9c698ece1efd46de4464726058a909d0916203e))

- **core, sdk**: Kernel services list their resources, remote modules serve listers
  ([`d1f60fa`](https://github.com/jupyter-naas/abi/commit/d1f60fa78b65fbdcd4e85f9bd33893f65fcc2b3d))

- **core, sdk, cli**: The container of the call in every kernel service
  ([`5f82765`](https://github.com/jupyter-naas/abi/commit/5f82765a103e9c08b1c01fa31d1b1445d28db369))

- **core,sdk**: A delegated token carries the user; the on-behalf-of header is gone
  ([`2826428`](https://github.com/jupyter-naas/abi/commit/282642841efbb4646e7815a45b7b3b462f64a073))

- **engine**: One serving engine per NATS account, shared event and activity storage
  ([`6416192`](https://github.com/jupyter-naas/abi/commit/6416192db46fdcf390928a8cbccb67562b134d5b))

- **iam**: Authorize_declared, the SDK's declared catalogs and require_action
  ([`e967e72`](https://github.com/jupyter-naas/abi/commit/e967e72d025cded4377488de08099319eff47d45))

- **iam**: Grant only what you hold
  ([`5f39192`](https://github.com/jupyter-naas/abi/commit/5f3919264b2788f2f91c04d3b57c01d9af50f060))

- **iam**: Organisation and workspace sets bound users' module scopes and features
  ([`d162b0f`](https://github.com/jupyter-naas/abi/commit/d162b0fe50426c09856b6c76b6df8844902d3724))

- **iam**: Pending grants for invitees and IdP group bindings
  ([`c7cc263`](https://github.com/jupyter-naas/abi/commit/c7cc2630d96ac5e64d430686314f314092cd0879))

- **iam**: Policies and groups owned by an organisation or a workspace
  ([`c575aad`](https://github.com/jupyter-naas/abi/commit/c575aad2effaa1f31bebb55eafdf018558c23d4b))

- **iam**: Sets removed; no built-in role holds a module scope
  ([`84633ff`](https://github.com/jupyter-naas/abi/commit/84633ff9b12598155200da3286b50d89e9fcdbb8))

- **iam**: Sub-policies, a policy narrowed by its parent read live
  ([`ac30519`](https://github.com/jupyter-naas/abi/commit/ac30519d7cdd6ac3d6dfd2fa910155c191f2942d))

- **iam**: Workflow notices and process workflows in the broker grants and manifests
  ([`c7356cf`](https://github.com/jupyter-naas/abi/commit/c7356cf846941dc22a32638fa89c333d0013a18c))

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

- **jobs**: A job or workflow started for a user runs for that user
  ([`7ec5df3`](https://github.com/jupyter-naas/abi/commit/7ec5df33e53c5816effac30cbc9db3d350c423b0))

- **nats**: Discovery and the SDK agent and model hosts answer calls side by side
  ([`079417d`](https://github.com/jupyter-naas/abi/commit/079417d9a6a89510737103bcdebd9607315e0c1d))

- **nats**: Stop the process when its NATS connection closes for good
  ([`0263240`](https://github.com/jupyter-naas/abi/commit/02632400cf9c7413730825735e3172869be6915a))

- **nexus**: A real API keys page; the engine exchanges an IdP token for a session
  ([`e6f7bce`](https://github.com/jupyter-naas/abi/commit/e6f7bce13cff55fcc623fa31c56f32aaa0db4f90))

- **nexus**: List and serve the apps of remote modules
  ([`c781461`](https://github.com/jupyter-naas/abi/commit/c7814613443767e5bfee96d31ccc88a891b2a679))

- **nexus**: Publishers, resource listing, and nothing lists more than the caller may grant
  ([`71020a3`](https://github.com/jupyter-naas/abi/commit/71020a3422f86390ef6fc5528dcf3c2d31127f7e))

- **nexus**: The API takes sessions, keys and coding keys where each belongs; links are IAM grants
  ([`0803aba`](https://github.com/jupyter-naas/abi/commit/0803aba2f1aadb283420940e32b692f1b6c15249))

- **sdk**: App bodies stream between Nexus and the module
  ([`fadf80f`](https://github.com/jupyter-naas/abi/commit/fadf80fcfd8ef5ed0597fb7716d1dcb22f6cd662))

- **sdk**: Cut module rollouts over without dropping in-flight work
  ([`a9559d9`](https://github.com/jupyter-naas/abi/commit/a9559d9239a6fdff8261a16df0e52426c3b31d1f))

- **sdk**: Modules run on service keys, behind the broker's confinement
  ([`b527fe0`](https://github.com/jupyter-naas/abi/commit/b527fe0fea33adcdabebf67e77f2d7e4cfeda7f5))

- **sdk**: Modules serve web apps over NATS
  ([`4bb50ee`](https://github.com/jupyter-naas/abi/commit/4bb50ee890df443a37bc186f13bf85e0485f0bba))

- **triple-store**: A module's ontology is loaded with triple_store:LoadSchema on its source
  ([`821918f`](https://github.com/jupyter-naas/abi/commit/821918f75b3ac1eae5617e48934d9dce35dc512b))

### Performance Improvements

- **agents**: Stop reading the whole registry for every agent poll
  ([`1755a62`](https://github.com/jupyter-naas/abi/commit/1755a623c805b37f59a1ca5d0cbdf8fb8f13e3fb))

### Refactoring

- Review minors for module scopes
  ([`750e738`](https://github.com/jupyter-naas/abi/commit/750e7389e526924896500b673e1dbdead050381c))

- **jobs**: One job identity per host, the broker request takes its call context
  ([`335df04`](https://github.com/jupyter-naas/abi/commit/335df046d7355cf2f372f1986336fffa2b6ea57f))

- **nats**: Size broker messages with one function
  ([`c5f1fe6`](https://github.com/jupyter-naas/abi/commit/c5f1fe6a811c4bffd22a83278fa4acdc4aa15863))

### Testing

- Cover the document and vector store NATS codecs
  ([`73c03ec`](https://github.com/jupyter-naas/abi/commit/73c03ec49418158ffd2c23c1000bf0906c5d6413))


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
