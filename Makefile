APP_NAME := agentic-development
GREEN := $(shell tput -Txterm setaf 2)
YELLOW := $(shell tput -Txterm setaf 3)
RED := $(shell tput -Txterm setaf 1)
RESET := $(shell tput -Txterm sgr0)

HERDR_CONFIG_DIR := $(HOME)/.config/herdr
CLAUDE_HOOKS_DIR := $(HOME)/.claude/hooks
CODEX_DIR := $(HOME)/.codex
CLAUDE_SKILLS_DIR := $(HOME)/.claude/skills
LOCAL_BIN := $(HOME)/.local/bin
REPO_DIR := $(shell pwd)

# Machine-local overrides. When either exists it replaces the committed config
# outright — nothing is merged — so a work machine can carry a private repo list
# and its own keybindings without either landing in git.
LOCAL_REPOS := $(HERDR_CONFIG_DIR)/repos.local.yaml
LOCAL_CONFIG := $(HERDR_CONFIG_DIR)/config.local.toml

# Directory scanned by `make repos-local`.
CODE_DIR ?= $(HOME)/Documents/Code

.DEFAULT_GOAL := help

# ============================================================================
# 🚀 Quick Start
# ============================================================================

.PHONY: all
all: install setup ## Install everything and configure

.PHONY: install
install: install-herdr install-spreader install-lazygit ## Install all dependencies

.PHONY: setup
setup: setup-config setup-hooks setup-skills setup-souls setup-workspaces setup-thrawn ## Configure herdr with this repo's settings

# ============================================================================
# 📦 Installation
# ============================================================================

.PHONY: install-herdr
install-herdr: ## Install herdr via Homebrew
	@echo "$(GREEN)Installing herdr...$(RESET)"
	@if command -v herdr >/dev/null 2>&1; then \
		echo "$(YELLOW)herdr already installed$(RESET)"; \
	else \
		brew install herdr; \
		echo "$(GREEN)herdr installed successfully$(RESET)"; \
	fi

.PHONY: install-spreader
install-spreader: ## Install herdr-spreader via cargo
	@echo "$(GREEN)Installing herdr-spreader...$(RESET)"
	@if command -v herdr-spreader >/dev/null 2>&1; then \
		echo "$(YELLOW)herdr-spreader already installed$(RESET)"; \
	else \
		cargo install herdr-spreader; \
		echo "$(GREEN)herdr-spreader installed successfully$(RESET)"; \
	fi

.PHONY: install-lazygit
install-lazygit: ## Install lazygit (used in prefix+g popup)
	@echo "$(GREEN)Installing lazygit...$(RESET)"
	@if command -v lazygit >/dev/null 2>&1; then \
		echo "$(YELLOW)lazygit already installed$(RESET)"; \
	else \
		brew install lazygit; \
		echo "$(GREEN)lazygit installed successfully$(RESET)"; \
	fi

.PHONY: install-deps
install-deps: ## Install brew and cargo if missing
	@echo "$(GREEN)Checking dependencies...$(RESET)"
	@if ! command -v brew >/dev/null 2>&1; then \
		echo "$(YELLOW)Installing Homebrew...$(RESET)"; \
		/bin/bash -c "$$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"; \
	fi
	@if ! command -v cargo >/dev/null 2>&1; then \
		echo "$(YELLOW)Installing Rust/Cargo...$(RESET)"; \
		curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh -s -- -y; \
	fi
	@echo "$(GREEN)Dependencies ready$(RESET)"

# ============================================================================
# 🔧 Configuration
# ============================================================================

.PHONY: setup-config
setup-config: ## Symlink herdr config files (machine-local overrides win)
	@echo "$(GREEN)Setting up herdr configuration...$(RESET)"
	@mkdir -p $(HERDR_CONFIG_DIR)
	@if [ -f $(LOCAL_CONFIG) ]; then \
		ln -sf $(LOCAL_CONFIG) $(HERDR_CONFIG_DIR)/config.toml; \
		echo "  $(YELLOW)~/.config/herdr/config.toml$(RESET) -> config.local.toml $(GREEN)(machine-local)$(RESET)"; \
	else \
		ln -sf $(REPO_DIR)/herdr/config.toml $(HERDR_CONFIG_DIR)/config.toml; \
		echo "  $(YELLOW)~/.config/herdr/config.toml$(RESET) -> repo herdr/config.toml"; \
	fi
	@if [ -f $(LOCAL_REPOS) ]; then \
		ln -sf $(LOCAL_REPOS) $(HERDR_CONFIG_DIR)/spreader.yaml; \
		echo "  $(YELLOW)~/.config/herdr/spreader.yaml$(RESET) -> repos.local.yaml $(GREEN)(machine-local)$(RESET)"; \
	else \
		ln -sf $(REPO_DIR)/herdr/spreader.yaml $(HERDR_CONFIG_DIR)/spreader.yaml; \
		echo "  $(YELLOW)~/.config/herdr/spreader.yaml$(RESET) -> repo herdr/spreader.yaml"; \
	fi
	@ln -sf $(REPO_DIR)/herdr/scripts/setup-spaces.sh $(HERDR_CONFIG_DIR)/setup-spaces.sh
	@ln -sf $(REPO_DIR)/herdr/scripts/setup-tabs.sh $(HERDR_CONFIG_DIR)/setup-tabs.sh
	@mkdir -p $(LOCAL_BIN)
	@ln -sf $(REPO_DIR)/herdr/scripts/scaffold-workspace.sh $(LOCAL_BIN)/herdr-scaffold-workspace
	@ln -sf $(REPO_DIR)/herdr/scripts/gen-spreader.sh $(LOCAL_BIN)/herdr-gen-spreader
	@chmod +x $(REPO_DIR)/herdr/scripts/*.sh
	@echo "  $(YELLOW)~/.config/herdr/setup-spaces.sh$(RESET)"
	@echo "  $(YELLOW)~/.config/herdr/setup-tabs.sh$(RESET)"
	@echo "  $(YELLOW)~/.local/bin/herdr-scaffold-workspace$(RESET)"
	@echo "  $(YELLOW)~/.local/bin/herdr-gen-spreader$(RESET)"

.PHONY: setup-hooks
setup-hooks: ## Symlink agent integration hooks
	@echo "$(GREEN)Setting up agent hooks...$(RESET)"
	@mkdir -p $(CLAUDE_HOOKS_DIR)
	@mkdir -p $(CODEX_DIR)
	@ln -sf $(REPO_DIR)/herdr/hooks/claude-agent-state.sh $(CLAUDE_HOOKS_DIR)/herdr-agent-state.sh
	@ln -sf $(REPO_DIR)/herdr/hooks/codex-agent-state.sh $(CODEX_DIR)/herdr-agent-state.sh
	@chmod +x $(REPO_DIR)/herdr/hooks/*.sh
	@echo "$(GREEN)Hook symlinks created:$(RESET)"
	@echo "  $(YELLOW)~/.claude/hooks/herdr-agent-state.sh$(RESET)"
	@echo "  $(YELLOW)~/.codex/herdr-agent-state.sh$(RESET)"

.PHONY: setup-skills
setup-skills: ## Symlink Claude Code skills
	@echo "$(GREEN)Setting up Claude Code skills...$(RESET)"
	@mkdir -p $(CLAUDE_SKILLS_DIR)
	@for s in $(REPO_DIR)/skills/*/; do \
		name=$$(basename "$$s"); \
		ln -sfn "$$s" $(CLAUDE_SKILLS_DIR)/$$name; \
		echo "  $(YELLOW)~/.claude/skills/$$name$(RESET)"; \
	done
	@chmod +x $(REPO_DIR)/skills/*/*.sh 2>/dev/null || true

.PHONY: setup-souls
setup-souls: ## Symlink the souls roster to ~/.claude/souls
	@echo "$(GREEN)Setting up souls...$(RESET)"
	@ln -sfn $(REPO_DIR)/souls $(HOME)/.claude/souls
	@echo "  $(YELLOW)~/.claude/souls$(RESET) -> repo souls/"

.PHONY: setup-workspaces
setup-workspaces: ## Create all workspaces using herdr-spreader
	@echo "$(GREEN)Creating workspaces...$(RESET)"
	@if command -v herdr-spreader >/dev/null 2>&1; then \
		herdr-spreader apply --file $(HERDR_CONFIG_DIR)/spreader.yaml && \
		echo "$(GREEN)Workspaces created successfully$(RESET)"; \
	else \
		echo "$(RED)herdr-spreader not found. Run 'make install-spreader' first$(RESET)"; \
		exit 1; \
	fi

# ============================================================================
# 🗂  Repo list
# ============================================================================

.PHONY: repos
repos: ## Show the workspace list currently in effect
	@src=$$(bash $(REPO_DIR)/herdr/scripts/resolve-repos.sh --source) || exit 1; \
	file=$$(bash $(REPO_DIR)/herdr/scripts/resolve-repos.sh) || exit 1; \
	case "$$src" in \
		env)   echo "$(GREEN)Source:$(RESET) \$$HERDR_REPOS" ;; \
		local) echo "$(GREEN)Source:$(RESET) machine-local" ;; \
		repo)  echo "$(GREEN)Source:$(RESET) committed personal list" ;; \
	esac; \
	echo "$(GREEN)File:$(RESET)   $$file"; \
	echo ""; \
	bash $(REPO_DIR)/herdr/scripts/resolve-repos.sh --entries \
		| while IFS="$$(printf '\t')" read -r label path; do \
			if [ -d "$$path" ]; then mark="$(GREEN)✓$(RESET)"; else mark="$(RED)✗$(RESET)"; fi; \
			printf "  %b %-30s %s\n" "$$mark" "$$label" "$$path"; \
		done
	@echo ""
	@echo "$(YELLOW)✗ = directory not present on this machine (skipped at setup)$(RESET)"

.PHONY: repos-local
repos-local: ## Generate a machine-local repo list by scanning CODE_DIR
	@echo "$(GREEN)Scanning $(CODE_DIR)...$(RESET)"
	@bash $(REPO_DIR)/herdr/scripts/gen-spreader.sh --scan $(CODE_DIR) -o $(LOCAL_REPOS) --force
	@$(MAKE) --no-print-directory setup-config
	@echo ""
	@echo "$(YELLOW)Review $(LOCAL_REPOS), then run 'make setup-workspaces'$(RESET)"

.PHONY: setup-thrawn
setup-thrawn: ## Install the thrawn orchestrator CLI
	@echo "$(GREEN)Setting up thrawn...$(RESET)"
	@mkdir -p $(HOME)/.local/bin $(HOME)/bin
	@chmod +x $(REPO_DIR)/thrawn/bin/thrawn
	@ln -sf $(REPO_DIR)/thrawn/bin/thrawn $(HOME)/.local/bin/thrawn
	@ln -sf $(REPO_DIR)/thrawn/bin/thrawn $(HOME)/bin/thrawn
	@echo "$(GREEN)thrawn linked:$(RESET)"
	@echo "  $(YELLOW)~/.local/bin/thrawn$(RESET)"
	@echo "  $(YELLOW)~/bin/thrawn$(RESET)"
	@case ":$$PATH:" in \
		*":$(HOME)/.local/bin:"*) ;; \
		*) echo "$(RED)~/.local/bin is not on your PATH — add it to your shell rc$(RESET)" ;; \
	esac

# ============================================================================
# 🧪 Testing
# ============================================================================

.PHONY: test
test: ## Run the thrawn test suite (pytest)
	@echo "$(GREEN)Running thrawn tests...$(RESET)"
	@python3 -m pytest thrawn/tests -q --basetemp=.pytest-tmp

.PHONY: lint
lint: ## Lint thrawn with ruff
	@echo "$(GREEN)Linting thrawn...$(RESET)"
	@ruff check thrawn/bin/thrawn thrawn/tests

# ============================================================================
# 🔄 Updates
# ============================================================================

.PHONY: update
update: update-herdr update-spreader ## Update all tools

.PHONY: update-herdr
update-herdr: ## Update herdr to latest version
	@echo "$(GREEN)Updating herdr...$(RESET)"
	@brew upgrade herdr || brew install herdr
	@echo "$(GREEN)herdr updated$(RESET)"

.PHONY: update-spreader
update-spreader: ## Update herdr-spreader to latest version
	@echo "$(GREEN)Updating herdr-spreader...$(RESET)"
	@cargo install herdr-spreader --force
	@echo "$(GREEN)herdr-spreader updated$(RESET)"

# ============================================================================
# 🧹 Cleanup
# ============================================================================

.PHONY: unlink
unlink: ## Remove all symlinks (keeps tools and machine-local configs)
	@echo "$(YELLOW)Removing symlinks...$(RESET)"
	@# repos.local.yaml and config.local.toml are deliberately left alone — they
	@# are yours, not ours, and nothing in the repo can regenerate their contents.
	@rm -f $(HERDR_CONFIG_DIR)/config.toml
	@rm -f $(HERDR_CONFIG_DIR)/spreader.yaml
	@rm -f $(HERDR_CONFIG_DIR)/setup-spaces.sh
	@rm -f $(HERDR_CONFIG_DIR)/setup-tabs.sh
	@rm -f $(LOCAL_BIN)/herdr-scaffold-workspace
	@rm -f $(LOCAL_BIN)/herdr-gen-spreader
	@rm -f $(CLAUDE_HOOKS_DIR)/herdr-agent-state.sh
	@rm -f $(CODEX_DIR)/herdr-agent-state.sh
	@for s in $(REPO_DIR)/skills/*/; do rm -f $(CLAUDE_SKILLS_DIR)/$$(basename "$$s"); done
	@rm -f $(HOME)/.claude/souls
	@rm -f $(HOME)/.local/bin/thrawn
	@rm -f $(HOME)/bin/thrawn
	@echo "$(GREEN)Symlinks removed$(RESET)"

.PHONY: uninstall
uninstall: unlink ## Uninstall herdr and remove symlinks
	@echo "$(YELLOW)Uninstalling herdr...$(RESET)"
	@brew uninstall herdr 2>/dev/null || true
	@cargo uninstall herdr-spreader 2>/dev/null || true
	@echo "$(GREEN)Uninstall complete$(RESET)"

# ============================================================================
# 🔍 Status
# ============================================================================

.PHONY: status
status: ## Show installation status
	@echo "$(GREEN)Installation Status$(RESET)"
	@echo ""
	@echo "$(YELLOW)Tools:$(RESET)"
	@printf "  herdr:          "; command -v herdr >/dev/null 2>&1 && echo "$(GREEN)installed$(RESET)" || echo "$(RED)not installed$(RESET)"
	@printf "  herdr-spreader: "; command -v herdr-spreader >/dev/null 2>&1 && echo "$(GREEN)installed$(RESET)" || echo "$(RED)not installed$(RESET)"
	@printf "  lazygit:        "; command -v lazygit >/dev/null 2>&1 && echo "$(GREEN)installed$(RESET)" || echo "$(RED)not installed$(RESET)"
	@echo ""
	@echo "$(YELLOW)Config symlinks:$(RESET)"
	@printf "  config.toml:    "; [ -L $(HERDR_CONFIG_DIR)/config.toml ] && echo "$(GREEN)linked$(RESET)" || echo "$(RED)not linked$(RESET)"
	@printf "  spreader.yaml:  "; [ -L $(HERDR_CONFIG_DIR)/spreader.yaml ] && echo "$(GREEN)linked$(RESET)" || echo "$(RED)not linked$(RESET)"
	@printf "  scaffold CLI:   "; [ -L $(LOCAL_BIN)/herdr-scaffold-workspace ] && echo "$(GREEN)linked$(RESET)" || echo "$(RED)not linked$(RESET)"
	@printf "  gen-spreader:   "; [ -L $(LOCAL_BIN)/herdr-gen-spreader ] && echo "$(GREEN)linked$(RESET)" || echo "$(RED)not linked$(RESET)"
	@echo ""
	@echo "$(YELLOW)Machine-local overrides:$(RESET)"
	@printf "  config.local:   "; [ -f $(LOCAL_CONFIG) ] && echo "$(GREEN)present (overrides repo config.toml)$(RESET)" || echo "$(YELLOW)none - using repo config.toml$(RESET)"
	@printf "  repos.local:    "; [ -f $(LOCAL_REPOS) ] && echo "$(GREEN)present (overrides repo spreader.yaml)$(RESET)" || echo "$(YELLOW)none - using repo spreader.yaml$(RESET)"
	@printf "  active list:    "; bash $(REPO_DIR)/herdr/scripts/resolve-repos.sh 2>/dev/null \
		| sed "s|^$(HOME)|~|" || echo "$(RED)unresolved$(RESET)"
	@printf "  workspaces:     "; bash $(REPO_DIR)/herdr/scripts/resolve-repos.sh --entries 2>/dev/null | wc -l | tr -d ' '
	@echo ""
	@echo "$(YELLOW)Hook symlinks:$(RESET)"
	@printf "  claude hook:    "; [ -L $(CLAUDE_HOOKS_DIR)/herdr-agent-state.sh ] && echo "$(GREEN)linked$(RESET)" || echo "$(RED)not linked$(RESET)"
	@printf "  codex hook:     "; [ -L $(CODEX_DIR)/herdr-agent-state.sh ] && echo "$(GREEN)linked$(RESET)" || echo "$(RED)not linked$(RESET)"
	@echo ""
	@echo "$(YELLOW)Skills:$(RESET)"
	@printf "  dependabot:     "; [ -L $(CLAUDE_SKILLS_DIR)/dependabot-automerge ] && echo "$(GREEN)linked$(RESET)" || echo "$(RED)not linked$(RESET)"
	@echo ""
	@echo "$(YELLOW)Thrawn:$(RESET)"
	@printf "  thrawn CLI:     "; [ -L $(HOME)/.local/bin/thrawn ] && echo "$(GREEN)linked$(RESET)" || echo "$(RED)not linked$(RESET)"
	@printf "  thrawn ~/bin:   "; [ -L $(HOME)/bin/thrawn ] && echo "$(GREEN)linked$(RESET)" || echo "$(RED)not linked$(RESET)"

# ============================================================================
# 📖 Help
# ============================================================================

.PHONY: help
help: ## Show all available make targets
	@echo "$(GREEN)$(APP_NAME) - Available targets:$(RESET)"
	@echo ""
	@grep -E '^[a-zA-Z0-9_.-]+:.*?## .*$$' $(MAKEFILE_LIST) \
		| sort \
		| awk 'BEGIN {FS = ":.*?## "}; {printf "  $(YELLOW)%-20s$(RESET) %s\n", $$1, $$2}'
	@echo ""
	@echo "$(GREEN)Quick start:$(RESET)"
	@echo "  make all          # Install everything and configure"
	@echo "  make status       # Check what's installed"
