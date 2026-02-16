# CHANGELOG

<!-- version list -->

## v1.13.2 (2026-02-16)

### Bug Fixes

- **deps**: Move greenlet to nexus-api package
  ([`0a381ae`](https://github.com/jupyter-naas/abi/commit/0a381ae7f92ad326afe18cae21aeceb544c1a597))


## v1.13.1 (2026-02-13)

### Bug Fixes

- Critical local development setup issues
  ([`b63d50e`](https://github.com/jupyter-naas/abi/commit/b63d50efa54e6c7e3a09bc3b3552084c1c9586b0))


## v1.13.0 (2026-02-13)

### Features

- Add named graph management
  ([`e4557e2`](https://github.com/jupyter-naas/abi/commit/e4557e2e5d55a43e062cc105368c254035329709))

- Add tests for Jena and Oxigrpah. Also implemented a generci test to be reuse. Improved portal
  ([`43ab798`](https://github.com/jupyter-naas/abi/commit/43ab798f1db273bb319cf952d5874d2729b743fa))

- Added apache Jena TB2 Fuseki adapter to the triple store service
  ([`620c466`](https://github.com/jupyter-naas/abi/commit/620c46608f2f74e845ed754e0332049da651aae4))


## v1.12.0 (2026-02-12)

### Features

- Working on wiring nexus to abi
  ([`db01f8b`](https://github.com/jupyter-naas/abi/commit/db01f8b624870b47d1be9a331546ad5313a4204a))


## v1.11.0 (2026-02-10)

### Bug Fixes

- Dependency dagster
  ([`69601cd`](https://github.com/jupyter-naas/abi/commit/69601cdc8c9760227591ebd04631b064d3d26c5b))

- Error query
  ([`c1fc341`](https://github.com/jupyter-naas/abi/commit/c1fc34160da6123ec81805be58e3f4bbf304b0ca))

- Improve timeout qdrant
  ([`391f803`](https://github.com/jupyter-naas/abi/commit/391f803baafdc62aa8800dfbfef6e997cd33e198))

- Load ontologies not working
  ([`10de7ab`](https://github.com/jupyter-naas/abi/commit/10de7abd351c36ed537f0d692485cd4d01dd1894))

- Manage default values for properties
  ([`f290794`](https://github.com/jupyter-naas/abi/commit/f290794454b6a3ee1176a63d995923f99137693c))

- New instances must be owl NamedIndividual
  ([`6e105d4`](https://github.com/jupyter-naas/abi/commit/6e105d49429c002838632de9cec86eba682336a3))

- Print sparql query performed
  ([`fd52035`](https://github.com/jupyter-naas/abi/commit/fd520355b27452d78ca1e626d6f33c7ecf2566d9))

- Remove debug
  ([`bfddde8`](https://github.com/jupyter-naas/abi/commit/bfddde813433a61076e5a5693e555be6ea3accee))

- Remove logger debug (duplicates)
  ([`3428387`](https://github.com/jupyter-naas/abi/commit/3428387e40252a3786ca3b6587fb331d45e1b1f5))

- Rename classes
  ([`c4932f7`](https://github.com/jupyter-naas/abi/commit/c4932f7033eaa2d2143ef0cd6bb7f37f850bffd4))

- Replace union of list by list of union + manage duplicates
  ([`2b11c8a`](https://github.com/jupyter-naas/abi/commit/2b11c8aa13ac55432047ba1e41518cf684134fd1))

- Right hand side values are not supported in TypedDict
  ([`774ca70`](https://github.com/jupyter-naas/abi/commit/774ca707db85c0cfffa5f6d80b7f291ba7198f99))

- Use restrictions, label for class and property names
  ([`ef6320e`](https://github.com/jupyter-naas/abi/commit/ef6320e47052f765504d3106e22e573f7ad298d4))

### Features

- Add method to save py file next to ttl
  ([`41f9cf1`](https://github.com/jupyter-naas/abi/commit/41f9cf136c311eafc4ece0d05f537e12e761b7e2))

- Add rdfs label, dcterms creator and created as default properties for class
  ([`4fc863f`](https://github.com/jupyter-naas/abi/commit/4fc863f1cab52c2325e4830a957850cf4e560350))

- Bind namespace to graph, add class label as prop, improve meta prop
  ([`f65cfdf`](https://github.com/jupyter-naas/abi/commit/f65cfdf90b767361a26bb29b1ea15fbb4b6e42d5))

- Create class from ttl in folder ontologies + test on linkedin
  ([`0c34ce2`](https://github.com/jupyter-naas/abi/commit/0c34ce23e9ab1a69af932f1b8337f9de74ea30e9))

### Refactoring

- Print trace back and logger debug
  ([`fd64d06`](https://github.com/jupyter-naas/abi/commit/fd64d06e8ad6b401343455021a0675a429f5aeb6))


## v1.10.0 (2026-02-09)

### Bug Fixes

- Working on make check
  ([`fa75fc6`](https://github.com/jupyter-naas/abi/commit/fa75fc6f21c0b0fe0158a861085a31844dbaf6d2))

- Working on make check
  ([`f90773c`](https://github.com/jupyter-naas/abi/commit/f90773c8ab6aac94712c9cb2aaf18a1e73aff89f))

### Features

- Working on deploy local cli
  ([`c3ffe6d`](https://github.com/jupyter-naas/abi/commit/c3ffe6db633f2ce7789de5460d8849f80490b699))

- Working on deploy local cli
  ([`798e02a`](https://github.com/jupyter-naas/abi/commit/798e02ad2576f86344a54068fcd00e8f717c977d))


## v1.9.1 (2026-02-09)

### Bug Fixes

- Rename keyvalue directory name
  ([`5834c55`](https://github.com/jupyter-naas/abi/commit/5834c55179737ff3ff80384a474653379de2c643))


## v1.9.0 (2026-02-09)

### Bug Fixes

- Add check
  ([`a991e7c`](https://github.com/jupyter-naas/abi/commit/a991e7c28ec2a6a4f87fe1297c4b90efff80ed0e))

- Add redis and rabbitmq to all optional group
  ([`eac0fa6`](https://github.com/jupyter-naas/abi/commit/eac0fa61962863123d581017b6840dd14d232628))

- Adding debug
  ([`6ed8edf`](https://github.com/jupyter-naas/abi/commit/6ed8edf8e7dfea3906f1b2e0bb8deb355b1157f4))

- Improve BusService configuration and add redis/rabbitmq to optional dependencies
  ([`451d242`](https://github.com/jupyter-naas/abi/commit/451d242505e40f20792322b6862364df44194df1))

- Remove undesired print
  ([`3beedd8`](https://github.com/jupyter-naas/abi/commit/3beedd8eda8a81a08bf9fa6c12822c2936dea1eb))

- Replace print with logger.debug in TripleStoreService and fix whitespace
  ([`da1e6d0`](https://github.com/jupyter-naas/abi/commit/da1e6d01c2a7d0468e572a3b2bbf5995e485b385))

- Update CLI and rename KVService
  ([`00e62d6`](https://github.com/jupyter-naas/abi/commit/00e62d61c51e36f792cbdc2540e527596df67097))

- Working on PR fixes
  ([`2421685`](https://github.com/jupyter-naas/abi/commit/24216859bc2c122ffdea8ad7a4e8086c11701067))

- Working on review
  ([`a85b4a9`](https://github.com/jupyter-naas/abi/commit/a85b4a9a10910ac16d52ee8be1032e5c8ec311f1))

### Features

- Working on addint BusService, KeyValueService and reworking Dagster orchestration
  ([`bc448a6`](https://github.com/jupyter-naas/abi/commit/bc448a6a22c9f1788bb204e0671e6efb0c1bb774))


## v1.8.0 (2026-02-03)

### Features

- Working on Dagster orchestration
  ([`b970d21`](https://github.com/jupyter-naas/abi/commit/b970d21e135ab32c344122be50f292c0b44ff039))


## v1.7.2 (2026-02-02)

### Bug Fixes

- How ABI Agent loads templatable sparql query
  ([`fa80a8c`](https://github.com/jupyter-naas/abi/commit/fa80a8c83f19e485b6d01abbb0573f58e214f517))


## v1.7.1 (2026-01-26)

### Bug Fixes

- CICD checks
  ([`1cc9a0d`](https://github.com/jupyter-naas/abi/commit/1cc9a0d8aa9e5b89c06269f11b8437d3a60d2c23))


## v1.7.0 (2026-01-24)


## v1.6.0 (2026-01-24)

### Features

- Working on improving project initialization
  ([`e7063bb`](https://github.com/jupyter-naas/abi/commit/e7063bb63a7d3b553f159861fb3e1c545e7d8849))


## v1.5.1 (2026-01-16)


## v1.5.0 (2026-01-15)


## v1.4.2 (2026-01-08)

### Bug Fixes

- Pandas-stubs lib version
  ([`343d981`](https://github.com/jupyter-naas/abi/commit/343d981689c044c87c89ce2bf3fc1d5065acde55))

- Tipo license
  ([`f639213`](https://github.com/jupyter-naas/abi/commit/f639213b6c680d211c9618737842f01b51a65f8d))

- Tipo license
  ([`0269100`](https://github.com/jupyter-naas/abi/commit/0269100ca7d2d338d1f68be0717be6e981cc8eac))


## v1.4.1 (2026-01-08)

### Bug Fixes

- Add project urls in pyproject.toml
  ([`c155efa`](https://github.com/jupyter-naas/abi/commit/c155efa2a794b44312eb90ae19ab1c0da402d3ef))

### Documentation

- Add README.md to naas-abi-core
  ([`dc42682`](https://github.com/jupyter-naas/abi/commit/dc4268204d14a396945b34ad5f3bac38fbf7a7cb))


## v1.4.0 (2026-01-02)

### Bug Fixes

- Add default logo api
  ([`0036796`](https://github.com/jupyter-naas/abi/commit/0036796586ac904879f4dd1fa4a40a400bd0e4ef))

- Error aws neptune
  ([`76ffc39`](https://github.com/jupyter-naas/abi/commit/76ffc39a0d9408a68d39bf704172c4ff5f5d98c3))

- Remove connections from api doc
  ([`4f629bf`](https://github.com/jupyter-naas/abi/commit/4f629bf0df5e3f3df30453f2531879301b05252d))

### Features

- Add boto3-stubs
  ([`47dccd1`](https://github.com/jupyter-naas/abi/commit/47dccd144ab4811c1c4e481287b39026d07bb7ec))

### Refactoring

- Move workflows ontology yaml to naas module
  ([`b4e8e9f`](https://github.com/jupyter-naas/abi/commit/b4e8e9fd738a338c462c9df2525e043cfdf5095d))


## v1.3.0 (2026-01-02)

### Bug Fixes

- Get env value from .env if not in env
  ([`b984252`](https://github.com/jupyter-naas/abi/commit/b98425297e596142ee39ece11f6542ed713e4d4e))

- Improve config first pass loading for secret service
  ([`f598e79`](https://github.com/jupyter-naas/abi/commit/f598e7995e7984a6bbe51e1a7e8a4a34de121968))

- Missing f string + display config file name in debug
  ([`17e4bac`](https://github.com/jupyter-naas/abi/commit/17e4bac2541642aa97fe5f59522c6cbc578c60fa))

- Remove duplicated logger
  ([`7e9ffb8`](https://github.com/jupyter-naas/abi/commit/7e9ffb81023126fe56c3150aba12e885260956a8))

- Update package management & add types-pyyaml
  ([`5a66600`](https://github.com/jupyter-naas/abi/commit/5a666002264744f571015ac45eef3e583b458f40))

### Documentation

- Add docstring
  ([`76766b9`](https://github.com/jupyter-naas/abi/commit/76766b9acafee1d0dc5b2ee32057b0c3e5a0ba75))

### Features

- Test adaptors dotenv & naas
  ([`d3b7204`](https://github.com/jupyter-naas/abi/commit/d3b7204f663f4ed969446db8475d97197227336b))


## v1.2.1 (2025-12-30)


## v1.2.0 (2025-12-19)

### Bug Fixes

- Inject naas_abi_core.modules.templatablesparqlquery by default
  ([`b6dc785`](https://github.com/jupyter-naas/abi/commit/b6dc78519e71afb46dd2ffc401539fab19fb865f))

- Review
  ([`6301a5f`](https://github.com/jupyter-naas/abi/commit/6301a5fcda63875b2748a625727903f236772966))

- Review
  ([`1ad319b`](https://github.com/jupyter-naas/abi/commit/1ad319ba2e47463ab84cabf7edbd2b721b053e3b))

### Chores

- Remove comments
  ([`05868ff`](https://github.com/jupyter-naas/abi/commit/05868ff0c60ccb3e7da46cdd8903d207622d5e8c))

- Remove duplicate logger
  ([`8438450`](https://github.com/jupyter-naas/abi/commit/84384505a88b9645e56628b39bfda8da054792cc))

### Features

- Workin on naas-abi-cli
  ([`16cd62d`](https://github.com/jupyter-naas/abi/commit/16cd62d77879d94c83fae9218bd451c1909554e4))


## v1.1.2 (2025-12-05)

### Bug Fixes

- Make it possible to define env secrets from config.yaml
  ([`d9903cf`](https://github.com/jupyter-naas/abi/commit/d9903cfecac03df40a6f3076c7ff44229c0c12cd))


## v1.1.1 (2025-12-05)


## v1.1.0 (2025-12-05)

### Features

- Make it possible to add env var using cli deploy
  ([`eb32c8d`](https://github.com/jupyter-naas/abi/commit/eb32c8d9613ecbddb3a891f25db0a5bc3498b258))


## v1.0.8 (2025-12-05)


## v1.0.7 (2025-12-03)

### Bug Fixes

- Working on embedding assets in the release
  ([`9737428`](https://github.com/jupyter-naas/abi/commit/97374285cb3c79ed03399859c58b8cac6373627d))

- **marketplace**: Convert applications.pubmed to a real module
  ([`b9ac395`](https://github.com/jupyter-naas/abi/commit/b9ac395c0e90980fb19379d40ae5017efcf06d1d))


## v1.0.6 (2025-12-02)

### Bug Fixes

- Working on abi cli
  ([`e1c11a1`](https://github.com/jupyter-naas/abi/commit/e1c11a15a80403fdb1992faa4dcb035fbaf9b5c0))


## v1.0.5 (2025-12-02)

### Bug Fixes

- Working on dependencies
  ([`cfb492f`](https://github.com/jupyter-naas/abi/commit/cfb492f5f1604d405ff0221d505e90101614d59e))


## v1.0.4 (2025-12-02)

### Bug Fixes

- Update release commit parser option
  ([`6eabfd8`](https://github.com/jupyter-naas/abi/commit/6eabfd8f61681240a1974affd377b983bd7885a9))
## v1.0.4-dev.2 (2025-12-02)


## v1.0.4-dev.1 (2025-12-02)

### Bug Fixes

- **naas_abi_core**: Working on dependencies
  ([`54ad989`](https://github.com/jupyter-naas/abi/commit/54ad9896794cf831e503aef22170a0b0485e9e31))


## v1.0.3-dev.1 (2025-12-01)
## v1.0.3 (2025-12-01)

### Bug Fixes

- Working on fixing mypy check for core and naas-abi-marketplace linkedin
  ([`fc11437`](https://github.com/jupyter-naas/abi/commit/fc11437fa5b655805327783016318416d17a0f1b))


## v1.0.2 (2025-12-01)

### Bug Fixes

- Working on fixing mcp-server
  ([`69ba291`](https://github.com/jupyter-naas/abi/commit/69ba291474a171da1652a8769493d35f3d2d3843))


## v1.0.1 (2025-12-01)

### Bug Fixes

- Working on api tests in CI/CD
  ([`5012a3b`](https://github.com/jupyter-naas/abi/commit/5012a3b4408f138d6e5c90a36c6f4d250f56af8a))


## v1.0.0 (2025-12-01)
## v1.0.0-dev.10 (2025-12-01)

### Bug Fixes

- Adding authors and removing uneeded configuration
  ([`c105454`](https://github.com/jupyter-naas/abi/commit/c105454bcb1ed1da88bda6ca23a05e9e3e9c1ed1))

- Configure release on main
  ([`fb32b93`](https://github.com/jupyter-naas/abi/commit/fb32b93ef0e3ce1b8bb291fda902a7a03c0f0646))


## v1.0.0-dev.9 (2025-11-30)

### Bug Fixes

- Working on api deployment
  ([`8a803ba`](https://github.com/jupyter-naas/abi/commit/8a803bad5db9ed9d020d18245b3b6fbafda6bb2c))


## v1.0.0-dev.8 (2025-11-30)


## v1.0.0-dev.7 (2025-11-30)


## v1.0.0-dev.6 (2025-11-30)


## v1.0.0-dev.5 (2025-11-30)

### Bug Fixes

- Working on ci/cd
  ([`d65250c`](https://github.com/jupyter-naas/abi/commit/d65250c10e433595a6ecd124c33aee9ca7e69535))


## v1.0.0-dev.4 (2025-11-30)

### Bug Fixes

- Working on ci
  ([`ba918da`](https://github.com/jupyter-naas/abi/commit/ba918da13147636ec732f2aba3e2978046b93970))


## v1.0.0-dev.3 (2025-11-30)

### Bug Fixes

- Uv install
  ([`c268208`](https://github.com/jupyter-naas/abi/commit/c268208bdcc69223fbb68114978211de7c161956))


## v1.0.0-dev.2 (2025-11-30)

### Bug Fixes

- Remove scoped prefix for semantic releases
  ([`c208c3f`](https://github.com/jupyter-naas/abi/commit/c208c3f12ad1cd2eb2264a166f0e683184efb2ca))


## v1.0.0-dev.1 (2025-11-30)

- Initial Release
