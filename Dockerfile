# GateProbe image (I4): the CLI with the corpus, policies, variants and configs.
# Reviewers replay recorded runs with no API key and no network:
#   docker run --rm --network none -v "$PWD/cache:/gateprobe/cache" -v "$PWD/runs:/gateprobe/runs" \
#     -v "$PWD/reports:/gateprobe/reports" gateprobe replay --gate jev --variants variants/generated.jsonl
# The package is installed editable at /gateprobe because it locates configs/,
# policies/ and the judge prompt relative to its source tree.
FROM python:3.11-slim

# Provenance without git in the image: build with --build-arg GIT_HASH=$(git rev-parse HEAD)
ARG GIT_HASH=unknown
ENV PYTHONDONTWRITEBYTECODE=1 PIP_NO_CACHE_DIR=1 PIP_DISABLE_PIP_VERSION_CHECK=1 GATEPROBE_GIT_HASH=$GIT_HASH
WORKDIR /gateprobe
COPY pyproject.toml README.md ./
COPY src ./src
RUN pip install -e ".[claude]"
COPY configs ./configs
COPY policies ./policies
COPY probes ./probes
COPY variants ./variants
RUN mkdir -p cache runs reports results
ENTRYPOINT ["gateprobe"]
CMD ["--help"]
