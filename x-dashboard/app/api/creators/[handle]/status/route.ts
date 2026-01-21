import { NextResponse } from "next/server";

import { updateCreatorPersonaStatus } from "@/lib/db";

type Params = {
  params: { handle: string };
};

export async function PATCH(request: Request, { params }: Params) {
  try {
    const body = await request.json();
    if (typeof body.status !== "string") {
      return NextResponse.json({ error: "Missing status" }, { status: 400 });
    }
    updateCreatorPersonaStatus(params.handle, body.status);
    return NextResponse.json({ ok: true });
  } catch (error) {
    return NextResponse.json(
      { error: "Creator personas table not ready." },
      { status: 503 }
    );
  }
}
