import { describe, expect, test, beforeEach, afterEach } from 'vitest';
import { runAgentViaFlask, isFlaskAgentEnabled } from './flask-agent.js';
import type { AgentRunRequest } from './agent-runner.js';

function makeFakeBody(sseText: string) {
  const bytes = Buffer.from(sseText, 'utf8');
  let sent = false;
  return {
    getReader() {
      return {
        async read() {
          if (sent) return { value: undefined, done: true };
          sent = true;
          return { value: bytes, done: false };
        },
      };
    },
  };
}

describe('flask-agent', () => {
  const OLD_ENV = process.env.FLASK_AGENT_URL;
  let fetchCalls: string[] = [];

  beforeEach(() => {
    process.env.FLASK_AGENT_URL = 'http://flask.test';
    fetchCalls = [];
  });

  afterEach(() => {
    if (OLD_ENV === undefined) {
      delete process.env.FLASK_AGENT_URL;
    } else {
      process.env.FLASK_AGENT_URL = OLD_ENV;
    }
    delete (globalThis as any).fetch;
  });

  test('uses /api/agent/stream and forwards SSE events', async () => {
    expect(isFlaskAgentEnabled()).toBe(true);

    const seen: Array<{ type: string }> = [];
    const payload = [
      { type: 'tool_progress', tool: 'dummy', message: 'Running dummy...' },
      { type: 'memory_recalled', filesLoaded: ['daily'], tokenCount: 42 },
      {
        type: 'done',
        answer: 'FINAL',
        toolCalls: [],
        iterations: 1,
        totalTime: 1,
        tokenUsage: null,
        tokensPerSecond: 0,
      },
    ];
    const sseText = payload.map((ev) => `data: ${JSON.stringify(ev)}\n\n`).join('');

    (globalThis as any).fetch = async (url: string) => {
      fetchCalls.push(url);
      return {
        ok: true,
        status: 200,
        body: makeFakeBody(sseText),
        text: async () => '',
      };
    };

    const req: AgentRunRequest = {
      sessionKey: 's1',
      runId: 'r1',
      query: 'hello',
      model: 'gpt-5.4',
      modelProvider: 'openai',
      maxIterations: 2,
      onEvent: (ev) => {
        seen.push(ev as any);
      },
      isolatedSession: false,
    };

    const answer = await runAgentViaFlask(req);
    expect(answer).toBe('FINAL');
    expect(fetchCalls[0]).toContain('/api/agent/stream');
    expect(seen.map((e) => e.type)).toEqual(['tool_progress', 'memory_recalled', 'done']);
  });
});

