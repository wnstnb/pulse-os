import { execFile } from "child_process";
import path from "path";
import { promisify } from "util";

import { NextResponse } from "next/server";

const execFileAsync = promisify(execFile);

type Params = {
  params: { id: string };
};

export async function POST(request: Request, { params }: Params) {
  try {
    const conversationId = Number(params.id);
    if (Number.isNaN(conversationId)) {
      return NextResponse.json({ error: "Invalid conversation id" }, { status: 400 });
    }

    const repoRoot = path.resolve(process.cwd(), "..");
    const scriptPath = path.join(repoRoot, "agent-service", "run_generate_reply.py");
    const pythonPath = process.env.PYTHON || "python";
    const dbPath =
      process.env.X_AGENT_OS_DB_PATH ?? path.join(repoRoot, "data", "x_agent_os.db");

    const { stdout } = await execFileAsync(
      pythonPath,
      [scriptPath, "--conversation-id", String(conversationId)],
      {
        cwd: path.join(repoRoot, "agent-service"),
        env: {
          ...process.env,
          X_AGENT_OS_DB_PATH: dbPath
        }
      }
    );

    const payload = JSON.parse(stdout.trim());
    return NextResponse.json({ reply: payload.reply });
  } catch (error) {
    const message = error instanceof Error ? error.message : String(error);
    return NextResponse.json(
      {
        error: "Failed to generate reply. Check Python env + API key.",
        detail: message
      },
      { status: 500 }
    );
  }
}
