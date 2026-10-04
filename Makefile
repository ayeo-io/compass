# Compass - top-level targets.
#
# The canonical command for each thing. `make test` disables pytest plugin
# autoload so the suite runs from a clean checkout; autoloaded plugins are
# the most common cause of environment-specific hangs.

.PHONY: help test test-clean lint validate ci release clean

# Parallel workers when pytest-xdist is installed. Autoload stays off, so the
# plugin is loaded by name; without it the suite runs in series as before.
XDIST := $(shell python3 -c "import xdist" 2>/dev/null && echo "-p xdist.plugin -n auto")

# `make ci` checks issues landed since the latest release tag; the ones
# before it were checked when that release was cut. COMPASS_FULL_ARCHIVE=1,
# or a checkout with no tag, checks every issue.
LAST_TAG := $(shell git describe --tags --abbrev=0 2>/dev/null)
SINCE := $(if $(COMPASS_FULL_ARCHIVE),,$(if $(LAST_TAG),--since $(LAST_TAG)))

help:  ## list targets
	@grep -E '^[a-z-]+:.*?##' Makefile | awk -F':.*?##' '{printf "  %-12s %s\n", $$1, $$2}'

test:  ## run the CLI test suite (autoload disabled - reliable in clean envs)
	PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 python3 -m pytest tests/ -q $(if $(XDIST),$(XDIST) -m "not serial")
	$(if $(XDIST),PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 python3 -m pytest tests/ -q -m serial)

# The target `make test-clean` runs inside the clone; a test of the target sets
# it to `help` to prove the clone works without running the whole suite.
CLEAN_TARGET ?= test

test-clean:  ## run the suite in a fresh clone of HEAD, as CI sees it (commit first)
	@d=$$(mktemp -d) && trap 'rm -rf "$$d"' EXIT && \
	  echo "test-clean: running in a clean clone of $$(git rev-parse --short HEAD); uncommitted changes and ignored files are left out" && \
	  git clone -q --no-hardlinks . "$$d/compass" && \
	  $(MAKE) -s -C "$$d/compass" $(CLEAN_TARGET)

lint:  ## check governance YAML
	python3 cli/compass policy lint

validate:  ## self-check the framework repo structure
	bash scripts/validate.sh

ci:  ## the mechanical gate suite (policy lint + issue lint + check of issues since the last tag)
	python3 cli/compass ci $(SINCE)

release:  ## build a clean release tarball into dist/
	bash scripts/release.sh

adapter-check:  ## run the pytest-bdd adapter exactly as CI does (cleans derived files first)
	git clean -fdX examples/
	cd examples/bdd-adapters/pytest-bdd && \
	  python3 ../../../cli/compass bdd extract --issue reset-password && \
	  python3 -m pytest tests/ -q
	@echo "adapter-check: PASS (from a clean tree, as CI sees it)"

clean:  ## remove build / pytest / cache noise (leaves `.compass/work/` alone)
	find . -name '__pycache__' -type d -exec rm -rf {} + 2>/dev/null || true
	find . -name '*.pyc' -delete 2>/dev/null || true
	find . -name '*.bak' -delete 2>/dev/null || true
	find . -name '.DS_Store' -delete 2>/dev/null || true
	rm -rf .pytest_cache .mypy_cache .coverage dist build 2>/dev/null || true
	@echo "cleaned."
