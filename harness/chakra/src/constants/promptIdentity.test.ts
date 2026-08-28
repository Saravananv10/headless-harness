import { afterEach, expect, test } from 'bun:test'

import { getSystemPrompt, DEFAULT_AGENT_PROMPT } from './prompts.js'
import { CLI_SYSPROMPT_PREFIXES, getCLISyspromptPrefix } from './system.js'
import { GENERAL_PURPOSE_AGENT } from '../tools/AgentTool/built-in/generalPurposeAgent.js'
import { EXPLORE_AGENT } from '../tools/AgentTool/built-in/exploreAgent.js'

const originalSimpleEnv = process.env.CLAUDE_CODE_SIMPLE

afterEach(() => {
  process.env.CLAUDE_CODE_SIMPLE = originalSimpleEnv
})

test('CLI identity prefixes are cleared', () => {
  expect(getCLISyspromptPrefix()).toBe('')

  for (const prefix of CLI_SYSPROMPT_PREFIXES) {
    expect(prefix).toBe('')
  }
})

test('simple mode still boots a system prompt', async () => {
  process.env.CLAUDE_CODE_SIMPLE = '1'

  const prompt = await getSystemPrompt([], 'gpt-4o')

  expect(prompt[0]).toBeTruthy()
  expect(prompt[0]).not.toContain("Anthropic's official CLI for Claude")
})

test('built-in agent prompts no longer use Anthropic CLI identity', () => {
  expect(DEFAULT_AGENT_PROMPT).not.toContain("Anthropic's official CLI for Claude")
  expect(DEFAULT_AGENT_PROMPT).not.toContain('open-source fork of Soket AI Labs')

  const generalPrompt = GENERAL_PURPOSE_AGENT.getSystemPrompt({
    toolUseContext: { options: {} as never },
  })
  expect(generalPrompt).not.toContain("Anthropic's official CLI for Claude")
  expect(generalPrompt).not.toContain('open-source fork of Soket AI Labs')

  const explorePrompt = EXPLORE_AGENT.getSystemPrompt({
    toolUseContext: { options: {} as never },
  })
  expect(explorePrompt).not.toContain("Anthropic's official CLI for Claude")
  expect(explorePrompt).not.toContain('open-source fork of Soket AI Labs')
})
