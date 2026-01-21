import { NextResponse } from "next/server";

import { updateConversationReply } from "@/lib/db";

type Params = {
  params: { id: string };
};

export async function PATCH(request: Request, { params }: Params) {
  try {
    const body = await request.json();
    const conversationId = Number(params.id);
    if (Number.isNaN(conversationId)) {
      return NextResponse.json({ error: "Invalid conversation id" }, { status: 400 });
    }
    if (typeof body.suggested_reply !== "string") {
      return NextResponse.json({ error: "Missing suggested_reply" }, { status: 400 });
    }
    updateConversationReply(conversationId, body.suggested_reply);
    return NextResponse.json({ ok: true });
  } catch (error) {
    return NextResponse.json(
      { error: "Conversations table not ready. Run the daily pipeline first." },
      { status: 503 }
    );
  }
}
