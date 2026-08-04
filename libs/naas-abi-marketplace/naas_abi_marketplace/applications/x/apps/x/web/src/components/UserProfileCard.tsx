"use client";

import { fmt } from "@/lib/format";
import type { UserAccount, UserRow } from "@/lib/types";

type Props = {
  profile: (UserRow & UserAccount) | null;
  username: string;
  timezone: string;
};

/** X serves a 48px avatar by default; the profile card wants the large one. */
function largeAvatar(url: string): string {
  return url.replace(/_normal\.(jpg|jpeg|png|gif|webp)$/i, "_400x400.$1");
}

function formatJoined(iso: string, timezone: string): string {
  try {
    return new Date(iso).toLocaleDateString(undefined, {
      timeZone: timezone,
      year: "numeric",
      month: "long",
    });
  } catch {
    return iso;
  }
}

const METRICS: { key: keyof NonNullable<UserAccount["metrics"]>; label: string }[] =
  [
    { key: "followers_count", label: "Followers" },
    { key: "following_count", label: "Following" },
    { key: "tweet_count", label: "Posts" },
    { key: "listed_count", label: "Listed" },
    { key: "like_count", label: "Likes" },
    { key: "media_count", label: "Media" },
  ];

export function UserProfileCard({ profile, username, timezone }: Props) {
  if (!profile) return null;

  const banner = profile.profile_banner_url || "";
  const avatar = profile.profile_image_url || "";
  const metrics = profile.metrics;
  const hasMetrics =
    metrics && METRICS.some(({ key }) => typeof metrics[key] === "number");

  const badges: string[] = [];
  if (profile.verified_type && profile.verified_type !== "none") {
    badges.push(profile.verified_type);
  }
  if (profile.is_identity_verified) badges.push("id verified");
  if (profile.protected) badges.push("protected");

  return (
    <div className="profile-card">
      {banner ? (
        // eslint-disable-next-line @next/next/no-img-element
        <img className="profile-banner" src={banner} alt="" loading="lazy" />
      ) : (
        <div className="profile-banner profile-banner-empty" />
      )}
      <div className="profile-body">
        {avatar ? (
          // eslint-disable-next-line @next/next/no-img-element
          <img
            className="profile-avatar"
            src={largeAvatar(avatar)}
            alt={`@${username}`}
            loading="lazy"
          />
        ) : null}
        <div className="profile-id">
          <div className="profile-name">
            {profile.display_name || username}
            {badges.map((b) => (
              <span className="profile-badge" key={b}>
                {b}
              </span>
            ))}
          </div>
          <a
            className="profile-handle"
            href={`https://x.com/${username}`}
            target="_blank"
            rel="noopener noreferrer"
          >
            @{username}
          </a>
        </div>

        {profile.description ? (
          <p className="profile-bio">{profile.description}</p>
        ) : null}

        <div className="profile-meta">
          {profile.location ? <span>📍 {profile.location}</span> : null}
          {profile.user_url ? (
            <a href={profile.user_url} target="_blank" rel="noopener noreferrer">
              🔗 {profile.user_url}
            </a>
          ) : null}
          {profile.user_created_at ? (
            <span>🗓 Joined {formatJoined(profile.user_created_at, timezone)}</span>
          ) : null}
          {profile.author_id ? (
            <span className="profile-id-raw">id {profile.author_id}</span>
          ) : null}
        </div>

        {hasMetrics ? (
          <div className="profile-metrics">
            {METRICS.map(({ key, label }) => (
              <div className="profile-metric" key={key}>
                <span className="profile-metric-value">
                  {typeof metrics?.[key] === "number"
                    ? fmt(metrics[key] as number)
                    : "—"}
                </span>
                <span className="profile-metric-label">{label}</span>
              </div>
            ))}
          </div>
        ) : null}

        {profile.pinned_tweet_id || profile.most_recent_tweet_id ? (
          <div className="profile-meta profile-meta-ids">
            {profile.pinned_tweet_id ? (
              <a
                href={`https://x.com/${username}/status/${profile.pinned_tweet_id}`}
                target="_blank"
                rel="noopener noreferrer"
              >
                Pinned post
              </a>
            ) : null}
            {profile.most_recent_tweet_id ? (
              <a
                href={`https://x.com/${username}/status/${profile.most_recent_tweet_id}`}
                target="_blank"
                rel="noopener noreferrer"
              >
                Most recent post
              </a>
            ) : null}
          </div>
        ) : null}
      </div>
    </div>
  );
}
