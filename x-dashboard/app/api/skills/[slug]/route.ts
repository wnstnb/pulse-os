import { NextResponse } from "next/server";

import { updateSkillConfig } from "@/lib/db";

type Params = {
  params: { slug: string };
};

export async function PATCH(request: Request, { params }: Params) {
  try {
    const body = await request.json();
    if (!body.config_json || typeof body.config_json !== "object") {
      return NextResponse.json({ error: "Invalid config_json" }, { status: 400 });
    }

    updateSkillConfig(params.slug, body.config_json);
    return NextResponse.json({ ok: true });
  } catch (error) {
    return NextResponse.json(
      { error: "Skills table not ready. Run the daily pipeline first." },
      { status: 503 }
    );
  }
}
