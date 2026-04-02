import { WebClient } from "@slack/web-api";

const slack = new WebClient(process.env.SLACK_BOT_TOKEN);

// ─── User lookup ─────────────────────────────────────────────────────────────

export async function findSlackUserByEmail(
  email: string
): Promise<string | null> {
  try {
    const result = await slack.users.lookupByEmail({ email });
    return result.user?.id ?? null;
  } catch {
    console.warn(`[Slack] Could not find user for email: ${email}`);
    return null;
  }
}

// ─── DM sender ───────────────────────────────────────────────────────────────

export async function sendSlackDM(
  userId: string,
  message: string
): Promise<void> {
  // Open a DM channel then post to it
  const dm = await slack.conversations.open({ users: userId });
  const channelId = dm.channel?.id;
  if (!channelId) throw new Error(`Could not open DM with user ${userId}`);

  await slack.chat.postMessage({
    channel: channelId,
    text: message,
  });
}

// ─── Alert messages ──────────────────────────────────────────────────────────

export function buildInterviewerAlert(
  interviewerName: string,
  interviewTitle: string
): string {
  return (
    `👋 Hi ${interviewerName}, this is a reminder that your interview *${interviewTitle}* started 5 minutes ago and it looks like you haven't joined the Zoom yet.\n\n` +
    `Please join as soon as possible or let the team know if you need to reschedule.`
  );
}

export function buildOrganizerAlert(
  interviewTitle: string,
  interviewerMissing: boolean,
  candidateMissing: boolean,
  interviewerName: string
): string {
  const lines = [`⚠️ *Interview Check — ${interviewTitle}*\n`];

  if (interviewerMissing && candidateMissing) {
    lines.push(`• Neither *${interviewerName}* (interviewer) nor the candidate have joined the Zoom meeting 5 minutes after the scheduled start time.`);
  } else if (interviewerMissing) {
    lines.push(`• *${interviewerName}* (interviewer) has not joined the Zoom meeting 5 minutes after the scheduled start time.`);
  } else if (candidateMissing) {
    lines.push(`• The *candidate* has not joined the Zoom meeting 5 minutes after the scheduled start time.`);
  }

  lines.push(`\nYou may want to follow up.`);
  return lines.join("\n");
}
