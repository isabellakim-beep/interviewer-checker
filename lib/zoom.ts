import axios from "axios";

// ─── Auth ────────────────────────────────────────────────────────────────────

let cachedToken: { value: string; expiresAt: number } | null = null;

async function getZoomToken(): Promise<string> {
  // Return cached token if still valid (with 60s buffer)
  if (cachedToken && Date.now() < cachedToken.expiresAt - 60_000) {
    return cachedToken.value;
  }

  const credentials = Buffer.from(
    `${process.env.ZOOM_CLIENT_ID}:${process.env.ZOOM_CLIENT_SECRET}`
  ).toString("base64");

  const response = await axios.post(
    `https://zoom.us/oauth/token?grant_type=account_credentials&account_id=${process.env.ZOOM_ACCOUNT_ID}`,
    null,
    { headers: { Authorization: `Basic ${credentials}` } }
  );

  cachedToken = {
    value: response.data.access_token,
    expiresAt: Date.now() + response.data.expires_in * 1000,
  };

  return cachedToken.value;
}

// ─── Types ───────────────────────────────────────────────────────────────────

export interface ZoomParticipant {
  name: string;
  email: string;
  joinTime: string;
}

export interface MeetingStatus {
  interviewerJoined: boolean;
  candidateJoined: boolean;    // true if >= 2 participants OR a non-interviewer joined
  participantCount: number;
  participants: ZoomParticipant[];
}

// ─── Main export ─────────────────────────────────────────────────────────────

/**
 * Checks who has joined the Zoom meeting using the Dashboard (live) API.
 * Requires dashboard_meetings:read:admin scope on a Business/Enterprise plan.
 */
export async function checkMeetingParticipants(
  meetingId: string,
  interviewerEmail: string
): Promise<MeetingStatus> {
  const token = await getZoomToken();

  // Fetch live participants from the Dashboard API
  const response = await axios.get(
    `https://api.zoom.us/v2/metrics/meetings/${meetingId}/participants`,
    {
      headers: { Authorization: `Bearer ${token}` },
      params: { type: "live", page_size: 100 },
    }
  );

  const participants: ZoomParticipant[] = (
    response.data.participants ?? []
  ).map((p: any) => ({
    name: p.name ?? p.user_name ?? "",
    email: p.email ?? p.user_email ?? "",
    joinTime: p.join_time ?? "",
  }));

  const interviewerJoined = participants.some(
    (p) => p.email.toLowerCase() === interviewerEmail.toLowerCase()
  );

  // Candidate is anyone who isn't the interviewer
  const nonInterviewerCount = participants.filter(
    (p) => p.email.toLowerCase() !== interviewerEmail.toLowerCase()
  ).length;

  return {
    interviewerJoined,
    candidateJoined: nonInterviewerCount > 0,
    participantCount: participants.length,
    participants,
  };
}
