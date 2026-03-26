/**
 * Delegates agent runs to the Python/Flask service when FLASK_AGENT_URL is set.
 */
import { config } from 'dotenv';
import type { AgentRunRequest } from './agent-runner.js';

config({ quiet: true });

function flaskBaseUrl(): string | undefined {
  const u = process.env.FLASK_AGENT_URL || process.env.DEXTER_FLASK_URL;
  return u?.replace(/\/$/, '') || undefined;
}

export function isFlaskAgentEnabled(): boolean {
  return Boolean(flaskBaseUrl());
}

export async function runAgentViaFlask(req: AgentRunRequest): Promise<string> {
  const base = flaskBaseUrl();
  if (!base) {
    throw new Error('Flask agent URL not configured');
  }
  const r = await fetch(`${base}/api/agent/run`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      sessionKey: req.sessionKey,
      query: req.query,
      model: req.model,
      modelProvider: req.modelProvider,
      maxIterations: req.maxIterations ?? 10,
      isolatedSession: req.isolatedSession ?? false,
      channel: req.channel,
      groupContext: req.groupContext,
      isHeartbeat: req.isHeartbeat,
    }),
  });
  if (!r.ok) {
    const body = await r.text();
    throw new Error(`Flask agent error: ${r.status} ${body.slice(0, 500)}`);
  }
  const j = (await r.json()) as { answer?: string };
  return j.answer ?? '';
}
