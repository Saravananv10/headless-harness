// harness/chakra/src/grpc/builtInGrpcAgents.ts
import { EXPLORE_AGENT } from '../tools/AgentTool/built-in/exploreAgent.js'
import { GENERAL_PURPOSE_AGENT } from '../tools/AgentTool/built-in/generalPurposeAgent.js'
import { PLAN_AGENT } from '../tools/AgentTool/built-in/planAgent.js'
import { VERIFICATION_AGENT } from '../tools/AgentTool/built-in/verificationAgent.js'
import type { AgentDefinition } from '../tools/AgentTool/loadAgentsDir.js'

/**
 * Built-in subagents registered for every gRPC session.
 *
 * Uses explicit imports — not getBuiltInAgents() — so agents are always
 * available regardless of bun:bundle feature flags or GrowthBook gates.
 */
export const GRPC_BUILTIN_AGENTS: AgentDefinition[] = [
  PLAN_AGENT,
  GENERAL_PURPOSE_AGENT,
  VERIFICATION_AGENT,
  EXPLORE_AGENT,
]

export const GRPC_BUILTIN_AGENT_TYPES: string[] = GRPC_BUILTIN_AGENTS.map(
  (agent) => agent.agentType,
)
