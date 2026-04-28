# CHANGELOG

<!-- version list -->

## v1.27.0 (2026-04-28)

### Features

- **nexus**: Allow downloading folders as ZIP archives
  ([`308d257`](https://github.com/jupyter-naas/abi/commit/308d257c94b271c563947fbbfb96009ed30d05eb))


## v1.26.0 (2026-04-28)

### Features

- **nexus**: Expand file previews to office docs and plain-text formats
  ([`8eecbf1`](https://github.com/jupyter-naas/abi/commit/8eecbf1dc7319b4626f79eb25978f562339b8b82))


## v1.25.0 (2026-04-28)

### Bug Fixes

- Agent logos
  ([`e199698`](https://github.com/jupyter-naas/abi/commit/e1996981452eb4ae37759053f608bc246ab4863d))

- Default graph and ontology navigation to network tab
  ([`5eda80f`](https://github.com/jupyter-naas/abi/commit/5eda80f5fee06ec0d194b019bfcaf0d5edf22b19))

- Display tool name only
  ([`cb03c23`](https://github.com/jupyter-naas/abi/commit/cb03c2364da49227754e238fc520a9f66663a8b0))

- Display tool name only
  ([`4e656fe`](https://github.com/jupyter-naas/abi/commit/4e656fea0704178ce09a8fce55f55e997c0999f5))

- Load agents from naas-abi module
  ([`be28c97`](https://github.com/jupyter-naas/abi/commit/be28c978714221138f408dabf34f901354bf25c7))

### Features

- Display logos in agent list
  ([`400613a`](https://github.com/jupyter-naas/abi/commit/400613a5b2b5d35af49e9156e2c35607a8673159))

- Pack graphs by roles
  ([`72b3ab2`](https://github.com/jupyter-naas/abi/commit/72b3ab2752345cebd5f7e9f66407aafdfdd58087))

- **AbiAgent**: Enrich routing intents and prompt context
  ([`184f9d1`](https://github.com/jupyter-naas/abi/commit/184f9d122b53dec563bbb80818226fe70f9ccc42))

- **agents-api**: Cache and persist resolved agent logos
  ([`7293a22`](https://github.com/jupyter-naas/abi/commit/7293a227206bda8d8d7c90b19d064bc87b6cafdb))

- **agents-assets**: Add public agent logos
  ([`01362a6`](https://github.com/jupyter-naas/abi/commit/01362a623641ddac27f361e57b0668878c3ff9d9))

- **agents-store**: Map model_id and normalize intent mappings
  ([`91a5c6d`](https://github.com/jupyter-naas/abi/commit/91a5c6d638b6fe6e3c048dd5f5dd0d1c4293fedd))

- **agents-web**: Add dedicated agent detail editor page
  ([`70ac3da`](https://github.com/jupyter-naas/abi/commit/70ac3dae2ab110cf80ea26d8651a292f67d5ff8d))

- **nexus-chat**: Show live activity line for tools and handoffs
  ([`a5cf9d4`](https://github.com/jupyter-naas/abi/commit/a5cf9d4075dbdab3f6dff161106d2c03dee8ecca))

### Performance Improvements

- **AbiAgent**: Load subagents in parallel via ThreadPoolExecutor
  ([`4230350`](https://github.com/jupyter-naas/abi/commit/423035099eef697f682df8e2d1ccc2a975d9e963))

- **agents-adapter**: Resolve agent class registry in parallel via ThreadPoolExecutor
  ([`9bea0f5`](https://github.com/jupyter-naas/abi/commit/9bea0f5db4af875332fb9f6d3fd6e47f675038ca))

### Refactoring

- Abi agents and models
  ([`4d63040`](https://github.com/jupyter-naas/abi/commit/4d630407f5fc1454bbb9970ea1abd32634421a06))

- Abi agents and models
  ([`afc18ae`](https://github.com/jupyter-naas/abi/commit/afc18ae29b805202fa0027f4812c1a0b349a9bd3))

- View endpoint to hexa
  ([`3d26bdb`](https://github.com/jupyter-naas/abi/commit/3d26bdbed8f46921fb2bbf8bc4cb00753cbb54e2))


## v1.24.1 (2026-04-27)

### Bug Fixes

- **nexus**: Remove duplicate socket field in WebSocketContextType
  ([`477898f`](https://github.com/jupyter-naas/abi/commit/477898fbc8494e4f64c52e2c35f9ee0a8c8893d9))


## v1.24.0 (2026-04-23)

### Bug Fixes

- Resolve ruff import sorting violations in ontology and graph services
  ([`d233cce`](https://github.com/jupyter-naas/abi/commit/d233ccecae7cedbb1af54a9aac4eb85de511f89e))

### Features

- **nexus**: Migrate graph endpoint to hexagonal architecture
  ([`a790d12`](https://github.com/jupyter-naas/abi/commit/a790d1200340f7b78107bc1a3ea2c796b21e7bf6))

- **nexus**: Migrate ontology endpoint to hexagonal architecture
  ([`88f8868`](https://github.com/jupyter-naas/abi/commit/88f88684f750fd4f8401385bfdc4f0c2c20f992b))


## v1.23.0 (2026-04-23)

### Bug Fixes

- **auth**: Persist refresh token and add silent session renewal
  ([`b2d5216`](https://github.com/jupyter-naas/abi/commit/b2d5216068ed728f92e73c5ee395b8bd56b5cef5))

- **chat**: Auto-create conversation on first file upload/ingest
  ([`b9cac75`](https://github.com/jupyter-naas/abi/commit/b9cac757bed7b0cfa36a838615e2b2fb4bc88140))

- **chat**: Strip timezone from datetime before INSERT into TIMESTAMP WITHOUT TIME ZONE
  ([`b5bf8ca`](https://github.com/jupyter-naas/abi/commit/b5bf8ca4999b34c2c840c2835ad6477dab6b0651))

- **ci**: Resolve mypy and bandit failures in check-core
  ([`89712a2`](https://github.com/jupyter-naas/abi/commit/89712a26e633bdb68e10b728fbbb6157a1409ef7))

- **ci**: Resolve ruff linting errors
  ([`eb4b926`](https://github.com/jupyter-naas/abi/commit/eb4b92662d5f2765d93a3cd6f646a0332e69a744))

- **test**: Update _FakeMatch stubs to flat SearchResult shape
  ([`a3461b8`](https://github.com/jupyter-naas/abi/commit/a3461b805e7eebb9169fe2ab7561f00b2bcb5327))

### Features

- **cache**: Multi-tier hot/cold cache with explicit tier targeting
  ([`3d1cf07`](https://github.com/jupyter-naas/abi/commit/3d1cf07f244eb44fe904107633c3ba8cae34191d))

- **cache**: Register CacheService in engine with configurable fs/redis/object_storage backends
  ([`f353ffc`](https://github.com/jupyter-naas/abi/commit/f353ffc7c09a91aef02ec9f4b2c5c5e1fef881a9))

- **chat**: Add drag-and-drop file support on the chat bar
  ([`cf70021`](https://github.com/jupyter-naas/abi/commit/cf70021f3d6e05e671e24385165c694264ab2564))

- **chat**: Add granular ingestion progress, fix worker race condition, and file browser UX
  ([`38b0629`](https://github.com/jupyter-naas/abi/commit/38b06295b75615854a4c649e4724b0cc88c71865))

- **chat**: Add My Drive file ingestion with RAG support
  ([`0d73b77`](https://github.com/jupyter-naas/abi/commit/0d73b77519948181632ecbae49576afc18717c60))

- **chat**: Add XLSX ingestion support via openpyxl
  ([`040720e`](https://github.com/jupyter-naas/abi/commit/040720e2700f25b87edfef458f38742d4034fa06))

- **chat**: Surface RAG source attribution as document pills
  ([`8255595`](https://github.com/jupyter-naas/abi/commit/8255595543a2a2a32692ac512a114e2571a6abb4))

### Performance Improvements

- **agents**: Cache agent class registry process-wide
  ([`b2d5216`](https://github.com/jupyter-naas/abi/commit/b2d5216068ed728f92e73c5ee395b8bd56b5cef5))

- **agents**: Pre-populate agent class registry at API startup
  ([`6a9a395`](https://github.com/jupyter-naas/abi/commit/6a9a39531b2532d59dd6bec96dddbe472e4f1437))


## v1.22.5 (2026-04-23)


## v1.22.4 (2026-04-22)


## v1.22.3 (2026-04-22)


## v1.22.2 (2026-04-22)


## v1.22.1 (2026-04-22)

### Bug Fixes

- Create method to get api key and assert not None
  ([`839f52c`](https://github.com/jupyter-naas/abi/commit/839f52c6139cb21d6f3a4afdeb5d33821a84b6de))

- Improv error handling messages for transcribe
  ([`6bea732`](https://github.com/jupyter-naas/abi/commit/6bea732ff53284986b51c517693d5917aa7736ed))


## v1.22.0 (2026-04-21)

### Bug Fixes

- Preserve voice in chat
  ([`9b0bc7f`](https://github.com/jupyter-naas/abi/commit/9b0bc7fb1794a5c227f39523c13109e629878858))


## v1.21.1 (2026-04-21)

### Bug Fixes

- **ci**: Resolve all PR check failures
  ([`5ba33bb`](https://github.com/jupyter-naas/abi/commit/5ba33bbf83483126546daef8815be32f119a45a3))


## v1.21.0 (2026-04-16)


## v1.20.0 (2026-04-16)

### Features

- **nexus**: Enforce workspace feature access by role
  ([`af14f8f`](https://github.com/jupyter-naas/abi/commit/af14f8fe754dc478bbb9ee8b987ecf2fcd0a0697))


## v1.19.4 (2026-04-16)

### Bug Fixes

- Add a CTA to signin after magic link to avoid mail bots authenticating
  ([`ca51e6d`](https://github.com/jupyter-naas/abi/commit/ca51e6ddd7b19ac726ed9ba911421311aa9b916e))


## v1.19.3 (2026-04-16)

### Bug Fixes

- Keep up to 5 magic links active at the same time
  ([`712cc0e`](https://github.com/jupyter-naas/abi/commit/712cc0e464894602b776265e45b6da82f9ca4679))


## v1.19.2 (2026-04-15)

### Bug Fixes

- Trigger build
  ([`e7e9fc3`](https://github.com/jupyter-naas/abi/commit/e7e9fc33ac3e645bb1969d8fd8323b16aac9c7c9))


## v1.19.1 (2026-04-15)

### Bug Fixes

- Working on file upload and fixing build
  ([`541fe08`](https://github.com/jupyter-naas/abi/commit/541fe086637d0f12b3384f14f3b4b9f3e4f1686a))


## v1.19.0 (2026-04-15)

### Bug Fixes

- CodingAgent test
  ([`030f1f9`](https://github.com/jupyter-naas/abi/commit/030f1f9128928ca6dbaf1eb74533d96a669d3326))

### Features

- Working on adding opencode agent
  ([`3f515d4`](https://github.com/jupyter-naas/abi/commit/3f515d48275f55c8ce8844942c4cdc4912698446))


## v1.18.0 (2026-04-15)

### Features

- Make the email customizable
  ([`9860f84`](https://github.com/jupyter-naas/abi/commit/9860f84186f8b411b2869f89d6197408a9d5352b))

- Working on magic link system
  ([`1d036ef`](https://github.com/jupyter-naas/abi/commit/1d036efbdbb05ddaf3baf7be9ef23a7373b20159))

### Refactoring

- Ontologies classes folder renamed (ontopy)
  ([`0050ee8`](https://github.com/jupyter-naas/abi/commit/0050ee878b837bd75fdce8ad5d6c929992852bfe))


## v1.17.1 (2026-04-14)

### Bug Fixes

- Bump versions
  ([`9096426`](https://github.com/jupyter-naas/abi/commit/90964266834d48b55770bccd536f26536bde9aec))

- **nexus**: Files loading race condition
  ([`86b82ee`](https://github.com/jupyter-naas/abi/commit/86b82ee10959b356dd0f812353ea5481066f41f0))


## v1.17.0 (2026-04-07)

### Bug Fixes

- Add logo to agent + rm cache
  ([`26d5f28`](https://github.com/jupyter-naas/abi/commit/26d5f28b1ef317409f946bf76c9a7664113ef23a))

- All ontologies not displayed in ontology section
  ([`2bccf8e`](https://github.com/jupyter-naas/abi/commit/2bccf8e728ebe249da33ab9e7c72c4f60c8004f1))

- Comment query
  ([`5554de4`](https://github.com/jupyter-naas/abi/commit/5554de43c1ede1160899cba5df1e9500eedb190d))

- Display class and object prop labels
  ([`7266403`](https://github.com/jupyter-naas/abi/commit/7266403989bc5eee0c8e27861f9ed529fd4913c6))

- Display ontology hower and active bar
  ([`c0d2953`](https://github.com/jupyter-naas/abi/commit/c0d2953a5cbd1bb171ea627f47409a3a34c30fb6))

- Load ontologies
  ([`8f17414`](https://github.com/jupyter-naas/abi/commit/8f1741414030f130f3f15888386a35f12d065305))

- Ontology display overview
  ([`6fb4cae`](https://github.com/jupyter-naas/abi/commit/6fb4caeb77ef6150a6d958980f1883e3482744d2))

- Ontology graph loading errors
  ([`a9c9e3a`](https://github.com/jupyter-naas/abi/commit/a9c9e3a69640e8d6ad9ad5b3fead1e60ccee5a9e))

- Ontology imports error
  ([`c0747c4`](https://github.com/jupyter-naas/abi/commit/c0747c41727ff31627a6c51daa5dff014f8ebf2d))

- Remove obj prop role
  ([`2442820`](https://github.com/jupyter-naas/abi/commit/2442820379848180756c0da12ecd2c5ae28322f5))

- Rm ontology triples in templatable sparql query tool
  ([`379e097`](https://github.com/jupyter-naas/abi/commit/379e09717933a2b6d587ffbddd1b9950b92d4cfa))

- Ruff errors
  ([`cfd07e1`](https://github.com/jupyter-naas/abi/commit/cfd07e12d5c1b3cbd51685456eb8088c7fa13701))

- Select classes or object properties
  ([`359aa06`](https://github.com/jupyter-naas/abi/commit/359aa06f2111e42a494aec6748ead50036078dc6))

### Features

- Add agent role to kg + ontology
  ([`17c2fad`](https://github.com/jupyter-naas/abi/commit/17c2fadc1ba7ee79d600d38058729c9ee968d511))

- Display logo url
  ([`9f58112`](https://github.com/jupyter-naas/abi/commit/9f58112045e46471ca9c79a2277cbe47d914967c))


## v1.16.3 (2026-04-07)

### Bug Fixes

- Add static method in agents + update pipeline
  ([`5a8aafc`](https://github.com/jupyter-naas/abi/commit/5a8aafcb84d51182e283ea251cb2aba98de0c0de))


## v1.16.2 (2026-04-03)

### Bug Fixes

- Remove unused import in NexusPlatformPipeline.py
  ([`f829279`](https://github.com/jupyter-naas/abi/commit/f829279bfe4e0ea7a91bd01692332b95c1d7e91d))


## v1.16.1 (2026-04-03)

### Bug Fixes

- Remove graph saving logic from NexusPlatformPipeline
  ([`193768e`](https://github.com/jupyter-naas/abi/commit/193768ebe2d999cc836df051f96aa90e8dc87f74))


## v1.16.0 (2026-04-02)

### Bug Fixes

- Nexus pipeline
  ([`85aedc5`](https://github.com/jupyter-naas/abi/commit/85aedc5eb8ca6bb1e6d88da4d9c78b36788a4065))


## v1.15.0 (2026-04-02)

### Bug Fixes

- Add agent tools and intents to ontologies
  ([`46a9410`](https://github.com/jupyter-naas/abi/commit/46a9410ac20e4b4f0c6edc45bb5f0bc9d620d5ce))

- Add description to view and graph + improve graph clear and delete
  ([`25cabc6`](https://github.com/jupyter-naas/abi/commit/25cabc6589f37c0e3e89c10353933e3465f4ef1b))

- Add features and roles to ontology + generate py file
  ([`e932509`](https://github.com/jupyter-naas/abi/commit/e9325090f1b44635f924030e97968c62dc72620f))

- Agent tools & intents in pipeline
  ([`863f200`](https://github.com/jupyter-naas/abi/commit/863f200c2606e1fe794ed3d4c91c670c872c82d0))

- Auto seed demo data False
  ([`ef690ed`](https://github.com/jupyter-naas/abi/commit/ef690ed7a0152911a43745f69438df32b000b89d))

- Comment init view
  ([`4f9724a`](https://github.com/jupyter-naas/abi/commit/4f9724a49e3d4d4964ddf54455df623caa129b3d))

- Create views
  ([`e1b6f4b`](https://github.com/jupyter-naas/abi/commit/e1b6f4b4072ef2c68b70b0d571ae61836aafeb49))

- Error make check
  ([`028b516`](https://github.com/jupyter-naas/abi/commit/028b516808c30931db03afbfdbe6dd0b48a6fb11))

- Exclude turtle files from sandbox folders
  ([`b62ee3d`](https://github.com/jupyter-naas/abi/commit/b62ee3d6eb35eef25eb9b73ebfc2171fa59e07f5))

- Force update nexus graph
  ([`2b64dfa`](https://github.com/jupyter-naas/abi/commit/2b64dfa4f7ee132a635198db1240d438ff59dbae))

- Graph & view order + font
  ([`a8b2af9`](https://github.com/jupyter-naas/abi/commit/a8b2af9dcf53d8f09c6317a8670d108b3be42783))

- Hide actions clear / delete for nexus and schema graph
  ([`1c8ed61`](https://github.com/jupyter-naas/abi/commit/1c8ed61fd4310873facbfc8923f1204bcc3baf9c))

- Kg graph builder agent
  ([`38b3687`](https://github.com/jupyter-naas/abi/commit/38b3687ba274a6321fc57b3ac1a03088803d88c5))

- List graphs in nexus
  ([`e474464`](https://github.com/jupyter-naas/abi/commit/e47446488c2ffe38d23ae4e9891bea18a1ec7ef0))

- List ontologies
  ([`2d29b93`](https://github.com/jupyter-naas/abi/commit/2d29b937296ac46159bf356525db807b0b725e6e))

- Onto2py infite loop on nexus
  ([`886577d`](https://github.com/jupyter-naas/abi/commit/886577dd29700f4a350c40b1e59bab97f4a4aef6))

- Overview + loading time
  ([`b6024c3`](https://github.com/jupyter-naas/abi/commit/b6024c372c4a280adfddf64b021b941f3e6629f3))

- Remove blank nodes
  ([`1cd035a`](https://github.com/jupyter-naas/abi/commit/1cd035a3803cf573365ddf492ef5ce650f041dfd))

- Remove view
  ([`1e05ac3`](https://github.com/jupyter-naas/abi/commit/1e05ac36339be7cac02413adf312a5219e3f4201))

- Renaming endpoint view
  ([`21d4b54`](https://github.com/jupyter-naas/abi/commit/21d4b5464b671e320113c72ccec9c5d7870190b6))

- Tipo
  ([`a49ab9b`](https://github.com/jupyter-naas/abi/commit/a49ab9bd244f687b2b16417c35ea09485775807c))

- Update datasource ontology
  ([`abc4a06`](https://github.com/jupyter-naas/abi/commit/abc4a06047eb189fffc49d44e60b05a6392f33d0))

### Features

- Add agent data properties
  ([`41d8bd5`](https://github.com/jupyter-naas/abi/commit/41d8bd52fd80ae5f729628004185a14511de54b2))

- Add intents and tools to class init
  ([`1b90239`](https://github.com/jupyter-naas/abi/commit/1b9023923b49a8a2bc451480e0cc7d34617327c6))

- Add user as creator
  ([`0351d3d`](https://github.com/jupyter-naas/abi/commit/0351d3df0fc76b20e133e742c81f76d55f1aab23))

- Bind namespace
  ([`03c810c`](https://github.com/jupyter-naas/abi/commit/03c810cf35f4e6e20123dac09418dd18e38dfaea))

- Create views api route
  ([`3100292`](https://github.com/jupyter-naas/abi/commit/3100292cfc6631cfcb84a828cded9ae05147410c))

- Init nexus pipeline & remove legacy
  ([`b968172`](https://github.com/jupyter-naas/abi/commit/b968172bbd5da59e5bf6969ecff392a478c72721))

- Init nexus platform ontologies + refactor structure + rm legacy
  ([`76d571e`](https://github.com/jupyter-naas/abi/commit/76d571eb6c5d4ff3c267b42f078c2a1fd929797d))

- Init nexus with pipeline and create onto2py files
  ([`04cc5a0`](https://github.com/jupyter-naas/abi/commit/04cc5a0140c7952188231b5e45bc2e6db8004031))

- Init views in pipeline nexus
  ([`e060371`](https://github.com/jupyter-naas/abi/commit/e0603716c54632735bb23d6ecbbc9f1118bf0617))

- Load pipeline nexus platform in init
  ([`bec53e0`](https://github.com/jupyter-naas/abi/commit/bec53e04aaf2a6d1a8636ed7a59f960720ba6389))

- Use pipeline in init
  ([`713fe27`](https://github.com/jupyter-naas/abi/commit/713fe2796122ecbb2c413cff184926a619a6c6d8))

### Refactoring

- Graph and view nexus api endpoint & pages
  ([`bc104ac`](https://github.com/jupyter-naas/abi/commit/bc104accec4bd3a517270d461ca0d47b623c4282))

- Nexus platform pipeline
  ([`2d9be72`](https://github.com/jupyter-naas/abi/commit/2d9be72a952c6fb194b9e3f8e525110f4b85d0be))

- Remove individual pipeline
  ([`468b46f`](https://github.com/jupyter-naas/abi/commit/468b46f75684298d7b3ea55f253a7385091b6de2))


## v1.14.0 (2026-04-02)

### Chores

- Update .gitignore, enhance security checks in Makefile, and refine Python version setup in CI
  workflow
  ([`fbb7073`](https://github.com/jupyter-naas/abi/commit/fbb7073adf2ec04d71b013422122ae2321d96346))

### Features

- **auth**: Add avatar removal endpoint and update avatar handling
  ([`506fa32`](https://github.com/jupyter-naas/abi/commit/506fa3208e540ea3bb22a877a0b5ed6f9a5f8200))

- **auth**: Refactor avatar handling to use object storage and add avatar retrieval endpoint
  ([`0ab8842`](https://github.com/jupyter-naas/abi/commit/0ab884234f7a9deadcd37d7ef99085953a4ad624))

### Refactoring

- **auth**: Clean up import statements and enhance error handling in avatar retrieval
  ([`d414e84`](https://github.com/jupyter-naas/abi/commit/d414e84b11c45e3af9c94e5f98b3aab14066526b))

- **auth**: Streamline import statements in FastAPI primary adapter
  ([`f0ebacb`](https://github.com/jupyter-naas/abi/commit/f0ebacb6427b8d035147751b2bdd250804431a20))


## v1.13.0 (2026-03-30)

### Bug Fixes

- Make check
  ([`04f1524`](https://github.com/jupyter-naas/abi/commit/04f1524a0286e004ad9d37db01441d240dbae3d5))

### Features

- Rework remaining endpoints
  ([`988f8a2`](https://github.com/jupyter-naas/abi/commit/988f8a239c1616101fa20d50d86779ba7090ef37))

- Update initialization of the naas-abi module
  ([`b53dff1`](https://github.com/jupyter-naas/abi/commit/b53dff10302ed169354ffc28f67fbab199609aaa))


## v1.12.1 (2026-03-19)

### Bug Fixes

- AppCard null pointer
  ([`a964d71`](https://github.com/jupyter-naas/abi/commit/a964d7134e3adf8ead4a9b02e0360afd4ca546d9))

- Check core
  ([`3362916`](https://github.com/jupyter-naas/abi/commit/336291624113803242f5a059d950f6cdae2771d2))


## v1.12.0 (2026-03-17)

### Bug Fixes

- Apps and files section nexus ui
  ([`1d1072f`](https://github.com/jupyter-naas/abi/commit/1d1072f05f56e27914b2784bfc78381b17038695))

### Features

- Add viewers to files
  ([`79e9068`](https://github.com/jupyter-naas/abi/commit/79e906835240e64170aca034a8a0bbeeb82a4bdc))


## v1.11.0 (2026-03-05)

### Bug Fixes

- Dialog box chat
  ([`b8d5f64`](https://github.com/jupyter-naas/abi/commit/b8d5f644474f263ee79071fe6c30c902aadaedaf))

- Display class name in nexus
  ([`32d8611`](https://github.com/jupyter-naas/abi/commit/32d8611cf0ed12692f8480965dbdbb44f64c1af9))

- Display export above corner tab
  ([`d6052bd`](https://github.com/jupyter-naas/abi/commit/d6052bd409748fac4370b2bc0aaa45f70d01872c))

- Import with example not working
  ([`5c24ec9`](https://github.com/jupyter-naas/abi/commit/5c24ec921b7f015fde9b5c0dba8d2134d80cd67f))

- Improve display of module path
  ([`698c103`](https://github.com/jupyter-naas/abi/commit/698c10317fd8cb3c8a939fd3801ca0b20648bb60))

- Improve href display in chat interface
  ([`56b9c1b`](https://github.com/jupyter-naas/abi/commit/56b9c1b68d62f45e8d8cabe6d79f48fe074b30da))

- Overview data not display + improving create class & object prop
  ([`7d48660`](https://github.com/jupyter-naas/abi/commit/7d486605a65fc47aef5def98ab331b0df8f19a92))

- Rename agents
  ([`73090b9`](https://github.com/jupyter-naas/abi/commit/73090b93c5b1cbb38967fd79af49877f36714a77))

- Tenant display in all sections
  ([`83df650`](https://github.com/jupyter-naas/abi/commit/83df650aacdc3f0dc3ebc47ce159885d989d4f76))

- Type error adapater pg
  ([`e56185a`](https://github.com/jupyter-naas/abi/commit/e56185acc67d119ce407938d391ca093191d4cca))

### Features

- Add system prompt and intents to agent
  ([`039894b`](https://github.com/jupyter-naas/abi/commit/039894b4f495380f9513da6f47a6bf5cbc0e9829))

### Refactoring

- Redirect to agent settings ws on click
  ([`18010f0`](https://github.com/jupyter-naas/abi/commit/18010f05b5f065093be8f70fd4136ead4bdad7c4))

- Update abi with new method
  ([`22a5e00`](https://github.com/jupyter-naas/abi/commit/22a5e001d66d7c5003faaa760d81eb095d73bf23))


## v1.10.0 (2026-03-05)

### Features

- Working on centralizing COES
  ([`5de2a36`](https://github.com/jupyter-naas/abi/commit/5de2a369f0b5908c2fb92f731708da8dc2cfe8bf))

- Working on centralizing CORS usage
  ([`08caa0d`](https://github.com/jupyter-naas/abi/commit/08caa0d2896f03a0c88e25d38ed0f2a076ec73ef))


## v1.9.7 (2026-03-04)

### Bug Fixes

- Make favicon & title persistant
  ([`6602223`](https://github.com/jupyter-naas/abi/commit/66022239cc255ce4bc525d31bd3f9e230dc8d2b2))


## v1.9.6 (2026-03-03)


## v1.9.5 (2026-03-03)

### Bug Fixes

- Exclude agent with no name
  ([`641d7bd`](https://github.com/jupyter-naas/abi/commit/641d7bd7e9ff0acf21a716ff05830fa82d62307b))


## v1.9.4 (2026-03-03)

### Bug Fixes

- Condition to exclude agent.name None
  ([`e889924`](https://github.com/jupyter-naas/abi/commit/e889924299a26ec40a912ff47e8d7b9b9893213d))

- Display logo url of agent in chat interface
  ([`d7a74d9`](https://github.com/jupyter-naas/abi/commit/d7a74d9eaf36e799522bc389d7c9881bd481efdd))

- File lint
  ([`53fe441`](https://github.com/jupyter-naas/abi/commit/53fe4419cf9087ac09375a421d93f80db0dd5c55))

- Get password from secret or add it
  ([`540c7fc`](https://github.com/jupyter-naas/abi/commit/540c7fc39f8ab4fa3a6635915fbfa3257dad0e54))

- Remove icon settings
  ([`a8a76fe`](https://github.com/jupyter-naas/abi/commit/a8a76fe990edd1c4030ea63d6f58ac75fa87e2b1))

### Refactoring

- Display first 2 rows of agent description
  ([`549622c`](https://github.com/jupyter-naas/abi/commit/549622cd94fda66a8b9a91e31995460222d46bf2))


## v1.9.3 (2026-03-02)

### Bug Fixes

- Type 'null' is not assignable to type 'string | number | boolean'.
  ([`83e1a10`](https://github.com/jupyter-naas/abi/commit/83e1a10cfe64bd2de72d0abf80331f0f3b3cfc48))


## v1.9.2 (2026-03-02)


## v1.9.1 (2026-03-02)

### Bug Fixes

- Error build nexus web
  ([`2f9bff2`](https://github.com/jupyter-naas/abi/commit/2f9bff2962a0510e3e3f05fdd63dc6c2cc319e40))


## v1.9.0 (2026-03-02)


## v1.8.2 (2026-03-02)

### Bug Fixes

- Add abi agents to nexus
  ([`dee9936`](https://github.com/jupyter-naas/abi/commit/dee99363e27f5f36935dd23ffb9167dd1f6a25e1))

- Add classname
  ([`0423f88`](https://github.com/jupyter-naas/abi/commit/0423f8809b4bdf3bd60e235e050ac331e19b17f6))

- Code cleaning
  ([`2d2783f`](https://github.com/jupyter-naas/abi/commit/2d2783f8ffd9464985f88489ab3deb771e0f70d8))

- Init hexa archi agents
  ([`ad5a997`](https://github.com/jupyter-naas/abi/commit/ad5a997bc51bd9ed8b2b5092521aa6ddf0a6c92d))

- Mypy errors
  ([`1f53767`](https://github.com/jupyter-naas/abi/commit/1f53767e45700dc6dd9c4c256d79c4589de84614))

- Ollama exception thrown
  ([`9cbb53a`](https://github.com/jupyter-naas/abi/commit/9cbb53a5ea42badc20fbd44cdbaadcc7196daace))

- Remove ollama error from front
  ([`b7b19a9`](https://github.com/jupyter-naas/abi/commit/b7b19a92ae1b42512a2a50b3287b1aadd2e54c9e))

- Rm seeding default agents
  ([`d00665a`](https://github.com/jupyter-naas/abi/commit/d00665af79d4b52a1fa510d2a7fdddbf6aff4368))

- Save agents to db
  ([`2185ae7`](https://github.com/jupyter-naas/abi/commit/2185ae73ebd9ce8ae52bab19fc4511f1d5ca3efa))


## v1.8.1 (2026-02-19)

### Bug Fixes

- Does not make abi load every agent
  ([`ec600b1`](https://github.com/jupyter-naas/abi/commit/ec600b1c85bb3e2b29c3959291dd8eaa1a20109f))


## v1.8.0 (2026-02-19)

### Bug Fixes

- Do not update already existing users
  ([`8754e4b`](https://github.com/jupyter-naas/abi/commit/8754e4b32324ecbaec35d7a0cd30bab13235c101))

- Make checks
  ([`b789da0`](https://github.com/jupyter-naas/abi/commit/b789da0cf1153e81f812fd94aa08abad00f33bf5))

### Features

- **nexus**: Make tenant/org branding and provisioning fully config-driven
  ([`9ce64e5`](https://github.com/jupyter-naas/abi/commit/9ce64e59dc208af2cca659f71f99954b5d1626a8))


## v1.7.14 (2026-02-19)


## v1.7.13 (2026-02-18)

### Bug Fixes

- Nexus web build and service portal links for local dev
  ([`a41432e`](https://github.com/jupyter-naas/abi/commit/a41432e81cfa57a4d2b3af481ba61d5c8fa9297a))


## v1.7.12 (2026-02-18)

### Bug Fixes

- Working on multi env management
  ([`482e67c`](https://github.com/jupyter-naas/abi/commit/482e67c01a4446bbac7fbf9d29948d91851707f4))


## v1.7.11 (2026-02-17)


## v1.7.10 (2026-02-17)

### Bug Fixes

- **nexus**: File manager api url
  ([`09b3fde`](https://github.com/jupyter-naas/abi/commit/09b3fdecae31770a8620284c052b953c1810a7d4))


## v1.7.9 (2026-02-17)


## v1.7.8 (2026-02-17)


## v1.7.7 (2026-02-17)


## v1.7.6 (2026-02-17)


## v1.7.5 (2026-02-17)

### Bug Fixes

- Add missing data in naas_abi release
  ([`4aa9316`](https://github.com/jupyter-naas/abi/commit/4aa9316facc963b4ef4f1653f41b594ea7ae5479))


## v1.7.4 (2026-02-17)


## v1.7.3 (2026-02-17)

### Bug Fixes

- Install nexus-api deps from naas_abi pyproject directly
  ([`a0a5734`](https://github.com/jupyter-naas/abi/commit/a0a57344e2d34adae689b52695b1f586c09b0ab3))


## v1.7.2 (2026-02-17)

### Bug Fixes

- Build nexus for arm64
  ([`859a31b`](https://github.com/jupyter-naas/abi/commit/859a31b68d121bbf5a1370d8daa1661db47831a3))


## v1.7.1 (2026-02-16)


## v1.7.0 (2026-02-16)

### Features

- Trigger release
  ([`cf5dfe9`](https://github.com/jupyter-naas/abi/commit/cf5dfe9691af94ff1d791de0bd0d6a53cb877a32))


## v1.6.1 (2026-02-16)

### Bug Fixes

- Make check-core
  ([`5fcd0cd`](https://github.com/jupyter-naas/abi/commit/5fcd0cd53fb3f02ab12e6f9e65613afc65a7ffbc))


## v1.6.0 (2026-02-16)

### Features

- Working on nexus container release to ghcr
  ([`7f6f441`](https://github.com/jupyter-naas/abi/commit/7f6f441f07c409337e4082ea721a7b71080b49a8))


## v1.5.2 (2026-02-16)

### Bug Fixes

- Remaning issues
  ([`e9480ea`](https://github.com/jupyter-naas/abi/commit/e9480ea53bb33b2358e73dc9fead3915738bc2b8))


## v1.5.1 (2026-02-16)

### Bug Fixes

- **deps**: Move greenlet to nexus-api package
  ([`0a381ae`](https://github.com/jupyter-naas/abi/commit/0a381ae7f92ad326afe18cae21aeceb544c1a597))

- **infra**: Rollback unstable weekend runtime wiring
  ([`aac4a33`](https://github.com/jupyter-naas/abi/commit/aac4a33f2309ebff4a5889f72e45d13192955dd4))


## v1.5.0 (2026-02-13)

### Bug Fixes

- Improve favicon display across browsers
  ([`a26d1aa`](https://github.com/jupyter-naas/abi/commit/a26d1aa674494496045e145604c88535472865dd))

- **infra**: Resolve CORS/500 errors and optimize Docker startup
  ([`661f2cd`](https://github.com/jupyter-naas/abi/commit/661f2cde9390eb34c914e856644b1355d6b4907f))

### Features

- Rename to ABI NEXUS in browser tab
  ([`a8725a6`](https://github.com/jupyter-naas/abi/commit/a8725a6dc1f08879face965fcbe7c7a6487d1b71))


## v1.4.1 (2026-02-13)

### Bug Fixes

- AI Pane SupervisorAgent duplicate streaming and defaults
  ([`f571323`](https://github.com/jupyter-naas/abi/commit/f5713236933003a4e8ace09e58cca4542b355504))


## v1.4.0 (2026-02-12)

### Bug Fixes

- Add header to chat page for settings access
  ([`0cc3604`](https://github.com/jupyter-naas/abi/commit/0cc360414716726366e87f57da18a7e77b334179))

- Working on new project setup
  ([`cd2a5cc`](https://github.com/jupyter-naas/abi/commit/cd2a5ccb156fe540759561e6eeb91abdeb1d4924))

### Features

- Working on wiring nexus to abi
  ([`db01f8b`](https://github.com/jupyter-naas/abi/commit/db01f8b624870b47d1be9a331546ad5313a4204a))


## v1.3.0 (2026-02-11)

### Features

- Migrate assets from root to nexus app
  ([`acea3c8`](https://github.com/jupyter-naas/abi/commit/acea3c88affcbeaf636b953ed04cdfb8e450117d))


## v1.2.0 (2026-02-11)

### Features

- Integrate nexus app into abi monorepo
  ([`f3699f0`](https://github.com/jupyter-naas/abi/commit/f3699f0b84fddd12b0f69d202779ab48ebf16e82))


## v1.1.1 (2026-02-10)

### Bug Fixes

- Get module instances from current module
  ([`a5f4bc3`](https://github.com/jupyter-naas/abi/commit/a5f4bc3376c8f926c4e4959aee7b7dbb3012ba14))


## v1.1.0 (2026-02-09)

### Features

- Working on addint BusService, KeyValueService and reworking Dagster orchestration
  ([`bc448a6`](https://github.com/jupyter-naas/abi/commit/bc448a6a22c9f1788bb204e0671e6efb0c1bb774))


## v1.0.15 (2026-02-02)

### Bug Fixes

- How ABI Agent loads templatable sparql query
  ([`fa80a8c`](https://github.com/jupyter-naas/abi/commit/fa80a8c83f19e485b6d01abbb0573f58e214f517))


## v1.0.14 (2026-01-26)

### Bug Fixes

- CICD checks
  ([`1cc9a0d`](https://github.com/jupyter-naas/abi/commit/1cc9a0d8aa9e5b89c06269f11b8437d3a60d2c23))


## v1.0.13 (2026-01-08)

### Bug Fixes

- Tipo license
  ([`f639213`](https://github.com/jupyter-naas/abi/commit/f639213b6c680d211c9618737842f01b51a65f8d))

- Tipo license
  ([`0269100`](https://github.com/jupyter-naas/abi/commit/0269100ca7d2d338d1f68be0717be6e981cc8eac))


## v1.0.12 (2026-01-08)

### Bug Fixes

- Add project urls in pyproject.toml
  ([`c155efa`](https://github.com/jupyter-naas/abi/commit/c155efa2a794b44312eb90ae19ab1c0da402d3ef))

### Documentation

- Add README.md to naas-abi
  ([`18a5283`](https://github.com/jupyter-naas/abi/commit/18a52833309839e6b0fa90f130cbfb18c174f9d3))


## v1.0.11 (2026-01-08)

### Bug Fixes

- Exclude agents from name
  ([`524944e`](https://github.com/jupyter-naas/abi/commit/524944ead7ebb3dfb6db70ac5c1978a5f6c648ad))

### Refactoring

- Add applications modules as soft
  ([`afe93a4`](https://github.com/jupyter-naas/abi/commit/afe93a42fb1a603f48f331ff74181f45c2941d07))

- Add support and github module to abi init as soft
  ([`1f283db`](https://github.com/jupyter-naas/abi/commit/1f283db8ed540a7681a64d98c28c33c9920ad6ff))


## v1.0.10 (2026-01-03)

### Bug Fixes

- Add agents from dependency modules
  ([`ecfb4f3`](https://github.com/jupyter-naas/abi/commit/ecfb4f34a79e66bba18728c589a3108dd859bc5d))


## v1.0.9 (2026-01-02)

### Bug Fixes

- Enable templatables sparql query
  ([`173eaca`](https://github.com/jupyter-naas/abi/commit/173eaca02526b3fe0f9fff92bd27681bf9efa8fa))

- Errors mypy naas-abi
  ([`a269c0a`](https://github.com/jupyter-naas/abi/commit/a269c0a72430cb029df96cb61daaaa017cfadc1a))

- Move export graph workflow to naas module
  ([`8537e0b`](https://github.com/jupyter-naas/abi/commit/8537e0b75ed9a606c31f15473946e844f1c076e5))

- Mypy
  ([`1dda079`](https://github.com/jupyter-naas/abi/commit/1dda0799adae95f8eabda29e152054b48e4b570f))

- Pyproject.toml
  ([`c8b9c43`](https://github.com/jupyter-naas/abi/commit/c8b9c437949040ae8b07224023346fd3e2e10bac))

- Remove terminal agent not used in naas-abi but core
  ([`1f69255`](https://github.com/jupyter-naas/abi/commit/1f692557d8e07fc5073cc6256a23aac4e10eebba))

- Templatable sparql query
  ([`bc73926`](https://github.com/jupyter-naas/abi/commit/bc73926a2dca407da84ce674446d02e3e4285ba7))

### Refactoring

- Move workflows ontology yaml to naas module
  ([`b4e8e9f`](https://github.com/jupyter-naas/abi/commit/b4e8e9fd738a338c462c9df2525e043cfdf5095d))


## v1.0.8 (2025-12-30)


## v1.0.7 (2025-12-19)

### Bug Fixes

- Inject naas_abi_core.modules.templatablesparqlquery by default
  ([`b6dc785`](https://github.com/jupyter-naas/abi/commit/b6dc78519e71afb46dd2ffc401539fab19fb865f))


## v1.0.6 (2025-12-08)


## v1.0.6-dev.1 (2025-12-08)


## v1.0.3-dev.2 (2025-12-04)

### Bug Fixes

- Use dependencies and not configuration from module
  ([`71e4f10`](https://github.com/jupyter-naas/abi/commit/71e4f102c4a7a5f16ba4d344a5ca878efea8ffe0))


## v1.0.3-dev.1 (2025-12-02)

### Bug Fixes

- Github and support module
  ([`8f113ea`](https://github.com/jupyter-naas/abi/commit/8f113ea071126a4ebd44e2aa22b26f55aa22bee3))
## v1.0.5 (2025-12-02)

### Bug Fixes

- Working on dependencies
  ([`cfb492f`](https://github.com/jupyter-naas/abi/commit/cfb492f5f1604d405ff0221d505e90101614d59e))


## v1.0.4 (2025-12-02)


## v1.0.3 (2025-12-02)

### Bug Fixes

- Update release commit parser option
  ([`6eabfd8`](https://github.com/jupyter-naas/abi/commit/6eabfd8f61681240a1974affd377b983bd7885a9))


## v1.0.2-dev.1 (2025-12-01)
## v1.0.2 (2025-12-01)

### Bug Fixes

- Working on fixing mypy check for core and naas-abi-marketplace linkedin
  ([`fc11437`](https://github.com/jupyter-naas/abi/commit/fc11437fa5b655805327783016318416d17a0f1b))


## v1.0.1 (2025-12-01)


## v1.0.0 (2025-12-01)

### Bug Fixes

- Configure release on main
  ([`fb32b93`](https://github.com/jupyter-naas/abi/commit/fb32b93ef0e3ce1b8bb291fda902a7a03c0f0646))
## v1.0.0-dev.12 (2025-12-01)


## v1.0.0-dev.11 (2025-12-01)


## v1.0.0-dev.10 (2025-11-30)

### Bug Fixes

- Trigger release
  ([`681608b`](https://github.com/jupyter-naas/abi/commit/681608bc3c4732a800c3987521b8fb2637e4ad39))


## v1.0.0-dev.9 (2025-11-30)


## v1.0.0-dev.8 (2025-11-30)


## v1.0.0-dev.7 (2025-11-30)

### Bug Fixes

- Trigger release
  ([`276711d`](https://github.com/jupyter-naas/abi/commit/276711dfe108f150067ac15876dcc191791fc3bc))


## v1.0.0-dev.6 (2025-11-30)

### Bug Fixes

- Trigger release
  ([`9100e73`](https://github.com/jupyter-naas/abi/commit/9100e73607e9f3b05146283b4b43070f0fc21353))


## v1.0.0-dev.5 (2025-11-30)


## v1.0.0-dev.4 (2025-11-30)

### Bug Fixes

- Trigger release
  ([`92f107e`](https://github.com/jupyter-naas/abi/commit/92f107ebf3f0a850fed34a18140ce1976fa39b07))


## v1.0.0-dev.3 (2025-11-30)

### Bug Fixes

- Uv install
  ([`c268208`](https://github.com/jupyter-naas/abi/commit/c268208bdcc69223fbb68114978211de7c161956))

- Working on ci
  ([`ba918da`](https://github.com/jupyter-naas/abi/commit/ba918da13147636ec732f2aba3e2978046b93970))

- Working on ci
  ([`15fc2f5`](https://github.com/jupyter-naas/abi/commit/15fc2f5c4ce0a92e017fe25ec91db4fac4f58ae8))


## v1.0.0-dev.2 (2025-11-30)

### Bug Fixes

- Remove scoped prefix for semantic releases
  ([`c208c3f`](https://github.com/jupyter-naas/abi/commit/c208c3f12ad1cd2eb2264a166f0e683184efb2ca))


## v1.0.0-dev.1 (2025-11-30)

- Initial Release
