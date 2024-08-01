define usage_str


░░      ░░░       ░░░        ░
▒  ▒▒▒▒  ▒▒  ▒▒▒▒  ▒▒▒▒▒  ▒▒▒▒
▓  ▓▓▓▓  ▓▓       ▓▓▓▓▓▓  ▓▓▓▓
█        ██  ████  █████  ████
█  ████  ██       ███        █
                              
Usage:
	make all: 					Create the conda environment and install the ABI kernel
	make dependencies: 				Install the dependencies
	make conda-install-kernel: 			Install the ABI kernel in the conda environment
	make conda-env-add package=<package>: 		Add a package to the conda environment
	make conda-env-update: 				Update the conda environment
	make conda-export: 				Export the conda environment to conda.yml
	make windows-install-conda: 			Download and install Miniconda for Windows
	make usage:					Show this message
	make build:					Build the Docker image to package ABI.

	make ci-generate-schedulers:			Generate the scheduler files for the CI/CD
	make ci-run-scheduler scheduler=<scheduler>:	Run a specific scheduler


endef
export usage_str

# # Detect the operating system
# ifeq ($(OS),Windows_NT)
#     OS_TYPE = Windows
# else
#     UNAME_S := $(shell uname -s)
#     ifeq ($(UNAME_S),Darwin)
#         OS_TYPE = macOS
#     else ifeq ($(UNAME_S),Linux)
#         OS_TYPE = Linux
# 	else
# 		OS_TYPE = Unknown
#     endif
# endif

# # Detect the architecture
# ifeq ($(OS_TYPE),Windows)
#     ARCH := $(shell if exist "%ProgramFiles(x86)%" (echo 64-bit) else (echo 32-bit))
# else
#     ARCH := $(shell uname -m)
#     ifeq ($(ARCH),x86_64)
#         ARCH = 64-bit
#     else ifeq ($(ARCH),i686)
#         ARCH = 32-bit
#     else ifeq ($(ARCH),arm64)
#         ARCH = arm64
#     else ifeq ($(ARCH),aarch64)
#         ARCH = 64-bit
#     else
#         ARCH = Unknown
#     endif
# endif


.PHONY: all conda-install-kernel conda-export windows-install-conda
usage:
	@echo "$$usage_str"

# Setup
# CONDA_EXISTS := $(shell if command -v conda >/dev/null 2>&1; then echo yes; else echo no; fi)
# setup:
# 	@ if [ "$(OS_TYPE)" == "Windows" ] && [ "$(CONDA_EXISTS)" == "no" ]; then \
# 		make windows-install-conda; \
# 	fi

# 	@ if [ "$(OS_TYPE)" == "macOS" ] && [ "$(CONDA_EXISTS)" == "no" ]; then \
# 		make macos-install-conda; \
# 	fi


all: conda-install-kernel

# Conda environment
MD5=$(shell command -v md5sum &> /dev/null && echo "md5sum" || echo "md5")
CONDA_ENV_HASH = .abi-conda/$(shell cat conda.yml | $(MD5) | sed 's/ .*//g').hash

$(CONDA_ENV_HASH): .abi-conda
	@ echo "\n📦 conda.yml drift detected. Updating conda environment ...\n\n"
	@ make conda-env-update && \
		make conda-update-hash && \
		echo "\n\n✅ conda environment updated.\n\n"

conda-update-hash:
	@ (rm .abi-conda/*.hash || true) && \
		touch $(CONDA_ENV_HASH)

.abi-conda:
	conda env create -f conda.yml --prefix .abi-conda
	make conda-update-hash

dep: dependencies
dependencies: .abi-conda $(CONDA_ENV_HASH)

conda-env-add: dep
	conda run -p .abi-conda pip install $(package)

conda-env-update:
	conda env update --file conda.yml --prune -p .abi-conda

conda-install-kernel: dep
	conda run -p .abi-conda python -m ipykernel install --user --name abi --display-name "abi"
	conda run -p .abi-conda jupyter kernelspec install --user .abi-conda/share/jupyter/kernels/python3/

conda-export: dep
	@ rm .naas_drivers_packages > /dev/null 2>&1; cat conda.yml | grep '\- naas-drivers' | sed 's/^.*\[//g; s/\].*//g' > .naas_drivers_packages
	@ echo "name: .abi-conda" > conda.yml
	@ conda run -p .abi-conda conda env export --no-builds | grep -v "^prefix: " | grep -v "^name: " >> conda.yml
	@ export packages=`cat .naas_drivers_packages` && cat conda.yml | sed "s/naas-drivers/naas-drivers\[$$packages\]/g" > conda.yml.new && mv conda.yml.new conda.yml
	@ rm .naas_drivers_packages

windows-install-conda:
	wget https://repo.anaconda.com/miniconda/Miniconda3-latest-Linux-x86_64.sh
	chmod +x Miniconda3-latest-Linux-x86_64.sh
	./Miniconda3-latest-Linux-x86_64.sh

# Docker
build: build.linux.x86_64

build.linux.x86_64:
	docker build . -t abi -f Dockerfile.linux.x86_64 --platform linux/amd64

# CI/CD
ci-generate-schedulers: dep
	@ conda run -p .abi-conda python .github/scripts/generate_schedulers.py

ci-run-scheduler: dep
	@ conda run -p .abi-conda python .github/scripts/run_scheduler.py $(scheduler)
# Validations

validate-config: dep
	@ conda run -p .abi-conda python .github/scripts/validate_jsonschema_yaml.py config.schema.json config.yml