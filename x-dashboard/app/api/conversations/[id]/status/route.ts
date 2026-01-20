import { NextResponse } from "next/server";

import { updateConversationStatus } from "@/lib/db";

type Params = {
  params: { id: string };
};

export async function POST(request: Request, { params }: Params) {
  const body = await request.json();
  const conversationId = Number(params.id);
  if (Number.isNaN(conversationId)) {
    return NextResponse.json({ error: "Invalid conversation id" }, { status: 400 });
  }
  if (typeof body.status !== "string") {
    return NextResponse.json({ error: "Missing status" }, { status: 400 });
  }
  updateConversationStatus(conversationId, body.status);
  return NextResponse.json({ ok: true });
}
