"use client";

import { useUser } from "@clerk/nextjs";
import { useState, useEffect } from "react";
import { getProfile, Profile } from "@/lib/db";

export function useProfile() {
  const { user, isSignedIn } = useUser();
  const [profile, setProfile] = useState<Profile | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (isSignedIn && user) {
      getProfile(user.id)
        .then((data) => setProfile(data))
        .catch(() => {})
        .finally(() => setLoading(false));
    } else {
      setLoading(false);
    }
  }, [isSignedIn, user]);

  return { profile, loading, isSignedIn };
}
