"use client";

import { type FormEvent, useState } from "react";

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { useCreatePost } from "@/hooks/use-create-post";

export default function CreatePostPage() {
  const [title, setTitle] = useState("");
  const [body, setBody] = useState("");
  const { mutate, isPending } = useCreatePost();

  function handleSubmit(event: FormEvent) {
    event.preventDefault();
    mutate({ title, body });
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle>Create post</CardTitle>
        <CardDescription>Share something with the community.</CardDescription>
      </CardHeader>
      <CardContent>
        <form className="flex flex-col gap-4" onSubmit={handleSubmit}>
          <div className="flex flex-col gap-1.5">
            <Label htmlFor="title">Title</Label>
            <Input
              id="title"
              required
              maxLength={200}
              value={title}
              onChange={(event) => setTitle(event.target.value)}
            />
          </div>
          <div className="flex flex-col gap-1.5">
            <Label htmlFor="body">Body</Label>
            <Textarea
              id="body"
              required
              rows={8}
              maxLength={10_000}
              value={body}
              onChange={(event) => setBody(event.target.value)}
            />
          </div>
          <Button type="submit" disabled={isPending} className="self-start">
            {isPending ? "Publishing..." : "Publish"}
          </Button>
        </form>
      </CardContent>
    </Card>
  );
}
