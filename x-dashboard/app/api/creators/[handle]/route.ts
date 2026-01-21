import { NextResponse } from "next/server";

import Database from "better-sqlite3";
import path from "path";

type Params = {
  params: { handle: string };
};

export async function DELETE(request: Request, { params }: Params) {
  try {
    const dbPath =
      process.env.X_AGENT_OS_DB_PATH ??
      path.resolve(process.cwd(), "..", "data", "x_agent_os.db");
    const db = new Database(dbPath);

    const persona = db
      .prepare("SELECT id FROM creator_personas WHERE handle = ?")
      .get(params.handle) as { id: number } | undefined;
    if (!persona) {
      return NextResponse.json({ ok: false, error: "Not found" }, { status: 404 });
    }

    db.prepare("DELETE FROM creator_persona_posts WHERE persona_id = ?").run(persona.id);
    db.prepare("DELETE FROM creator_persona_runs WHERE persona_id = ?").run(persona.id);
    db.prepare("DELETE FROM creator_personas WHERE id = ?").run(persona.id);
    db.close();

    return NextResponse.json({ ok: true });
  } catch (error) {
    const message = error instanceof Error ? error.message : String(error);
    return NextResponse.json(
      { error: "Failed to delete persona", detail: message },
      { status: 500 }
    );
  }
}
