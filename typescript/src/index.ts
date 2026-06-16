export class OrkaPolicyBlocked extends Error {
  constructor(public reason: string, public policyName?: string) {
    super(`Blocked by policy: ${reason}`);
    this.name = "OrkaPolicyBlocked";
  }
}

export class OrkaAuthError extends Error {
  constructor() { super("Invalid API key"); this.name = "OrkaAuthError"; }
}

export class OrkaConnectionError extends Error {
  constructor(url: string) { super(`Cannot reach Orka at ${url}`); this.name = "OrkaConnectionError"; }
}

type RiskLevel = "UNACCEPTABLE" | "HIGH" | "LIMITED" | "MINIMAL" | "NONE";

interface GuardOptions {
  agentId: string;
  taskType: string;
  risk?: RiskLevel;
  blockOnPolicy?: boolean;
}

class OrkaClient {
  constructor(
    private apiKey: string,
    private baseUrl: string = "https://orka-backend.onrender.com/api/v1"
  ) {}

  private get headers() {
    return { Authorization: `Bearer ${this.apiKey}`, "Content-Type": "application/json" };
  }

  private async request(method: string, path: string, body?: unknown): Promise<unknown> {
    let res: Response;
    try {
      res = await fetch(`${this.baseUrl}${path}`, {
        method,
        headers: this.headers,
        body: body ? JSON.stringify(body) : undefined,
        signal: AbortSignal.timeout(10_000),
      });
    } catch {
      throw new OrkaConnectionError(this.baseUrl);
    }
    if (res.status === 401) throw new OrkaAuthError();
    if (res.status === 403) {
      const data = await res.json().catch(() => ({})) as Record<string, string>;
      throw new OrkaPolicyBlocked(data.reason ?? "Policy denied", data.policy_name);
    }
    return res.ok ? (res.headers.get("content-length") !== "0" ? res.json() : {}) : {};
  }

  async checkPolicy(agentId: string, taskType: string, payload: unknown) {
    return this.request("POST", "/xshield/check", { agent_id: agentId, task_type: taskType, payload });
  }

  async logExecution(agentId: string, taskType: string, status: string,
    inputPayload: unknown, outputPayload?: unknown, error?: string, durationMs?: number) {
    return this.request("POST", "/executions", {
      requesting_agent_id: agentId, executing_agent_target: agentId,
      task_type: taskType, task_payload: inputPayload,
      status, output_payload: outputPayload, error, duration_ms: durationMs,
    });
  }
}

let _client: OrkaClient | null = null;

export function init(apiKey: string, baseUrl?: string): OrkaClient {
  _client = new OrkaClient(apiKey, baseUrl);
  return _client;
}

/**
 * Wraps an async function with Orka governance.
 * - Checks X-Shield policies before execution
 * - Logs result to X-Ledger after execution
 *
 * @example
 * const summarize = orka.guard(
 *   async (text: string) => openai.chat(text),
 *   { agentId: "uuid", taskType: "summarize" }
 * );
 */
export function guard<T extends (...args: unknown[]) => Promise<unknown>>(
  fn: T,
  options: GuardOptions
): T {
  const { agentId, taskType, blockOnPolicy = true } = options;

  return (async (...args: unknown[]) => {
    if (!_client) return fn(...args);

    const inputPayload = { args };
    const start = performance.now();
    let status = "COMPLETED";
    let output: unknown;
    let error: string | undefined;

    try {
      await _client.checkPolicy(agentId, taskType, inputPayload);
    } catch (e) {
      if (e instanceof OrkaPolicyBlocked && blockOnPolicy) throw e;
    }

    try {
      output = await fn(...args);
      return output;
    } catch (e) {
      error = e instanceof Error ? e.message : String(e);
      status = "FAILED";
      throw e;
    } finally {
      const durationMs = Math.round(performance.now() - start);
      _client.logExecution(agentId, taskType, status, inputPayload,
        output !== undefined ? String(output) : undefined, error, durationMs
      ).catch(() => {});
    }
  }) as T;
}

export default { init, guard };
