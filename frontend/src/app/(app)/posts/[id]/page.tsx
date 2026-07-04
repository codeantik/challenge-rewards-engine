interface PostDetailPageProps {
  params: Promise<{ id: string }>;
}

export default async function PostDetailPage({ params }: PostDetailPageProps) {
  const { id } = await params;
  return (
    <div className="flex flex-col gap-2">
      <h1 className="text-lg font-semibold">Post {id}</h1>
      <p className="text-muted-foreground text-sm">
        Nested comments, optimistic comment, and mark-as-solution land in Phase 7.
      </p>
    </div>
  );
}
