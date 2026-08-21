APP_NAME := agentic-development
GREEN := $(shell tput -Txterm setaf 2)
YELLOW := $(shell tput -Txterm setaf 3)
RED := $(shell tput -Txterm setaf 1)
RESET := $(shell tput -Txterm sgr0)

HERDR_CONFIG_DIR := $(HOME)/.config/herdr
CLAUDE_HOOKS_DIR := $(HOME)/.claude/hooks
CODEX_DIR := $(HOME)/.codex
LOCAL_BIN := $(HOME)/.local/bin
REPO_DIR := $(shell pwd)

.DEFAULT_GOAL := help

# ============================================================================
# 🚀 Quick Start
# ============================================================================

.PHONY: all
all: install setup ## Install everything and configure

.PHONY: install
install: install-herdr install-spreader install-lazygit ## Install all dependencies

.PHONY: setup
setup: setup-config setup-hooks setup-workspaces setup-thrawn ## Configure herdr with this repo's settings

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
setup-config: ## Symlink herdr config files
	@echo "$(GREEN)Setting up herdr configuration...$(RESET)"
	@mkdir -p $(HERDR_CONFIG_DIR)
	@ln -sf $(REPO_DIR)/herdr/config.toml $(HERDR_CONFIG_DIR)/config.toml
	@ln -sf $(REPO_DIR)/herdr/spreader.yaml $(HERDR_CONFIG_DIR)/spreader.yaml
	@ln -sf $(REPO_DIR)/herdr/scripts/setup-spaces.sh $(HERDR_CONFIG_DIR)/setup-spaces.sh
	@ln -sf $(REPO_DIR)/herdr/scripts/setup-tabs.sh $(HERDR_CONFIG_DIR)/setup-tabs.sh
	@mkdir -p $(LOCAL_BIN)
	@ln -sf $(REPO_DIR)/herdr/scripts/scaffold-workspace.sh $(LOCAL_BIN)/herdr-scaffold-workspace
	@chmod +x $(REPO_DIR)/herdr/scripts/*.sh
	@echo "$(GREEN)Config symlinks created:$(RESET)"
	@echo "  $(YELLOW)~/.config/herdr/config.toml$(RESET)"
	@echo "  $(YELLOW)~/.config/herdr/spreader.yaml$(RESET)"
	@echo "  $(YELLOW)~/.config/herdr/setup-spaces.sh$(RESET)"
	@echo "  $(YELLOW)~/.config/herdr/setup-tabs.sh$(RESET)"
	@echo "  $(YELLOW)~/.local/bin/herdr-scaffold-workspace$(RESET)"

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

.PHONY: setup-thrawn
setup-thrawn: ## Install the thrawn orchestrator CLI
	@echo "$(GREEN)Setting up thrawn...$(RESET)"
	@mkdir -p $(HOME)/.local/bin
	@chmod +x $(REPO_DIR)/thrawn/bin/thrawn
	@ln -sf $(REPO_DIR)/thrawn/bin/thrawn $(HOME)/.local/bin/thrawn
	@echo "$(GREEN)thrawn linked:$(RESET)"
	@echo "  $(YELLOW)~/.local/bin/thrawn$(RESET)"
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
unlink: ## Remove all symlinks (keeps tools installed)
	@echo "$(YELLOW)Removing symlinks...$(RESET)"
	@rm -f $(HERDR_CONFIG_DIR)/config.toml
	@rm -f $(HERDR_CONFIG_DIR)/spreader.yaml
	@rm -f $(HERDR_CONFIG_DIR)/setup-spaces.sh
	@rm -f $(HERDR_CONFIG_DIR)/setup-tabs.sh
	@rm -f $(LOCAL_BIN)/herdr-scaffold-workspace
	@rm -f $(CLAUDE_HOOKS_DIR)/herdr-agent-state.sh
	@rm -f $(CODEX_DIR)/herdr-agent-state.sh
	@rm -f $(HOME)/.local/bin/thrawn
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
	@echo ""
	@echo "$(YELLOW)Hook symlinks:$(RESET)"
	@printf "  claude hook:    "; [ -L $(CLAUDE_HOOKS_DIR)/herdr-agent-state.sh ] && echo "$(GREEN)linked$(RESET)" || echo "$(RED)not linked$(RESET)"
	@printf "  codex hook:     "; [ -L $(CODEX_DIR)/herdr-agent-state.sh ] && echo "$(GREEN)linked$(RESET)" || echo "$(RED)not linked$(RESET)"
	@echo ""
	@echo "$(YELLOW)Thrawn:$(RESET)"
	@printf "  thrawn CLI:     "; [ -L $(HOME)/.local/bin/thrawn ] && echo "$(GREEN)linked$(RESET)" || echo "$(RED)not linked$(RESET)"

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
