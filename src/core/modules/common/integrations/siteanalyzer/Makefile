develop:
	docker compose run --workdir /app/src/core/modules/common/integrations/siteanalyzer abi bash -c '. "$$HOME/.cargo/env" && maturin develop && bash'

release:
	docker compose run --workdir /app/src/core/modules/common/integrations/siteanalyzer abi bash -c '. "$$HOME/.cargo/env" && maturin build --release'
