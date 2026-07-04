"use client";

import { LogOutIcon, MessageSquareIcon, TrophyIcon, UserIcon } from "lucide-react";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useState } from "react";

import { ThemeToggle } from "@/components/theme-toggle";
import { Avatar, AvatarFallback } from "@/components/ui/avatar";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { Skeleton } from "@/components/ui/skeleton";
import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";
import { useAuth } from "@/lib/auth-context";

const NAV_ITEMS = [
  { href: "/feed", label: "Feed", icon: MessageSquareIcon },
  { href: "/challenges", label: "Challenges", icon: TrophyIcon },
  { href: "/profile", label: "Profile", icon: UserIcon },
];

export function Sidebar() {
  const pathname = usePathname();
  const router = useRouter();
  const { user, status, logout } = useAuth();
  const [confirmOpen, setConfirmOpen] = useState(false);

  return (
    <aside className="border-border bg-sidebar text-sidebar-foreground flex h-full w-16 shrink-0 flex-col justify-between border-r p-3 md:w-60 md:p-4">
      <div className="flex flex-col gap-6">
        <Link href="/feed" className="flex items-center gap-2 px-1">
          <span className="brand-gradient-bg flex size-7 shrink-0 items-center justify-center rounded-lg text-sm font-bold text-white shadow-sm">
            V
          </span>
          <span className="hidden truncate text-sm font-semibold tracking-tight md:inline">
            Vultr Community
          </span>
        </Link>
        <nav className="flex flex-col gap-1">
          {NAV_ITEMS.map((item) => {
            const active = pathname.startsWith(item.href);
            const Icon = item.icon;
            return (
              <Tooltip key={item.href}>
                <TooltipTrigger
                  render={
                    <Link
                      href={item.href}
                      className={cn(
                        "flex items-center gap-2.5 rounded-lg px-2.5 py-2 text-sm font-medium transition-colors",
                        active
                          ? "bg-primary text-primary-foreground shadow-sm"
                          : "text-muted-foreground hover:bg-accent hover:text-foreground",
                      )}
                    />
                  }
                >
                  <Icon className="size-4 shrink-0" />
                  <span className="hidden truncate md:inline">{item.label}</span>
                </TooltipTrigger>
                <TooltipContent className="md:hidden">{item.label}</TooltipContent>
              </Tooltip>
            );
          })}
        </nav>
      </div>

      <div className="flex flex-col gap-2">
        <div className="hidden items-center justify-between px-1 md:flex">
          <span className="text-muted-foreground text-xs font-medium">Theme</span>
          <ThemeToggle />
        </div>
        <div className="flex items-center justify-center md:hidden">
          <ThemeToggle />
        </div>

        {status === "loading" ? (
          <div className="flex items-center gap-2">
            <Skeleton className="size-8 shrink-0 rounded-full" />
            <Skeleton className="hidden h-3.5 w-24 md:block" />
          </div>
        ) : user ? (
          <>
            <DropdownMenu>
              <DropdownMenuTrigger className="hover:bg-accent flex w-full items-center gap-2 rounded-lg p-1.5 text-left transition-colors">
                <Avatar className="ring-border size-8 ring-1">
                  <AvatarFallback className="brand-gradient-bg text-white">
                    {user.email.slice(0, 2).toUpperCase()}
                  </AvatarFallback>
                </Avatar>
                <span className="hidden truncate text-sm md:inline">{user.email}</span>
              </DropdownMenuTrigger>
              <DropdownMenuContent align="start">
                <DropdownMenuItem
                  variant="destructive"
                  onClick={() => setConfirmOpen(true)}
                >
                  <LogOutIcon />
                  Log out
                </DropdownMenuItem>
              </DropdownMenuContent>
            </DropdownMenu>

            <Dialog open={confirmOpen} onOpenChange={setConfirmOpen}>
              <DialogContent>
                <DialogHeader>
                  <DialogTitle>Log out?</DialogTitle>
                  <DialogDescription>
                    You&apos;ll need to sign back in to see your feed, challenges, and rewards.
                  </DialogDescription>
                </DialogHeader>
                <DialogFooter>
                  <Button variant="outline" onClick={() => setConfirmOpen(false)}>
                    Cancel
                  </Button>
                  <Button
                    variant="destructive"
                    onClick={() => {
                      logout();
                      router.push("/login");
                    }}
                  >
                    Log out
                  </Button>
                </DialogFooter>
              </DialogContent>
            </Dialog>
          </>
        ) : null}
      </div>
    </aside>
  );
}
