"use client";

import { useState } from "react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardFooter, CardHeader } from "@/components/ui/card";
import { Textarea } from "@/components/ui/textarea";
import type { Post } from "@/lib/db";

type Props = {
  post: Post;
};

export function PostCard({ post }: Props) {
  const [draft, setDraft] = useState(post.draft_content);
  const [saving, setSaving] = useState(false);
  const [approved, setApproved] = useState(Boolean(post.metadata_json?.approved));

  async function saveEdits() {
    setSaving(true);
    await fetch(`/api/posts/${post.id}`, {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ draft_content: draft })
    });
    setSaving(false);
  }

  async function markApproved() {
    setSaving(true);
    await fetch(`/api/posts/${post.id}`, {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ approved: true })
    });
    setApproved(true);
    setSaving(false);
  }

  return (
    <Card>
      <CardHeader className="flex flex-row items-center justify-between">
        <div className="text-sm text-slate-200">
          <div className="font-semibold">{post.skill_slug || "unspecified skill"}</div>
          <div className="text-xs text-slate-400">
            {post.kind} • {post.platform}
          </div>
        </div>
        {approved ? <Badge className="bg-emerald-500 text-white">Approved</Badge> : null}
      </CardHeader>
      <CardContent>
        <Textarea value={draft} onChange={(event) => setDraft(event.target.value)} />
      </CardContent>
      <CardFooter className="flex items-center justify-between gap-2">
        <Button variant="outline" onClick={saveEdits} disabled={saving}>
          Save Edits
        </Button>
        <Button onClick={markApproved} disabled={saving || approved}>
          Mark Approved
        </Button>
      </CardFooter>
    </Card>
  );
}
