import { Card, CardContent, CardHeader } from "@/components/ui/card";
import { ConversationCard } from "@/components/today/ConversationCard";
import { PostCard } from "@/components/today/PostCard";
import {
  getPendingConversations,
  getPendingPosts,
  getTodayBrief
} from "@/lib/db";

export default function TodayPage() {
  const date = new Date().toISOString().slice(0, 10);
  const brief = getTodayBrief(date);
  const posts = getPendingPosts();
  const conversations = getPendingConversations();

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-semibold text-white">Today</h1>
        <p className="text-sm text-slate-400">Daily brief and execution queue</p>
      </div>

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

      <section className="space-y-4">
        <div>
          <h2 className="text-lg font-semibold text-white">Publish These</h2>
          <p className="text-sm text-slate-400">{posts.length} pending posts</p>
        </div>
        <div className="grid gap-4 lg:grid-cols-2">
          {posts.map((post) => (
            <PostCard key={post.id} post={post} />
          ))}
        </div>
      </section>

      <section className="space-y-4">
        <div>
          <h2 className="text-lg font-semibold text-white">Join These Conversations</h2>
          <p className="text-sm text-slate-400">
            {conversations.length} opportunities
          </p>
        </div>
        <div className="grid gap-4 lg:grid-cols-2">
          {conversations.map((conversation) => (
            <ConversationCard key={conversation.id} conversation={conversation} />
          ))}
        </div>
      </section>
    </div>
  );
}
