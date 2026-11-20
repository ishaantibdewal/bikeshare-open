.PHONY: all data features train test clean model check-model

# --- The pipeline ----------------------------------------------------------
all: data features train

data:
	python -m src.ingest

features:
	python -m src.features

train:
	python -m src.train

test:
	python -m pytest tests/ -q

clean:
	rm -f data/processed/*.parquet reports/metrics.json reports/*.png

# --- The agent model (open weights, local) ----------------------------------
# Builds `bikeshare-coder`: the base model plus a 64k context window, which
# Claude Code needs and Ollama does not give you by default. Pick a larger
# BASE if your machine has the memory (see README.md).
BASE ?= qwen3.5:9b

model:
	ollama pull $(BASE)
	# Ollama >= 0.22 no longer reads a Modelfile from stdin (`-f -` fails with
	# "no Modelfile or safetensors files found"), so write it to a file first.
	sed "s|^FROM .*|FROM $(BASE)|" model/Modelfile > model/.Modelfile.build
	ollama create bikeshare-coder -f model/.Modelfile.build
	rm -f model/.Modelfile.build

check-model:
	bash model/check.sh
