"use client";

import { useState } from "react";

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardFooter, CardHeader } from "@/components/ui/card";
import { Textarea } from "@/components/ui/textarea";
import type { Conversation } from "@/lib/db";

type Props = {
  conversation: Conversation;
};

export function ConversationCard({ conversation }: Props) {
  const [reply, setReply] = useState(conversation.suggested_reply || "");
  const [updating, setUpdating] = useState(false);
  const [status, setStatus] = useState(conversation.status);

  async function updateStatus(nextStatus: string) {
    setUpdating(true);
    await fetch(`/api/conversations/${conversation.id}/status`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ status: nextStatus })
    });
    setStatus(nextStatus);
    setUpdating(false);
  }

  return (
    <Card>
      <CardHeader>
        <div className="text-sm text-slate-200">
          <div className="font-semibold">{conversation.skill_slug || "unspecified skill"}</div>
          <div className="text-xs text-slate-400">{conversation.author_handle || "unknown"}</div>
        </div>
      </CardHeader>
      <CardContent className="space-y-3">
        <div className="text-sm text-slate-300">{conversation.snippet}</div>
        {conversation.x_tweet_url ? (
          <a className="text-xs text-blue-300 underline" href={conversation.x_tweet_url} target="_blank">
            View tweet
          </a>
        ) : null}
        <Textarea value={reply} onChange={(event) => setReply(event.target.value)} />
      </CardContent>
      <CardFooter className="flex items-center justify-between gap-2">
        <Button variant="outline" onClick={() => updateStatus("skipped")} disabled={updating}>
          Skip
        </Button>
        <Button onClick={() => updateStatus("replied")} disabled={updating || status === "replied"}>
          Mark Replied
        </Button>
      </CardFooter>
    </Card>
  );
}
