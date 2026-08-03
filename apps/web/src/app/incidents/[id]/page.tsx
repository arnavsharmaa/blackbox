"use client";

import { use, useEffect } from "react";
import { fetchIncidentDetail } from "@/lib/api";
import { useApi } from "@/lib/useApi";
import { failureTime } from "@/lib/telemetry";
import { useReplayStore } from "@/store/replay";
import { ErrorState, LoadingState } from "@/components/ui";
import { IncidentHeader } from "@/components/incident/IncidentHeader";
import { SummaryCard } from "@/components/incident/SummaryCard";
import { ReplayControls } from "@/components/incident/ReplayControls";
import { Timeline } from "@/components/incident/Timeline";
import { TelemetryCharts } from "@/components/incident/TelemetryCharts";
import { PathMap } from "@/components/incident/PathMap";
import { EvidencePanel } from "@/components/incident/EvidencePanel";
import { HealthPanel } from "@/components/incident/HealthPanel";
import { EventInspector } from "@/components/incident/EventInspector";
import { useReplayClock } from "@/components/incident/useReplayClock";

export default function IncidentDetailPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = use(params);
  const detail = useApi(() => fetchIncidentDetail(id), [id]);
  useReplayClock();

  const incident = detail.data?.incident;
  const analysis = detail.data?.analysis ?? null;

  // (Re)initialize the replay store whenever a new incident loads.
  useEffect(() => {
    if (!incident) return;
    const duration =
      (new Date(incident.end_time).getTime() -
        new Date(incident.start_time).getTime()) /
      1000;
    useReplayStore.getState().init(duration, failureTime(incident));
  }, [incident]);

  if (detail.loading) return <LoadingState label="Loading incident…" />;
  if (detail.error)
    return <ErrorState error={detail.error} onRetry={detail.refetch} />;
  if (!incident) return null;

  return (
    <div className="space-y-4">
      <IncidentHeader incident={incident} analysis={analysis} />

      <div className="grid gap-4 xl:grid-cols-[1fr_380px]">
        <div className="space-y-4">
          <ReplayControls />
          <Timeline incident={incident} />
          <TelemetryCharts incident={incident} />
        </div>
        <div className="space-y-4">
          <SummaryCard incident={incident} analysis={analysis} />
          <PathMap incident={incident} />
          {analysis && <EvidencePanel analysis={analysis} />}
          <HealthPanel incident={incident} />
          <EventInspector incident={incident} />
        </div>
      </div>
    </div>
  );
}
