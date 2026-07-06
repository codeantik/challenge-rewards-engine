"use client";

import { type FormEvent, useState } from "react";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { NativeSelect } from "@/components/ui/native-select";
import { Textarea } from "@/components/ui/textarea";
import {
  CHALLENGE_PERIODS,
  CHALLENGE_STATUSES,
  CHALLENGE_TYPES,
  EVENT_TYPES,
  type AdminChallenge,
  type ChallengeInput,
  type ChallengePeriod,
  type ChallengeStatus,
  type ChallengeType,
  type EventType,
} from "@/lib/admin-challenges-api";

function humanize(value: string): string {
  return value.replace(/_/g, " ");
}

/** `datetime-local` inputs work in the browser's local wall time, not the
 * fixed forum TZ (UTC) that streak/weekly bucketing uses — that invariant
 * governs how the *engine* buckets event timestamps, not how an admin picks
 * a challenge's start/end window here, so converting through the browser's
 * local time via `Date` is fine. */
function toDatetimeLocal(iso: string | null): string {
  if (!iso) return "";
  const date = new Date(iso);
  const pad = (n: number) => String(n).padStart(2, "0");
  return `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())}T${pad(date.getHours())}:${pad(date.getMinutes())}`;
}

function fromDatetimeLocal(value: string): string | null {
  return value ? new Date(value).toISOString() : null;
}

interface ChallengeFormProps {
  initial?: AdminChallenge;
  onSubmit: (input: ChallengeInput) => void;
  isPending: boolean;
  submitLabel: string;
}

export function ChallengeForm({ initial, onSubmit, isPending, submitLabel }: ChallengeFormProps) {
  const [name, setName] = useState(initial?.name ?? "");
  const [description, setDescription] = useState(initial?.description ?? "");
  const [type, setType] = useState<ChallengeType>((initial?.type as ChallengeType) ?? "count");
  const [eventType, setEventType] = useState<EventType>(
    (initial?.event_type as EventType) ?? "post_created",
  );
  const [ruleValue, setRuleValue] = useState(() => {
    const config = initial?.rule_config ?? {};
    const value = initial?.type === "streak" ? config.length : config.target;
    return typeof value === "number" ? String(value) : "3";
  });
  const [rewardType, setRewardType] = useState(initial?.reward.type ?? "points");
  const [rewardAmount, setRewardAmount] = useState(String(initial?.reward.amount ?? 10));
  const [status, setStatus] = useState<ChallengeStatus>(
    (initial?.status as ChallengeStatus) ?? "draft",
  );
  const [period, setPeriod] = useState<ChallengePeriod>(
    (initial?.period as ChallengePeriod) ?? "one_time",
  );
  const [startAt, setStartAt] = useState(toDatetimeLocal(initial?.start_at ?? null));
  const [endAt, setEndAt] = useState(toDatetimeLocal(initial?.end_at ?? null));

  const ruleKey = type === "streak" ? "length" : "target";

  function handleSubmit(event: FormEvent) {
    event.preventDefault();
    onSubmit({
      name,
      description,
      type,
      event_type: eventType,
      rule_config: { [ruleKey]: Number(ruleValue) },
      reward: { type: rewardType, amount: Number(rewardAmount) },
      status,
      period,
      start_at: fromDatetimeLocal(startAt),
      end_at: fromDatetimeLocal(endAt),
    });
  }

  return (
    <form className="flex flex-col gap-4" onSubmit={handleSubmit}>
      <div className="flex flex-col gap-1.5">
        <Label htmlFor="name">Name</Label>
        <Input
          id="name"
          required
          maxLength={200}
          value={name}
          onChange={(event) => setName(event.target.value)}
        />
      </div>

      <div className="flex flex-col gap-1.5">
        <Label htmlFor="description">Description</Label>
        <Textarea
          id="description"
          rows={3}
          maxLength={2_000}
          value={description}
          onChange={(event) => setDescription(event.target.value)}
        />
      </div>

      <div className="grid grid-cols-2 gap-4">
        <div className="flex flex-col gap-1.5">
          <Label htmlFor="type">Type</Label>
          <NativeSelect
            id="type"
            value={type}
            onChange={(event) => setType(event.target.value as ChallengeType)}
          >
            {CHALLENGE_TYPES.map((option) => (
              <option key={option} value={option}>
                {humanize(option)}
              </option>
            ))}
          </NativeSelect>
        </div>

        <div className="flex flex-col gap-1.5">
          <Label htmlFor="event_type">Event type</Label>
          <NativeSelect
            id="event_type"
            value={eventType}
            onChange={(event) => setEventType(event.target.value as EventType)}
          >
            {EVENT_TYPES.map((option) => (
              <option key={option} value={option}>
                {humanize(option)}
              </option>
            ))}
          </NativeSelect>
        </div>
      </div>

      <div className="flex flex-col gap-1.5">
        <Label htmlFor="rule_value">
          {type === "streak" ? "Streak length (consecutive days)" : "Target count"}
        </Label>
        <Input
          id="rule_value"
          type="number"
          min={1}
          required
          value={ruleValue}
          onChange={(event) => setRuleValue(event.target.value)}
        />
      </div>

      <div className="grid grid-cols-2 gap-4">
        <div className="flex flex-col gap-1.5">
          <Label htmlFor="reward_type">Reward type</Label>
          <Input
            id="reward_type"
            required
            maxLength={50}
            value={rewardType}
            onChange={(event) => setRewardType(event.target.value)}
          />
        </div>
        <div className="flex flex-col gap-1.5">
          <Label htmlFor="reward_amount">Reward amount</Label>
          <Input
            id="reward_amount"
            type="number"
            min={1}
            required
            value={rewardAmount}
            onChange={(event) => setRewardAmount(event.target.value)}
          />
        </div>
      </div>

      <div className="grid grid-cols-2 gap-4">
        <div className="flex flex-col gap-1.5">
          <Label htmlFor="status">Status</Label>
          <NativeSelect
            id="status"
            value={status}
            onChange={(event) => setStatus(event.target.value as ChallengeStatus)}
          >
            {CHALLENGE_STATUSES.map((option) => (
              <option key={option} value={option}>
                {humanize(option)}
              </option>
            ))}
          </NativeSelect>
        </div>
        <div className="flex flex-col gap-1.5">
          <Label htmlFor="period">Period</Label>
          <NativeSelect
            id="period"
            value={period}
            onChange={(event) => setPeriod(event.target.value as ChallengePeriod)}
          >
            {CHALLENGE_PERIODS.map((option) => (
              <option key={option} value={option}>
                {humanize(option)}
              </option>
            ))}
          </NativeSelect>
        </div>
      </div>

      <div className="grid grid-cols-2 gap-4">
        <div className="flex flex-col gap-1.5">
          <Label htmlFor="start_at">Start at (optional)</Label>
          <Input
            id="start_at"
            type="datetime-local"
            value={startAt}
            onChange={(event) => setStartAt(event.target.value)}
          />
        </div>
        <div className="flex flex-col gap-1.5">
          <Label htmlFor="end_at">End at (optional)</Label>
          <Input
            id="end_at"
            type="datetime-local"
            value={endAt}
            onChange={(event) => setEndAt(event.target.value)}
          />
        </div>
      </div>

      <Button type="submit" disabled={isPending} className="self-start">
        {isPending ? "Saving..." : submitLabel}
      </Button>
    </form>
  );
}
