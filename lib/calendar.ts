import { google } from "googleapis";

export interface Interviewer {
  name: string;
  email: string;
}

export interface Interview {
  id: string;
  title: string;
  startTime: Date;
  zoomLink: string | null;
  zoomMeetingId: string | null;
  interviewer: Interviewer;
}

// ─── Auth ────────────────────────────────────────────────────────────────────

function getCalendarClient() {
  const auth = new google.auth.JWT({
    email: process.env.GOOGLE_SERVICE_ACCOUNT_EMAIL,
    key: process.env.GOOGLE_PRIVATE_KEY?.replace(/\\n/g, "\n"),
    scopes: ["https://www.googleapis.com/auth/calendar.readonly"],
  });
  return google.calendar({ version: "v3", auth });
}

// ─── Helpers ─────────────────────────────────────────────────────────────────

function extractZoomLink(text: string | null | undefined): string | null {
  if (!text) return null;
  const match = text.match(/https:\/\/[a-z0-9.]*zoom\.us\/j\/[^\s<"]+/i);
  return match ? match[0] : null;
}

function extractMeetingId(zoomUrl: string): string | null {
  // Handles: https://zoom.us/j/96598579501?pwd=...
  const match = zoomUrl.match(/zoom\.us\/j\/(\d+)/);
  return match ? match[1] : null;
}

function isOrganizer(email: string): boolean {
  return email.toLowerCase() === process.env.MY_EMAIL?.toLowerCase();
}

function isGreenhouse(email: string): boolean {
  const domain = process.env.GREENHOUSE_EMAIL_DOMAIN ?? "greenhouse.io";
  return email.toLowerCase().endsWith(`@${domain}`);
}

// ─── Main export ─────────────────────────────────────────────────────────────

/**
 * Returns interviews that started between (minutesAgo + 1) and minutesAgo
 * minutes in the past, so the cron job (running every minute) processes
 * each interview exactly once — right at the 5-minute mark.
 */
export async function getInterviewsDueForCheck(
  minutesAgo = 5
): Promise<Interview[]> {
  const calendar = getCalendarClient();

  const windowEnd = new Date(Date.now() - minutesAgo * 60 * 1000);
  const windowStart = new Date(windowEnd.getTime() - 60 * 1000); // 1-min window

  const response = await calendar.events.list({
    calendarId: process.env.GOOGLE_CALENDAR_ID!,
    timeMin: windowStart.toISOString(),
    timeMax: windowEnd.toISOString(),
    singleEvents: true,
    orderBy: "startTime",
  });

  const events = response.data.items ?? [];
  const interviews: Interview[] = [];

  for (const event of events) {
    const attendees = event.attendees ?? [];

    // Find the interviewer: not the organizer, not Greenhouse
    const interviewer = attendees.find(
      (a) =>
        a.email &&
        !isOrganizer(a.email) &&
        !isGreenhouse(a.email) &&
        a.responseStatus !== "declined"
    );

    if (!interviewer?.email) continue; // Skip if no valid interviewer found

    const zoomLink =
      extractZoomLink(event.description) ??
      extractZoomLink(event.location) ??
      null;

    interviews.push({
      id: event.id ?? "",
      title: event.summary ?? "Interview",
      startTime: new Date(event.start?.dateTime ?? event.start?.date ?? ""),
      zoomLink,
      zoomMeetingId: zoomLink ? extractMeetingId(zoomLink) : null,
      interviewer: {
        name: interviewer.displayName ?? interviewer.email,
        email: interviewer.email,
      },
    });
  }

  return interviews;
}
