.abi-conda:
	conda env create -f conda.yml --prefix .abi-conda

all: .abi-conda