#!/bin/bash
# Audit a repo's readiness for Dependabot auto-merge.
#
# Usage:
#   audit.sh <owner/repo> [<owner/repo> ...]
#   audit.sh --dir <path>      audit every git repo in a directory
#
# Read-only: makes no changes. Reports whether required status checks can
# actually be enforced, because auto-merge without them merges immediately
# and untested.

set -uo pipefail

command -v gh >/dev/null || { echo "audit: gh not found in PATH" >&2; exit 1; }
command -v jq >/dev/null || { echo "audit: jq not found in PATH" >&2; exit 1; }

audit_repo() {
  local r="$1" j adm priv def db prot checks wfs verdict reasons

  j=$(gh api "repos/$r" 2>/dev/null) || { printf '%s\n  ERROR: cannot read repo\n\n' "$r"; return; }
  adm=$(printf '%s' "$j" | jq -r '.permissions.admin|tostring')
  priv=$(printf '%s' "$j" | jq -r '.private|tostring')
  def=$(printf '%s' "$j" | jq -r '.default_branch')
  am=$(printf '%s' "$j" | jq -r '.allow_auto_merge|tostring')

  gh api "repos/$r/contents/.github/dependabot.yml" >/dev/null 2>&1 && db=yes || db=no

  prot=$(gh api "repos/$r/branches/$def/protection" 2>&1)
  if printf '%s' "$prot" | jq -e '.required_status_checks' >/dev/null 2>&1; then
    prot_state="protected, requires: $(printf '%s' "$prot" | jq -r '(.required_status_checks.contexts//[])|join(", ")')"
    prot_ok=yes
  elif printf '%s' "$prot" | grep -q 'Upgrade to GitHub Pro'; then
    prot_state="UNAVAILABLE (private repo on this plan)"; prot_ok=no
  elif printf '%s' "$prot" | grep -q 'Branch not protected'; then
    prot_state="unprotected (can be enabled)"; prot_ok=yes
  else
    prot_state="unknown: $(printf '%s' "$prot" | jq -r '.message // "?"' 2>/dev/null)"; prot_ok=no
  fi

  # Check-run names are job ids, not workflow names.
  local sha
  sha=$(gh api "repos/$r/commits?per_page=1" --jq '.[0].sha' 2>/dev/null)
  checks=$(gh api "repos/$r/commits/$sha/check-runs" --jq '.check_runs[].name' 2>/dev/null | sort -u | tr '\n' ' ')
  wfs=$(gh api "repos/$r/actions/workflows" --jq '.workflows[]? | select(.state=="active") | .path' 2>/dev/null \
        | grep '^\.github/workflows/' | tr '\n' ' ')

  # A repo with only linters and scanners has a nominal gate, not a real one.
  local has_test=no
  printf '%s' "$checks" | grep -qiE '(^| )(test|tests|spec|e2e|rspec|pytest|jest)( |$)' && has_test=yes

  local existing=no
  printf '%s' "$wfs" | grep -qi 'auto.\?merge' && existing=yes

  reasons=""
  verdict="ELIGIBLE"
  [ "$adm"  = "false" ] && { verdict="BLOCKED"; reasons="$reasons no-admin;"; }
  [ "$db"   = "no" ]    && { verdict="BLOCKED"; reasons="$reasons no-dependabot.yml;"; }
  [ -z "${checks// /}" ] && { verdict="BLOCKED"; reasons="$reasons no-ci-checks;"; }
  [ "$prot_ok" = "no" ] && { verdict="BLOCKED"; reasons="$reasons cannot-require-checks;"; }
  [ "$has_test" = "no" ] && [ "$verdict" = "ELIGIBLE" ] && { verdict="WEAK"; reasons="$reasons no-test-job-only-linters;"; }
  [ "$existing" = "yes" ] && reasons="$reasons existing-automerge-workflow-review-it;"

  printf '%s\n' "$r"
  printf '  private:%-6s admin:%-6s auto_merge:%s\n' "$priv" "$adm" "$am"
  printf '  dependabot.yml: %s\n' "$db"
  printf '  protection:     %s\n' "$prot_state"
  printf '  checks seen:    %s\n' "${checks:-(none)}"
  printf '  verdict:        %s%s\n\n' "$verdict" "${reasons:+  [${reasons% }]}"
}

main() {
  local repos=()
  if [ "${1:-}" = "--dir" ]; then
    local dir="${2:?--dir needs a path}"
    for d in "$dir"/*/; do
      local u
      u=$(git -C "$d" remote get-url origin 2>/dev/null) || continue
      repos+=("$(printf '%s' "$u" | sed -e 's#.*github\.com[:/]##' -e 's#\.git$##')")
    done
  else
    [ $# -gt 0 ] || { sed -n '2,12p' "$0"; exit 1; }
    repos=("$@")
  fi

  for r in "${repos[@]}"; do audit_repo "$r"; done

  cat <<'NOTE'
Reminder: enabling auto-merge without required status checks merges PRs
immediately and untested. Only proceed on repos marked ELIGIBLE.
NOTE
}

main "$@"
