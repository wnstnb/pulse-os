import { TodayClient } from "@/components/today/TodayClient";
import { getPendingConversations, getPendingPosts, getTodayBrief } from "@/lib/db";

export default function TodayPage() {
  const date = new Date().toISOString().slice(0, 10);
  const brief = getTodayBrief(date);
  const posts = getPendingPosts();
  const conversations = getPendingConversations();

  return <TodayClient brief={brief} posts={posts} conversations={conversations} />;
}
