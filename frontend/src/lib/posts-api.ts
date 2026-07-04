import { apiRequest, apiRequestEnvelope } from "@/lib/api";

export type SortOption = "latest" | "trending";

export interface PostSummary {
  id: string;
  author_id: string;
  title: string;
  body: string;
  comment_count: number;
  view_count: number;
  solution_comment_id: string | null;
  created_at: string;
}

export interface CommentOut {
  id: string;
  post_id: string;
  author_id: string;
  body: string;
  created_at: string;
}

export interface PostDetail extends PostSummary {
  comments: CommentOut[];
}

export interface PageMeta {
  page: number;
  limit: number;
  total: number;
  total_pages: number;
}

export interface PostListResult {
  posts: PostSummary[];
  meta: PageMeta;
}

export async function fetchPosts(
  token: string,
  { sort, page, limit = 20 }: { sort: SortOption; page: number; limit?: number },
): Promise<PostListResult> {
  const params = new URLSearchParams({ sort, page: String(page), limit: String(limit) });
  const envelope = await apiRequestEnvelope<PostSummary[]>(`/posts?${params.toString()}`, {
    token,
  });
  return { posts: envelope.data, meta: envelope.meta as unknown as PageMeta };
}

export function fetchPost(token: string, postId: string): Promise<PostDetail> {
  return apiRequest<PostDetail>(`/posts/${postId}`, { token });
}

export function createPost(
  token: string,
  input: { title: string; body: string },
): Promise<PostSummary> {
  return apiRequest<PostSummary>("/posts", { method: "POST", body: input, token });
}

export function createComment(token: string, postId: string, body: string): Promise<CommentOut> {
  return apiRequest<CommentOut>(`/posts/${postId}/comments`, {
    method: "POST",
    body: { body },
    token,
  });
}

export function markSolution(
  token: string,
  postId: string,
  commentId: string,
): Promise<PostSummary> {
  return apiRequest<PostSummary>(`/posts/${postId}/solution`, {
    method: "POST",
    body: { comment_id: commentId },
    token,
  });
}
