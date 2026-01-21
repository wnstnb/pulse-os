import { NextResponse } from "next/server";

import { markPostApproved, updatePostContent } from "@/lib/db";

type Params = {
  params: { id: string };
};

export async function PATCH(request: Request, { params }: Params) {
  try {
    const body = await request.json();
    const postId = Number(params.id);

    if (Number.isNaN(postId)) {
      return NextResponse.json({ error: "Invalid post id" }, { status: 400 });
    }

    if (typeof body.draft_content === "string") {
      updatePostContent(postId, body.draft_content);
    }

    if (body.approved === true) {
      markPostApproved(postId);
    }

    return NextResponse.json({ ok: true });
  } catch (error) {
    return NextResponse.json(
      { error: "Posts table not ready. Run the daily pipeline first." },
      { status: 503 }
    );
  }
}
