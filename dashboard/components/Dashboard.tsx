"use client";

import { useEffect, useMemo, useState } from "react";
import Bars from "@/components/Bars";
import { API_URL, api, type Camera, type EventPage, type Run, type Stats, type Zone } from "@/lib/api";

const PAGE_SIZE = 20;

function formatTime(iso: string): string {
  return new Date(iso).toLocaleString("id-ID", { timeZone: "Asia/Jakarta", hour12: false });
}

function formatVideoTime(seconds: number | null): string {
  if (seconds === null) return "-";
  const minutes = Math.floor(seconds / 60);
  const rest = (seconds - minutes * 60).toFixed(1).padStart(4, "0");
  return `${String(minutes).padStart(2, "0")}:${rest}`;
}


export default function Dashboard() {
  const [cameras, setCameras] = useState<Camera[]>([]);
  const [runs, setRuns] = useState<Run[]>([]);
  const [camera, setCamera] = useState("");
  const [runId, setRunId] = useState("");
  const [eventType, setEventType] = useState("");
  const [className, setClassName] = useState("");
  const [zone, setZone] = useState("");
  const [offset, setOffset] = useState(0);

  const [stats, setStats] = useState<Stats | null>(null);
  const [zones, setZones] = useState<Zone[]>([]);
  const [page, setPage] = useState<EventPage | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [refresh, setRefresh] = useState(0);

  const fail = (e: unknown) => setError(e instanceof Error ? e.message : String(e));

  // 1) daftar kamera dan run
  useEffect(() => {
    Promise.all([api.cameras(), api.runs()])
      .then(([cams, rs]) => {
        setCameras(cams);
        setRuns(rs);
        setCamera((current) => current || cams[0]?.name || "");
        setError(null);
      })
      .catch(fail);
  }, [refresh]);

  // run milik kamera terpilih (API mengurutkan dari yang terbaru)
  const cameraRuns = useMemo(() => runs.filter((r) => r.camera === camera), [runs, camera]);

  useEffect(() => {
    setRunId((current) =>
      cameraRuns.some((r) => r.run_id === current) ? current : (cameraRuns[0]?.run_id ?? ""),
    );
  }, [cameraRuns]);

  useEffect(() => {
    setOffset(0);
  }, [camera, runId]);

  const scope = useMemo(() => ({ camera, run_id: runId }), [camera, runId]);

  // 2) ringkasan dan zona (tidak terpengaruh filter tabel)
  useEffect(() => {
    if (!camera) return;
    Promise.all([api.stats(scope), api.zones(camera)])
      .then(([s, z]) => {
        setStats(s);
        setZones(z);
      })
      .catch(fail);
  }, [scope, camera, refresh]);

  // 3) tabel event
  useEffect(() => {
    if (!camera) return;
    setLoading(true);
    api
      .events({ ...scope, event_type: eventType, class_name: className, zone, limit: PAGE_SIZE, offset })
      .then(setPage)
      .catch(fail)
      .finally(() => setLoading(false));
  }, [scope, eventType, className, zone, offset, refresh, camera]);

  const onFilter = (setter: (v: string) => void) => (value: string) => {
    setter(value);
    setOffset(0);
  };

  const byType = stats?.by_event_type ?? {};
  const total = page?.total ?? 0;
  const from = total === 0 ? 0 : offset + 1;
  const to = Math.min(offset + PAGE_SIZE, total);

  return (
    <main className="wrap">
      <header className="top">
        <div>
          <h1>AI CCTV Monitoring</h1>
          <p className="muted">Deteksi, tracking, dan event zona</p>
        </div>
        <div className="controls">
          <label>
            Kamera
            <select value={camera} onChange={(e) => setCamera(e.target.value)}>
              {cameras.map((c) => (
                <option key={c.id} value={c.name}>
                  {c.name}
                </option>
              ))}
            </select>
          </label>
          <label>
            Run
            <select value={runId} onChange={(e) => setRunId(e.target.value)}>
              {cameraRuns.map((r) => (
                <option key={r.run_id} value={r.run_id}>
                  {r.run_id} ({r.events} event)
                </option>
              ))}
            </select>
          </label>
          <button onClick={() => setRefresh((n) => n + 1)}>Muat ulang</button>
        </div>
      </header>

      {error && (
        <div className="error">
          Tidak bisa mengambil data dari <code>{API_URL}</code>: {error}. Pastikan API berjalan:{" "}
          <code>uvicorn api.main:create_app --factory</code>
        </div>
      )}

      {!error && cameras.length === 0 && (
        <div className="empty">
          Belum ada data. Jalankan pipeline dengan bagian <code>database</code> aktif di config.
        </div>
      )}

      {stats && (
        <>
          <section className="cards">
            <div className="card">
              <span>Total event</span>
              <strong>{stats.total}</strong>
            </div>
            <div className="card">
              <span>Masuk zona</span>
              <strong>{(byType["zone_enter"] ?? 0) + (byType["object_in_zone"] ?? 0)}</strong>
            </div>
            <div className="card">
              <span>Keluar zona</span>
              <strong>{byType["zone_exit"] ?? 0}</strong>
            </div>
            <div className="card">
              <span>Kepadatan</span>
              <strong>
                {(byType["congestion"] ?? 0) + (byType["congestion_start"] ?? 0)}
              </strong>
            </div>
          </section>

          <section className="grid2">
            <div className="panel">
              <h2>Event per kelas</h2>
              <Bars data={stats.by_class} />
            </div>
            <div className="panel">
              <h2>Event per zona</h2>
              <Bars data={stats.by_zone} />
            </div>
          </section>
        </>
      )}

      {zones.length > 0 && (
        <section className="panel">
          <h2>Zona kamera {camera}</h2>
          <div className="zones">
            {zones.map((z) => (
              <div className="zone" key={z.id}>
                <strong>{z.name}</strong>
                <span className="muted">
                  {z.classes.length ? z.classes.join(", ") : "semua kelas"}
                  {z.min_confidence !== null && ` · min conf ${z.min_confidence}`}
                  {z.congestion_threshold !== null && ` · padat ≥ ${z.congestion_threshold}`}
                </span>
              </div>
            ))}
          </div>
        </section>
      )}

      {stats && (
        <section className="panel">
          <div className="table-head">
            <h2>Daftar event</h2>
            <div className="controls">
              <select value={eventType} onChange={(e) => onFilter(setEventType)(e.target.value)}>
                <option value="">Semua jenis</option>
                {Object.keys(stats.by_event_type).map((k) => (
                  <option key={k}>{k}</option>
                ))}
              </select>
              <select value={className} onChange={(e) => onFilter(setClassName)(e.target.value)}>
                <option value="">Semua kelas</option>
                {Object.keys(stats.by_class).map((k) => (
                  <option key={k}>{k}</option>
                ))}
              </select>
              <select value={zone} onChange={(e) => onFilter(setZone)(e.target.value)}>
                <option value="">Semua zona</option>
                {Object.keys(stats.by_zone).map((k) => (
                  <option key={k}>{k}</option>
                ))}
              </select>
            </div>
          </div>

          <div className="table-scroll">
            <table>
              <thead>
                <tr>
                  <th>Waktu video</th>
                  <th>Diproses (WIB)</th>
                  <th>Event</th>
                  <th>Kelas</th>
                  <th>Zona</th>
                  <th>ID</th>
                  <th>Frame</th>
                  <th>Conf</th>
                  <th>Jumlah</th>
                </tr>
              </thead>
              <tbody>
                {page?.items.map((e) => (
                  <tr key={e.id}>
                    <td>{formatVideoTime(e.video_time)}</td>
                    <td>{formatTime(e.timestamp)}</td>
                    <td>
                      <span className={`badge ${e.event_type}`}>{e.event_type}</span>
                    </td>
                    <td>{e.class_name}</td>
                    <td>{e.zone ?? "-"}</td>
                    <td>{e.track_id ?? "-"}</td>
                    <td>{e.frame_id}</td>
                    <td>{(e.confidence * 100).toFixed(0)}%</td>
                    <td>{e.count ?? "-"}</td>
                  </tr>
                ))}
                {page && page.items.length === 0 && (
                  <tr>
                    <td colSpan={9} className="muted">
                      Tidak ada event untuk filter ini.
                    </td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>

          <div className="pager">
            <span className="muted">
              {from}-{to} dari {total} {loading && "· memuat..."}
            </span>
            <div>
              <button disabled={offset === 0} onClick={() => setOffset(Math.max(0, offset - PAGE_SIZE))}>
                Sebelumnya
              </button>
              <button disabled={offset + PAGE_SIZE >= total} onClick={() => setOffset(offset + PAGE_SIZE)}>
                Berikutnya
              </button>
            </div>
          </div>
        </section>
      )}
    </main>
  );
}