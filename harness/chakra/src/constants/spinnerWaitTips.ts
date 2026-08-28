/**
 * Sync fallback lines for the primary spinner row when `spinnerTip` is not yet
 * available (e.g. first wait) or undefined. Rotated deterministically via
 * `spinnerSessionKey` so the line is stable for a given wait.
 */
export const SPINNER_WAIT_TIPS: string[] = [
  'Tip: Press ? for shortcuts and slash commands',
  'Tip: /clear frees context when you switch topics',
  'Tip: /compact can shrink long threads without losing the task',
  'Tip: Tab completes paths and command names in many prompts',
  'Tip: Redirect long output to a file and @-mention it for the model',
  'Tip: Git worktrees isolate branches without stashing everything',
  'Tip: ripgrep (rg) respects .gitignore — fast repo-wide search',
  'Tip: jq filters JSON in the shell without leaving the terminal',
  'Tip: Set CHAKRA.md for project conventions the agent should follow',
  'Tip: Use skills for workflows you run more than twice',
  'Tip: /model switches models mid-session when you need speed vs depth',
  'Tip: Verbose mode shows more tool and timing detail',
  'Tip: Your shell history is searchable — Ctrl+R in bash/zsh',
  'Tip: tmux or zellij keep sessions alive over SSH drops',
  'Tip: Small, focused prompts often beat one giant paragraph',
]

export function pickSpinnerWaitTip(sessionKey: number): string {
  const i = Math.abs(sessionKey) % SPINNER_WAIT_TIPS.length
  return SPINNER_WAIT_TIPS[i] ?? SPINNER_WAIT_TIPS[0]!
}
