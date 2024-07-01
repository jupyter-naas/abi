.abi-conda:
	conda env create -f conda.yml --prefix .abi-conda

all: .abi-conda

windows-install-conda:
	wget https://repo.anaconda.com/miniconda/Miniconda3-latest-Linux-x86_64.sh
	chmod +x Miniconda3-latest-Linux-x86_64.sh
	./Miniconda3-latest-Linux-x86_64.sh