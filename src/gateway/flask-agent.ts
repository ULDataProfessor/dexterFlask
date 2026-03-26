/**
 * Delegates agent runs to the Python/Flask service when FLASK_AGENT_URL is set.
 */
import { config } from 'dotenv';
import type { AgentRunRequest } from './agent-runner.js';
import type { ApprovalDecision } from '../agent/types.js';

config({ quiet: true });

function flaskBaseUrl(): string | undefined {
  const u = process.env.FLASK_AGENT_URL || process.env.DEXTER_FLASK_URL;
  return u?.replace(/\/$/, '') || undefined;
}

export function isFlaskAgentEnabled(): boolean {
  return Boolean(flaskBaseUrl());
}

async function runAgentViaFlaskStream(req: AgentRunRequest): Promise<string> {
  const base = flaskBaseUrl();
  if (!base) {
    throw new Error('Flask agent URL not configured');
  }

  const r = await fetch(`${base}/api/agent/stream`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      sessionKey: req.sessionKey,
      runId: req.runId,
      query: req.query,
      model: req.model,
      modelProvider: req.modelProvider,
      maxIterations: req.maxIterations ?? 10,
      isolatedSession: req.isolatedSession ?? false,
      channel: req.channel,
      groupContext: req.groupContext,
      isHeartbeat: req.isHeartbeat,
    }),
    signal: req.signal,
  });

  if (!r.ok) {
    const body = await r.text();
    throw new Error(`Flask agent error: ${r.status} ${body.slice(0, 500)}`);
  }

  const textStream = r.body;
  if (!textStream) return '';

  const decoder = new TextDecoder();
  let buffer = '';
  let finalAnswer = '';

  const emitEvent = async (ev: unknown) => {
    // The backend emits plain JSON event objects, not SSE "event:" frames.
    if (!ev || typeof ev !== 'object') return;
    await req.onEvent?.(ev as any);
    const e = ev as { type?: string; answer?: unknown };
    if (e.type === 'done' && typeof e.answer === 'string') {
      finalAnswer = e.answer;
    }
  };

  // Parse incremental `data: <json>\n\n` frames.
  const reader = textStream.getReader();
  while (true) {
    const { value, done } = await reader.read();
    if (done) break;

    buffer += decoder.decode(value, { stream: true });

    while (true) {
      const frameEnd = buffer.indexOf('\n\n');
      if (frameEnd === -1) break;

      const frame = buffer.slice(0, frameEnd);
      buffer = buffer.slice(frameEnd + 2);

      const dataLines = frame
        .split('\n')
        .map((l) => l.trim())
        .filter((l) => l.startsWith('data:'));

      for (const dl of dataLines) {
        const payload = dl.replace(/^data:\s*/, '');
        if (!payload) continue;
        try {
          const ev = JSON.parse(payload) as unknown;
          await emitEvent(ev);
        } catch {
          // Ignore non-JSON frames defensively.
        }
      }
    }
  }

  return finalAnswer;
}

export async function runAgentViaFlask(req: AgentRunRequest): Promise<string> {
  return runAgentViaFlaskStream(req);
}

export async function sendToolApprovalToFlask(
  params: { runId: string; decision: ApprovalDecision },
): Promise<void> {
  const base = flaskBaseUrl();
  if (!base) throw new Error('Flask agent URL not configured');

  const r = await fetch(`${base}/api/agent/approval`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      runId: params.runId,
      decision: params.decision,
    }),
  });

  if (!r.ok) {
    const body = await r.text().catch(() => '');
    throw new Error(`Flask approval error: ${r.status} ${body.slice(0, 500)}`);
  }
}

export async function cancelFlaskRun(runId: string): Promise<void> {
  const base = flaskBaseUrl();
  if (!base) throw new Error('Flask agent URL not configured');

  const r = await fetch(`${base}/api/agent/cancel`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ runId }),
  });

  // Best-effort: if endpoint isn’t implemented yet, don’t fail the whole UI.
  if (!r.ok) return;
}
