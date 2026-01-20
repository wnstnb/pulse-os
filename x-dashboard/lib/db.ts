import Database from "better-sqlite3";
import path from "path";

const dbPath =
  process.env.X_AGENT_OS_DB_PATH ??
  path.resolve(process.cwd(), "..", "data", "x_agent_os.db");

const globalForDb = global as unknown as { _db?: Database.Database };
const db = globalForDb._db ?? new Database(dbPath);
if (process.env.NODE_ENV !== "production") {
  globalForDb._db = db;
}

export type DailyBrief = {
  id: number;
  date: string;
  content_md: string;
  summary_json: Record<string, unknown> | null;
  created_at: string;
};

export type Post = {
  id: number;
  session_id: number | null;
  skill_slug: string | null;
  platform: string;
  kind: string;
  source: string;
  draft_content: string;
  published_content: string | null;
  typefully_draft_id: string | null;
  x_tweet_id: string | null;
  x_thread_root_id: string | null;
  planned_for: string | null;
  published_at: string | null;
  metadata_json: Record<string, unknown> | null;
  created_at: string;
  updated_at: string;
};

export type Conversation = {
  id: number;
  session_id: number | null;
  skill_slug: string | null;
  x_tweet_url: string;
  x_tweet_id: string | null;
  author_handle: string | null;
  author_followers: number | null;
  snippet: string | null;
  reason: string | null;
  suggested_reply: string | null;
  status: string;
  created_at: string;
  updated_at: string;
};

export type Skill = {
  id: number;
  slug: string;
  name: string;
  type: string;
  status: string;
  priority: number;
  config_json: Record<string, unknown>;
  created_at: string;
  updated_at: string;
};

export function getTodayBrief(date: string): DailyBrief | null {
  const row = db
    .prepare("SELECT * FROM daily_briefs WHERE date = ?")
    .get(date) as DailyBrief | undefined;
  if (!row) return null;
  return {
    ...row,
    summary_json: row.summary_json ? JSON.parse(String(row.summary_json)) : null
  };
}

export function getPendingPosts(): Post[] {
  const rows = db
    .prepare("SELECT * FROM posts WHERE published_at IS NULL ORDER BY created_at DESC")
    .all() as Post[];
  return rows.map((row) => ({
    ...row,
    metadata_json: row.metadata_json ? JSON.parse(String(row.metadata_json)) : null
  }));
}

export function getPendingConversations(): Conversation[] {
  return db
    .prepare("SELECT * FROM conversations WHERE status = 'pending' ORDER BY created_at DESC")
    .all() as Conversation[];
}

export function getSkills(): Skill[] {
  const rows = db
    .prepare("SELECT * FROM skills ORDER BY priority DESC, name ASC")
    .all() as Skill[];
  return rows.map((row) => ({
    ...row,
    config_json: JSON.parse(String(row.config_json))
  }));
}

export function getSkillBySlug(slug: string): Skill | null {
  const row = db
    .prepare("SELECT * FROM skills WHERE slug = ?")
    .get(slug) as Skill | undefined;
  if (!row) return null;
  return {
    ...row,
    config_json: JSON.parse(String(row.config_json))
  };
}

export function updatePostContent(postId: number, draftContent: string) {
  db.prepare("UPDATE posts SET draft_content = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?")
    .run(draftContent, postId);
}

export function markPostApproved(postId: number) {
  const row = db.prepare("SELECT metadata_json FROM posts WHERE id = ?").get(postId) as {
    metadata_json?: string | null;
  };
  const metadata = row?.metadata_json ? JSON.parse(String(row.metadata_json)) : {};
  metadata.approved = true;
  metadata.approved_at = new Date().toISOString();
  db.prepare("UPDATE posts SET metadata_json = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?").run(
    JSON.stringify(metadata),
    postId
  );
}

export function updateConversationStatus(conversationId: number, status: string) {
  db.prepare("UPDATE conversations SET status = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?")
    .run(status, conversationId);
}

export function updateSkillConfig(slug: string, configJson: Record<string, unknown>) {
  db.prepare("UPDATE skills SET config_json = ?, updated_at = CURRENT_TIMESTAMP WHERE slug = ?")
    .run(JSON.stringify(configJson), slug);
}
