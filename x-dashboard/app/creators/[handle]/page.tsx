import Link from "next/link";

import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader } from "@/components/ui/card";
import {
  getCreatorPersonaByHandle,
  getCreatorPersonaPosts,
  getLatestCreatorPersonaRun
} from "@/lib/db";

type Props = {
  params: { handle: string };
};

export default function CreatorPersonaDetailPage({ params }: Props) {
  const persona = getCreatorPersonaByHandle(params.handle);
  if (!persona) {
    return (
      <div className="text-sm text-slate-300">
        Persona not found. Run the persona capture pipeline first.
      </div>
    );
  }

  const latest = getLatestCreatorPersonaRun(persona.handle);
  const posts = getCreatorPersonaPosts(persona.id, 15);

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-semibold text-white">@{persona.handle}</h1>
        <p className="text-sm text-slate-400">
          {persona.display_name || "Creator persona snapshot"}
        </p>
        <div className="mt-2 flex items-center gap-2">
          <Badge>{persona.status}</Badge>
          <Link
            className="text-xs text-blue-300 underline"
            href={`https://x.com/${persona.handle}`}
            target="_blank"
          >
            View on X
          </Link>
        </div>
      </div>

      <Card>
        <CardHeader>
          <div className="text-sm text-slate-200">Persona Summary</div>
          <div className="text-xs text-slate-500">
            Latest run: {latest?.run_at ? new Date(latest.run_at).toLocaleString() : "None"}
          </div>
        </CardHeader>
        <CardContent className="space-y-2 text-sm text-slate-300">
          {latest?.summary_json ? (
            <pre className="whitespace-pre-wrap rounded-md bg-slate-900 p-3 text-xs text-slate-200">
              {JSON.stringify(latest.summary_json, null, 2)}
            </pre>
          ) : (
            <p>No summary found. Run the persona capture pipeline.</p>
          )}
          {latest?.output_md_path ? (
            <div className="text-xs text-slate-500">
              Cached summary: {latest.output_md_path}
            </div>
          ) : null}
        </CardContent>
      </Card>

      <section className="space-y-3">
        <div>
          <h2 className="text-lg font-semibold text-white">Greatest Hits</h2>
          <p className="text-sm text-slate-400">Top posts by engagement score</p>
        </div>
        <div className="grid gap-4 lg:grid-cols-2">
          {posts.map((post) => (
            <Card key={post.id}>
              <CardHeader className="space-y-1">
                <div className="text-sm text-slate-300">
                  Score: {post.engagement_score ?? 0}
                </div>
                <div className="text-xs text-slate-500">{post.created_at}</div>
                {post.tweet_url ? (
                  <Link className="text-xs text-blue-300 underline" href={post.tweet_url} target="_blank">
                    View post
                  </Link>
                ) : null}
              </CardHeader>
              <CardContent className="text-sm text-slate-200">
                {post.content || "No content captured."}
              </CardContent>
            </Card>
          ))}
        </div>
      </section>
    </div>
  );
}
