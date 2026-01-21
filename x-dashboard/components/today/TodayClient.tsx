"use client";

import { useEffect, useMemo, useRef, useState } from "react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardFooter, CardHeader } from "@/components/ui/card";
import { Textarea } from "@/components/ui/textarea";
import type { Conversation, DailyBrief, Post } from "@/lib/db";

type TaskItem = {
  key: string;
  type: "post" | "conversation";
  title: string;
  subtitle: string;
  preview: string;
  post?: Post;
  conversation?: Conversation;
};

type Props = {
  brief: DailyBrief | null;
  posts: Post[];
  conversations: Conversation[];
};

const PREVIEW_LIMIT = 140;
const MIN_WIDTH = 280;
const MAX_WIDTH = 520;

function previewText(text: string, limit: number) {
  const chars = Array.from(text ?? "");
  if (chars.length <= limit) {
    return chars.join("");
  }
  return `${chars.slice(0, limit).join("")}...`;
}

function buildTasks(posts: Post[], conversations: Conversation[]): TaskItem[] {
  const postTasks = posts.map((post) => ({
    key: `post-${post.id}`,
    type: "post" as const,
    title: post.skill_slug || "unspecified skill",
    subtitle: `${post.kind} • ${post.platform}`,
    preview: previewText(post.draft_content, PREVIEW_LIMIT),
    post
  }));

  const convoTasks = conversations.map((conversation) => ({
    key: `conversation-${conversation.id}`,
    type: "conversation" as const,
    title: conversation.skill_slug || "unspecified skill",
    subtitle: conversation.author_handle || "unknown author",
    preview: previewText(conversation.snippet || "", PREVIEW_LIMIT),
    conversation
  }));

  return [...postTasks, ...convoTasks];
}

export function TodayClient({ brief, posts, conversations }: Props) {
  const tasks = useMemo(() => buildTasks(posts, conversations), [posts, conversations]);
  const [selectedKey, setSelectedKey] = useState<string | null>(tasks[0]?.key ?? null);
  const [listWidth, setListWidth] = useState(360);
  const resizingRef = useRef<{ startX: number; startWidth: number } | null>(null);

  useEffect(() => {
    if (!tasks.find((task) => task.key === selectedKey)) {
      setSelectedKey(tasks[0]?.key ?? null);
    }
  }, [tasks, selectedKey]);

  const selectedTask = tasks.find((task) => task.key === selectedKey);

  useEffect(() => {
    function onPointerMove(event: PointerEvent) {
      if (!resizingRef.current) return;
      const delta = event.clientX - resizingRef.current.startX;
      const next = resizingRef.current.startWidth + delta;
      setListWidth(Math.min(MAX_WIDTH, Math.max(MIN_WIDTH, next)));
    }

    function onPointerUp() {
      resizingRef.current = null;
      window.removeEventListener("pointermove", onPointerMove);
      window.removeEventListener("pointerup", onPointerUp);
    }

    if (resizingRef.current) {
      window.addEventListener("pointermove", onPointerMove);
      window.addEventListener("pointerup", onPointerUp);
    }

    return () => {
      window.removeEventListener("pointermove", onPointerMove);
      window.removeEventListener("pointerup", onPointerUp);
    };
  }, [resizingRef.current]);

  function onResizeStart(event: React.PointerEvent<HTMLDivElement>) {
    resizingRef.current = { startX: event.clientX, startWidth: listWidth };
    (event.target as HTMLElement).setPointerCapture(event.pointerId);
  }

  return (
    <div className="flex h-[calc(100vh-7rem)] min-h-0 gap-4">
      <section
        className="space-y-4 overflow-y-auto pr-2"
        style={{ width: listWidth }}
      >
        <details open className="space-y-3">
          <summary className="sticky top-0 z-10 cursor-pointer bg-slate-950 py-2 text-xs uppercase tracking-wide text-slate-500">
            Publish These ({posts.length})
          </summary>
          {posts.map((post) => {
            const key = `post-${post.id}`;
            const isActive = selectedKey === key;
            return (
              <Card
                key={key}
                className={isActive ? "border-blue-400" : "border-slate-800"}
              >
                <button
                  className="w-full text-left"
                  onClick={() => setSelectedKey(key)}
                >
                  <CardHeader className="space-y-1">
                    <div className="flex items-center justify-between">
                      <div className="text-sm font-semibold text-slate-200">
                        {post.skill_slug || "unspecified skill"}
                      </div>
                      <Badge>{post.kind}</Badge>
                    </div>
                    <div className="text-xs text-slate-400">{post.platform}</div>
                  </CardHeader>
                  <CardContent className="text-xs text-slate-400">
                    {previewText(post.draft_content, PREVIEW_LIMIT)}
                  </CardContent>
                </button>
              </Card>
            );
          })}
        </details>

        <details open className="space-y-3">
          <summary className="sticky top-0 z-10 cursor-pointer bg-slate-950 py-2 text-xs uppercase tracking-wide text-slate-500">
            Join These Conversations ({conversations.length})
          </summary>
          {conversations.map((conversation) => {
            const key = `conversation-${conversation.id}`;
            const isActive = selectedKey === key;
            return (
              <Card
                key={key}
                className={isActive ? "border-blue-400" : "border-slate-800"}
              >
                <button
                  className="w-full text-left"
                  onClick={() => setSelectedKey(key)}
                >
                  <CardHeader className="space-y-1">
                    <div className="flex items-center justify-between">
                      <div className="text-sm font-semibold text-slate-200">
                        {conversation.skill_slug || "unspecified skill"}
                      </div>
                      <Badge>conversation</Badge>
                    </div>
                    <div className="text-xs text-slate-400">
                      {conversation.author_handle || "unknown author"}
                    </div>
                  </CardHeader>
                  <CardContent className="text-xs text-slate-400">
                    {previewText(conversation.snippet || "", PREVIEW_LIMIT)}
                  </CardContent>
                </button>
              </Card>
            );
          })}
        </details>
      </section>

      <div
        className="w-1 cursor-col-resize rounded-full bg-slate-800/70 hover:bg-slate-600/80"
        onPointerDown={onResizeStart}
        role="separator"
        aria-orientation="vertical"
      />

      <section className="flex-1 space-y-4 overflow-y-auto pr-2">
        {!selectedTask ? (
          <Card>
            <CardHeader>
              <div className="text-sm text-slate-200">Daily Brief Summary</div>
            </CardHeader>
            <CardContent className="space-y-2 text-sm text-slate-300">
              {brief?.summary_json ? (
                <pre className="whitespace-pre-wrap rounded-md bg-slate-900 p-3 text-xs text-slate-200">
                  {JSON.stringify(brief.summary_json, null, 2)}
                </pre>
              ) : (
                <p>No brief found for today. Run the agent-service daily pipeline.</p>
              )}
            </CardContent>
          </Card>
        ) : selectedTask.type === "post" && selectedTask.post ? (
          <PostDetail key={selectedTask.post.id} post={selectedTask.post} />
        ) : selectedTask.type === "conversation" && selectedTask.conversation ? (
          <ConversationDetail
            key={selectedTask.conversation.id}
            conversation={selectedTask.conversation}
          />
        ) : null}
      </section>
    </div>
  );
}

function PostDetail({ post }: { post: Post }) {
  const [draft, setDraft] = useState(post.draft_content);
  const [saving, setSaving] = useState(false);
  const [approved, setApproved] = useState(Boolean(post.metadata_json?.approved));

  useEffect(() => {
    setDraft(post.draft_content);
    setApproved(Boolean(post.metadata_json?.approved));
  }, [post.id, post.draft_content, post.metadata_json]);

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
      <CardHeader className="space-y-1">
        <div className="text-lg font-semibold text-white">
          {post.skill_slug || "unspecified skill"}
        </div>
        <div className="text-xs text-slate-400">
          {post.kind} • {post.platform}
        </div>
        {approved ? <Badge className="w-fit bg-emerald-500 text-white">Approved</Badge> : null}
      </CardHeader>
      <CardContent className="space-y-3">
        <Textarea
          className="min-h-[280px]"
          value={draft}
          onChange={(event) => setDraft(event.target.value)}
        />
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

function ConversationDetail({ conversation }: { conversation: Conversation }) {
  const [reply, setReply] = useState(conversation.suggested_reply || "");
  const [updating, setUpdating] = useState(false);
  const [status, setStatus] = useState(conversation.status);
  const [generating, setGenerating] = useState(false);

  useEffect(() => {
    setReply(conversation.suggested_reply || "");
    setStatus(conversation.status);
  }, [conversation.id, conversation.suggested_reply, conversation.status]);

  async function saveReply() {
    setUpdating(true);
    await fetch(`/api/conversations/${conversation.id}`, {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ suggested_reply: reply })
    });
    setUpdating(false);
  }

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

  async function generateReply() {
    setGenerating(true);
    const res = await fetch(`/api/conversations/${conversation.id}/generate`, {
      method: "POST"
    });
    if (res.ok) {
      const data = await res.json();
      if (typeof data.reply === "string") {
        setReply(data.reply);
      }
    }
    setGenerating(false);
  }

  return (
    <Card>
      <CardHeader className="space-y-1">
        <div className="text-lg font-semibold text-white">
          {conversation.skill_slug || "unspecified skill"}
        </div>
        <div className="text-xs text-slate-400">{conversation.author_handle || "unknown author"}</div>
        {conversation.x_tweet_url ? (
          <a className="text-xs text-blue-300 underline" href={conversation.x_tweet_url} target="_blank">
            View tweet
          </a>
        ) : null}
        <div className="text-sm text-slate-300">{conversation.snippet}</div>
      </CardHeader>
      <CardContent className="space-y-4">
        <div className="rounded-md border border-slate-800 bg-slate-900 p-3 text-sm text-slate-200">
          <div className="text-xs uppercase tracking-wide text-slate-500">Referenced Tweet</div>
          <p className="mt-2 whitespace-pre-wrap text-slate-200">
            {conversation.snippet || "No tweet snippet available."}
          </p>
          {conversation.x_tweet_url ? (
            <a
              className="mt-2 inline-block text-xs text-blue-300 underline"
              href={conversation.x_tweet_url}
              target="_blank"
            >
              Open tweet
            </a>
          ) : null}
        </div>
        <Textarea
          className="min-h-[280px]"
          value={reply}
          onChange={(event) => setReply(event.target.value)}
        />
      </CardContent>
      <CardFooter className="flex flex-wrap items-center justify-between gap-2">
        <div className="text-xs text-slate-400">Status: {status}</div>
        <div className="flex flex-wrap gap-2">
          <Button variant="outline" onClick={generateReply} disabled={generating}>
            {generating ? "Generating..." : "Generate Reply"}
          </Button>
          <Button variant="outline" onClick={saveReply} disabled={updating}>
            Save Reply
          </Button>
          <Button variant="outline" onClick={() => updateStatus("skipped")} disabled={updating}>
            Skip
          </Button>
          <Button onClick={() => updateStatus("replied")} disabled={updating || status === "replied"}>
            Mark Replied
          </Button>
        </div>
      </CardFooter>
    </Card>
  );
}
