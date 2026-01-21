import { execFile } from "child_process";
import path from "path";
import { promisify } from "util";

import { NextResponse } from "next/server";

const execFileAsync = promisify(execFile);

export async function POST(request: Request) {
  try {
    const body = await request.json();
    const handle = typeof body.handle === "string" ? body.handle : null;
    if (!handle) {
      return NextResponse.json({ error: "Missing handle" }, { status: 400 });
    }

    const windowDays = typeof body.windowDays === "number" ? body.windowDays : 30;
    const limit = typeof body.limit === "number" ? body.limit : 50;
    const topN = typeof body.topN === "number" ? body.topN : 7;
    const force = body.force === true;

    const repoRoot = path.resolve(process.cwd(), "..");
    const scriptPath = path.join(repoRoot, "agent-service", "run_creator_persona.py");
    const pythonPath = process.env.PYTHON || "python";
    const dbPath =
      process.env.X_AGENT_OS_DB_PATH ?? path.join(repoRoot, "data", "x_agent_os.db");

    const { stdout } = await execFileAsync(
      pythonPath,
      [
        scriptPath,
        "--username",
        handle,
        "--window-days",
        String(windowDays),
        "--limit",
        String(limit),
        "--top-n",
        String(topN),
        ...(force ? ["--force"] : [])
      ],
      {
        cwd: path.join(repoRoot, "agent-service"),
        env: {
          ...process.env,
          X_AGENT_OS_DB_PATH: dbPath
        }
      }
    );

    let parsed: unknown;
    try {
      parsed = JSON.parse(stdout.trim());
    } catch (parseError) {
      return NextResponse.json(
        {
          error: "Failed to parse persona capture output.",
          detail: stdout.trim().slice(0, 500)
        },
        { status: 502 }
      );
    }

    return NextResponse.json({ ok: true, result: parsed });
  } catch (error) {
    const message = error instanceof Error ? error.message : String(error);
    return NextResponse.json(
      { error: "Failed to run creator persona capture.", detail: message },
      { status: 500 }
    );
  }
}
