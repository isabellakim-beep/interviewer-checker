import { NextRequest, NextResponse } from "next/server";
import { getInterviewsDueForCheck } from "@/lib/calendar";
import { checkMeetingParticipants } from "@/lib/zoom";
import {
  findSlackUserByEmail,
  sendSlackDM,
  buildInterviewerAlert,
  buildOrganizerAlert,
} from "@/lib/slack";

// ─── Security: only allow Vercel Cron or requests with the correct secret ────

function isAuthorized(req: NextRequest): boolean {
  const authHeader = req.headers.get("authorization");
  return authHeader === `Bearer ${process.env.CRON_SECRET}`;
}

// ─── Main handler ─────────────────────────────────────────────────────────────

export async function GET(req: NextRequest) {
  if (!isAuthorized(req)) {
    return NextResponse.json({ error: "Unauthorized" }, { status: 401 });
  }

  console.log("[check-interviews] Cron triggered at", new Date().toISOString());

  const interviews = await getInterviewsDueForCheck(5);

  if (interviews.length === 0) {
    console.log("[check-interviews] No interviews at the 5-minute mark.");
    return NextResponse.json({ checked: 0 });
  }

  const results = [];

  for (const interview of interviews) {
    console.log(`[check-interviews] Checking: "${interview.title}"`);

    // ── Skip if no Zoom link ──────────────────────────────────────────────
    if (!interview.zoomMeetingId) {
      console.warn(`[check-interviews] No Zoom link found for "${interview.title}" — skipping.`);
      results.push({ title: interview.title, skipped: true, reason: "no_zoom_link" });
      continue;
    }

    // ── Check Zoom participants ───────────────────────────────────────────
    let meetingStatus;
    try {
      meetingStatus = await checkMeetingParticipants(
        interview.zoomMeetingId,
        interview.interviewer.email
      );
    } catch (err: any) {
      console.error(`[check-interviews] Zoom API error for "${interview.title}":`, err.message);
      results.push({ title: interview.title, skipped: true, reason: "zoom_api_error" });
      continue;
    }

    const { interviewerJoined, candidateJoined } = meetingStatus;
    console.log(
      `[check-interviews] "${interview.title}" — interviewer: ${interviewerJoined}, candidate: ${candidateJoined}`
    );

    // ── If everyone joined, nothing to do ────────────────────────────────
    if (interviewerJoined && candidateJoined) {
      results.push({ title: interview.title, allPresent: true });
      continue;
    }

    // ── Alert: DM the interviewer if they haven't joined ─────────────────
    if (!interviewerJoined) {
      const interviewerSlackId = await findSlackUserByEmail(
        interview.interviewer.email
      );

      if (interviewerSlackId) {
        await sendSlackDM(
          interviewerSlackId,
          buildInterviewerAlert(interview.interviewer.name, interview.title)
        );
        console.log(`[check-interviews] DM sent to interviewer ${interview.interviewer.name}`);
      } else {
        console.warn(
          `[check-interviews] Could not find Slack user for interviewer: ${interview.interviewer.email}`
        );
      }
    }

    // ── Alert: Always DM the organizer (you) if anyone is missing ────────
    const mySlackId = process.env.MY_SLACK_USER_ID!;
    await sendSlackDM(
      mySlackId,
      buildOrganizerAlert(
        interview.title,
        !interviewerJoined,
        !candidateJoined,
        interview.interviewer.name
      )
    );
    console.log(`[check-interviews] DM sent to organizer for "${interview.title}"`);

    results.push({
      title: interview.title,
      interviewerJoined,
      candidateJoined,
      alertsSent: true,
    });
  }

  return NextResponse.json({ checked: interviews.length, results });
}
