# naas-abi-idp

The built-in OIDC identity provider of ABI, for `abi dev up` and small installs.
It is an SDK module (`naas_abi_sdk.BaseModule`) that runs over NATS, depends on
the SDK, the proto package and `authlib` only, and shares nothing with Nexus or
the engine: its data lives in its own Document Service namespace (`idp`) and its
signing keys in the secret service under `idp/`, both sealed to its service
account.

See [AGENTS.md](AGENTS.md).
