import { buttonClass } from "@/lib/button";
import { useCallback, useEffect, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { CorrectionMap } from "@/components/corrections/CorrectionMap";
import { coordinates } from "@/lib/correction-map";
import { CORRECTION_TYPES, correctionApi, searchLabel, type CorrectionCandidate } from "@/lib/corrections";
import { displayValue, type CorrectionKind } from "@/lib/master";
import { PDPJ_FIELDS } from "@/lib/pdpj";
import type { ApiError } from "@/lib/api";
import { useAppStore } from "@/store/app";

const control = "min-w-0 rounded-sm border-2 border-neo-border bg-white px-3 py-2 text-sm disabled:opacity-50";
const button = buttonClass.secondary;
const panel = "space-y-4 rounded-sm border-2 border-neo-border bg-white p-4 sm:p-5";
const message = (error: unknown) => {
  const value = (error as ApiError)?.message;
  return typeof value === "string" ? value : "Proses belum berhasil. Coba lagi.";
};

export default function CorrectionMapPage() {
  const [params, setParams] = useSearchParams();
  const kind: CorrectionKind = params.get("category") === "idpel_kosong" ? "idpel_kosong" : "idpel_tidak_ketemu";
  const process = Number(params.get("process_id")) || null;
  const batch = Number(params.get("batch_id")) || null;
  return <MapWorkspace key={`${kind}-${batch}-${process}`} kind={kind} batchParam={batch} processParam={process} generationParam={Number(params.get("generation")) || null} changeParams={setParams} />;
}

function MapWorkspace({ kind, batchParam, processParam, generationParam, changeParams }: {
  kind: CorrectionKind; batchParam: number | null; processParam: number | null; generationParam: number | null;
  changeParams: (params: Record<string, string>) => void;
}) {
  const client = useQueryClient();
  const user = useAppStore((state) => state.user);
  const [actor, setActor] = useState(user?.username ?? "");
  const [reason, setReason] = useState("");
  const [selected, setSelected] = useState<number | null>(null);
  const [requested, setRequested] = useState<{ id: number; radius: number } | null>(null);
  const [radiusChoice, setRadiusChoice] = useState<string | null>(null);
  const [search, setSearch] = useState("");
  const [page, setPage] = useState(1);
  const [candidatePage, setCandidatePage] = useState(1);
  const [notice, setNotice] = useState("");
  const [focusedCandidate, setFocusedCandidate] = useState<number | null>(null);
  const descriptor = CORRECTION_TYPES.find((item) => item.key === kind)!;
  const batches = useQuery({ queryKey: ["correction-batches", kind], queryFn: () => correctionApi.batches(kind) });
  const batch = batchParam ?? batches.data?.find((item) => item.status === "completed")?.id;
  const checks = useQuery({ queryKey: ["correction-checks", kind, batch], queryFn: () => correctionApi.checks(kind, batch!), enabled: Boolean(batch) });
  const process = processParam ?? checks.data?.[0]?.process_id;
  const check = useQuery({ queryKey: ["correction-check", kind, process], queryFn: () => correctionApi.check(kind, process!), enabled: Boolean(process), refetchInterval: (query) => ["queued", "running"].includes(query.state.data?.latest_run.status ?? "") ? 1500 : false });
  const latestGeneration = check.data?.latest_run.processing ? check.data.latest_run.generation : check.data?.current_generation;
  const generation = generationParam ?? latestGeneration;
  const run = check.data?.runs.find((item) => item.generation === generation && (item.status === "completed" || item.processing));
  const partial = !!run?.processing && run.status !== "completed";
  const scope = { batch_id: batch, process_id: process, generation };
  const rows = useQuery({ queryKey: ["correction-map-rows", kind, scope, run?.processing?.processed_rows], queryFn: ({ signal }) => correctionApi.allRows(kind, scope, signal), enabled: Boolean(run && batch && check.data?.batch_id === batch) });
  const active = rows.data?.find((row) => row.id === selected);
  const radius = Number(radiusChoice ?? run?.radius_meters ?? 100);
  const validRadius = Number.isFinite(radius) && radius > 0 && radius <= 100000;
  const busy = ["queued", "running"].includes(check.data?.latest_run.status ?? "");
  const blockedBySearch = busy && !check.data?.latest_run.processing;
  const expansionBlocked = busy || partial;
  const historical = Boolean(check.data && generation !== latestGeneration);
  const candidateQuery = useQuery({ queryKey: ["correction-map-candidates", kind, process, generation, requested], queryFn: ({ signal }) => correctionApi.mapCandidates(kind, requested!.id, scope, requested!.radius, signal), enabled: Boolean(run && requested && requested.id === selected && requested.radius <= run.radius_meters && !blockedBySearch) });
  const candidates = requested?.id === selected && requested?.radius === radius ? candidateQuery.data ?? [] : [];
  const choiceKey = ["correction-choice", kind, process, selected];
  const choice = useQuery({ queryKey: choiceKey, queryFn: () => correctionApi.choice(kind, process!, selected!), enabled: Boolean(process && selected && active) });
  const expand = useMutation({
    mutationFn: () => correctionApi.retry(kind, process!, { latest_run_id: check.data!.latest_run.id, radius_meters: radius, actor: actor.trim(), request_key: crypto.randomUUID() }),
    onSuccess: (result) => { client.setQueryData(["correction-check", kind, process], result); setRequested({ id: selected!, radius }); setCandidatePage(1); setNotice(result.status === "failed" ? "Pencarian gagal. Hasil sebelumnya tetap tersedia; coba perluas lagi." : "Radius diperluas untuk pemeriksaan ini. Riwayat dan pilihan sebelumnya tetap tersimpan."); },
    onError: () => { void client.invalidateQueries({ queryKey: ["correction-check", kind, process] }); },
  });
  const choose = useMutation({
    mutationFn: (candidate: number | null) => correctionApi.choose(kind, process!, selected!, { generation: generation!, expected_revision: choice.data!.revision, candidate_id: candidate, actor: actor.trim(), reason: reason.trim(), request_key: crypto.randomUUID() }),
    onSuccess: (result) => { client.setQueryData(choiceKey, result); setReason(""); setNotice(result.current?.candidate_id ? "Pilihan kandidat tersimpan." : "Pilihan dibatalkan. Riwayat tetap tersimpan."); },
    onError: () => { void client.invalidateQueries({ queryKey: choiceKey }); void client.invalidateQueries({ queryKey: ["correction-check", kind, process] }); },
  });
  const select = useCallback((id: number) => { if (choose.isPending || expand.isPending) return; setSelected(id); setRequested(null); setCandidatePage(1); setReason(""); setNotice(""); }, [choose.isPending, expand.isPending]);
  const candidateFocus = (id: number) => { const index = candidates.findIndex((item) => item.id === id); if (index >= 0) { setCandidatePage(Math.floor(index / 10) + 1); setFocusedCandidate(id); } };
  useEffect(() => { if (focusedCandidate !== null) { const element = document.getElementById(`candidate-${focusedCandidate}`); element?.scrollIntoView({ behavior: "smooth", block: "center" }); element?.focus({ preventScroll: true }); } }, [focusedCandidate, candidatePage]);
  const filtered = (rows.data ?? []).filter((row) => !search.trim() || Object.values(row.fields).some((value) => String(value ?? "").toLowerCase().includes(search.trim().toLowerCase())));
  const pageRows = filtered.slice((page - 1) * 25, page * 25);
  const visibleCandidates = candidates.slice((candidatePage - 1) * 10, candidatePage * 10);
  const canChoose = Boolean(!historical && !blockedBySearch && !expand.isPending && !choose.isPending && choice.data && !choice.isFetching && actor.trim() && (!choice.data.current || reason.trim()));
  const selectedChoice = choice.data?.current?.candidate;
  const dataError = batches.error || checks.error || check.error || rows.error;
  const noCoordinates = (rows.data ?? []).filter((row) => !coordinates(row.fields)).length;
  return <div className="space-y-5">
    {check.data?.pdpj_update && <aside aria-label="Pembaruan versi PDPJ" className="space-y-2 rounded-sm border-2 border-amber-700 bg-amber-50 p-4 text-sm text-amber-950"><p>Hasil PDPJ yang lebih baru tersedia. Peta ini tetap memakai versi PDPJ #{check.data.pdpj_review_id} yang dipilih saat pemeriksaan dimulai.</p>{check.data.pdpj_update.conflicts.length > 0 && <p role="alert" className="font-bold">{check.data.pdpj_update.conflicts.length.toLocaleString("id-ID")} keputusan berbenturan dengan PDPJ terbaru dan perlu ditinjau ulang.</p>}<Link to={`/koreksi/${descriptor.slug}?batch_id=${batch}&process_id=${process}`} className="font-bold underline">Tinjau versi PDPJ dan hasil koreksi</Link></aside>}
    <header><p className="text-xs font-bold uppercase text-neo-border">Rekonsiliasi pelanggan</p><h1 className="mt-1 text-2xl font-black">Peta Koreksi</h1><p className="mt-2 text-sm">Pilih target dari tabel atau titik, tampilkan kandidat dalam radius, lalu simpan pilihan.</p></header>
    <section className={panel} aria-label="Filter peta koreksi">
      <div className="grid gap-3 md:grid-cols-3">
        <label className="flex flex-col gap-1 text-xs font-bold">Kategori<select disabled={choose.isPending || expand.isPending} aria-label="Kategori peta" value={kind} onChange={(event) => changeParams({ category: event.target.value })} className={control}>{CORRECTION_TYPES.map((item) => <option key={item.key} value={item.key}>{item.label}</option>)}</select></label>
        <label className="flex flex-col gap-1 text-xs font-bold">Berkas<select disabled={choose.isPending || expand.isPending} aria-label="Berkas peta" value={batch ?? ""} onChange={(event) => changeParams({ category: kind, batch_id: event.target.value })} className={control}><option value="" disabled>Pilih berkas</option>{batches.data?.filter((item) => item.status === "completed").map((item) => <option key={item.id} value={item.id}>#{item.id} · {item.filename}</option>)}</select></label>
        <label className="flex flex-col gap-1 text-xs font-bold">Pemeriksaan<select disabled={choose.isPending || expand.isPending} aria-label="Pemeriksaan peta" value={process ?? ""} onChange={(event) => changeParams({ category: kind, batch_id: String(batch), process_id: event.target.value })} className={control}><option value="" disabled>Pilih pemeriksaan</option>{checks.data?.map((item) => <option key={item.process_id} value={item.process_id}>#{item.process_id} · PDPJ #{item.pdpj_review_id}</option>)}</select></label>
      </div>
      <Link className="inline-block text-xs font-bold underline" to={`/koreksi/${descriptor.slug}${batch ? `?batch_id=${batch}${process ? `&process_id=${process}` : ""}` : ""}`}>Buka data dan riwayat pemeriksaan</Link>
      {dataError && <p role="alert" className="text-sm text-red-700">{message(dataError)}</p>}
      {!process && !checks.isPending && <p className="text-sm">Belum ada pemeriksaan. Selesaikan pemeriksaan pada Data Koreksi untuk menampilkan peta.</p>}
      {check.data && batch && check.data.batch_id !== batch && <p role="alert" className="text-red-700">Pemeriksaan tidak sesuai dengan berkas terpilih.</p>}
      {historical && <p role="status" className="text-sm text-amber-900">Anda melihat versi historis {generation}. Pilihan aktif ditampilkan untuk pembanding dan tidak dapat diubah di versi ini. <button className="underline" onClick={() => changeParams({ category: kind, batch_id: String(batch), process_id: String(process) })}>Buka versi terbaru</button></p>}
      {partial && <p role="status" className="text-sm">{run.processing!.processed_rows.toLocaleString("id-ID")} dari {run.processing!.total_rows.toLocaleString("id-ID")} baris sudah tersimpan dan tersedia untuk koreksi di peta. Pilihan kandidat langsung disimpan. Pemeriksaan sisa baris dapat dilanjutkan melalui Data Koreksi tanpa mengubah pilihan yang sudah tersimpan.</p>}
      {busy && !check.data?.latest_run.processing && <p role="status" className="text-sm">Pencarian sedang diproses. Hasil sebelumnya tetap terlihat sampai versi baru selesai.</p>}
      {check.data?.latest_run.status === "failed" && <p role="alert" className="text-sm text-red-700">Pencarian terakhir terhenti. Hasil yang sudah tersimpan tetap tersedia. Lanjutkan pemeriksaan melalui Data Koreksi.</p>}
    </section>
    <section className={panel} aria-label="Pemetaan koreksi">
      <p className="text-sm font-bold">{rows.isFetching ? "Memuat seluruh target…" : `${rows.data?.length ?? 0} baris · ${(rows.data?.length ?? 0) - noCoordinates} bertitik · ${noCoordinates} tanpa koordinat`} · {descriptor.label}</p>
      <CorrectionMap rows={rows.data ?? []} selected={selected} candidates={candidates} radius={requested?.id === selected && requested.radius === radius ? radius : null} onSelect={select} onCandidate={candidateFocus} />
      <div className="grid gap-3 sm:grid-cols-3">
        <label className="flex flex-col gap-1 text-xs font-bold">Radius (meter)<input aria-label="Radius peta (meter)" type="number" min="0.01" max="100000" step="any" value={radiusChoice ?? run?.radius_meters ?? 100} onChange={(event) => { setRadiusChoice(event.target.value); setRequested(null); }} disabled={blockedBySearch || expand.isPending || choose.isPending} className={control} /></label>
        <label className="flex flex-col gap-1 text-xs font-bold">Petugas<input aria-label="Petugas peta" disabled={choose.isPending} value={actor} maxLength={80} onChange={(event) => setActor(event.target.value)} className={control} /></label>
        <button type="button" disabled={choose.isPending || !active || !coordinates(active.fields) || !["matched", "no_candidates"].includes(active.search_status) || !validRadius || blockedBySearch || expand.isPending || !run || (radius > run.radius_meters && (historical || expansionBlocked || !actor.trim()))} onClick={() => { setNotice(""); setCandidatePage(1); if (radius > run!.radius_meters) expand.mutate(); else { setRequested({ id: selected!, radius }); } }} className={`${buttonClass.primary} self-end`}>{expand.isPending || blockedBySearch ? "Memproses pencarian…" : run && radius > run.radius_meters ? "Perluas pemeriksaan dan tampilkan kandidat" : "Tampilkan kandidat target"}</button>
      </div>
      <p className="text-xs">{run ? `Radius tersimpan ${run.radius_meters} m. Radius hingga batas ini memakai kandidat tersimpan. ${partial ? "Selesaikan pemeriksaan sisa baris sebelum memperluas radius." : "Perluasan memeriksa ulang seluruh berkas dan menyimpan versi baru."}` : "Selesaikan pemeriksaan terlebih dahulu."} {!active && "Pilih satu target untuk mengaktifkan tombol."}</p>
      {(expand.error || choose.error || candidateQuery.error) && <p role="alert" className="text-sm text-red-700">{message(expand.error || choose.error || candidateQuery.error)}</p>}
      {notice && <p role="status" className="border border-green-700 bg-green-50 p-3 text-sm">{notice}</p>}
    </section>
    <section className={panel} aria-label="Tabel target peta">
      <h2 className="text-sm font-black">Target {descriptor.label}</h2><input type="search" aria-label="Cari target peta" value={search} onChange={(event) => { setSearch(event.target.value); setPage(1); }} placeholder="Cari data target…" className={`${control} w-full`} />
      <div className="overflow-x-auto"><table className="w-full min-w-[700px] text-left text-xs"><thead><tr>{["Baris", "IDPEL / Nama", "Koordinat", "Hasil", "Kandidat", "Aksi"].map((label) => <th className="p-3" key={label}>{label}</th>)}</tr></thead><tbody>{pageRows.map((row) => <tr key={row.id} onClick={() => { if (!choose.isPending) select(row.id); }} aria-selected={selected === row.id} className={`cursor-pointer border-t ${selected === row.id ? "bg-blue-50" : "hover:bg-gray-50"}`}><td className="p-3">{row.row_number}</td><td className="p-3">{displayValue(row.fields.idpel)}<p>{displayValue(row.fields.nama)}</p></td><td className="p-3">{coordinates(row.fields) ? `${row.fields.lat}, ${row.fields.lon}` : "Koordinat belum lengkap"}</td><td className="p-3">{searchLabel[row.search_status]}</td><td className="p-3">{row.candidate_count}</td><td className="p-3"><button aria-label={`Pilih target baris ${row.row_number}`} disabled={choose.isPending} onClick={(event) => { event.stopPropagation(); select(row.id); }} className={selected === row.id ? buttonClass.primary : button}>{selected === row.id ? "Terpilih" : "Pilih target"}</button></td></tr>)}</tbody></table>{!rows.isFetching && !pageRows.length && <p className="p-5 text-center text-sm">Tidak ada target sesuai cakupan atau pencarian.</p>}</div>
      <div className="flex flex-wrap items-center justify-between gap-3 text-xs"><span>{filtered.length} baris · Halaman {page} dari {Math.max(1, Math.ceil(filtered.length / 25))}</span><div className="flex gap-3"><button className={button} disabled={page <= 1} onClick={() => setPage(page - 1)}>Target sebelumnya</button><button className={button} disabled={page * 25 >= filtered.length} onClick={() => setPage(page + 1)}>Target berikutnya</button></div></div>
    </section>
    {active && <section className={panel} aria-label="Detail target terpilih"><h2 className="font-black">Target baris {active.row_number}</h2><p className="text-sm">{displayValue(active.fields.idpel)} · {displayValue(active.fields.nama)} · {searchLabel[active.search_status]}</p>
      <details><summary className="cursor-pointer text-xs font-bold">Seluruh data target</summary><Fields fields={active.fields} /></details>
      {!coordinates(active.fields) && <p className="text-sm text-amber-900">Target belum mempunyai koordinat lengkap. Perbaiki data sumber dan unggah sebagai berkas baru sebelum mencari kandidat.</p>}
      {active.conflicts.length > 0 && <p className="text-sm text-red-700">Target berbenturan dengan PDPJ dan tidak dapat dipilihkan kandidat. Lihat rincian benturan di Data Koreksi.</p>}
      {active.warnings.length > 0 && <p className="text-sm text-amber-900">Koordinat sama dengan baris PDPJ; periksa bukti identitas dan detail sumber sebelum memilih.</p>}
      {choice.isError && <p role="alert" className="text-sm text-red-700">{message(choice.error)}</p>}
      {choice.data?.current?.candidate_id && <div className="space-y-2 border-2 border-green-700 bg-green-50 p-3 text-sm"><p className="font-bold">Pilihan aktif: {displayValue(selectedChoice?.fields?.idpel)} · {selectedChoice?.distance_meters?.toFixed(2)} m</p><p>Dipilih oleh {choice.data.current.actor} · Versi pencarian {choice.data.current.generation}. Pilihan ini tetap disimpan ketika radius berubah.</p><details><summary className="cursor-pointer font-bold">Detail pilihan aktif</summary><Fields fields={selectedChoice?.fields ?? {}} /></details><button disabled={!canChoose} className={button} onClick={() => choose.mutate(null)}>Batalkan pilihan</button></div>}
      <label className="flex flex-col gap-1 text-xs font-bold">Alasan perubahan pilihan<textarea aria-label="Alasan perubahan pilihan" disabled={choose.isPending} placeholder="Wajib untuk mengganti atau membatalkan pilihan" maxLength={1000} value={reason} onChange={(event) => setReason(event.target.value)} className={control} /></label>
      {choice.data && choice.data.history.length > 0 && <details><summary className="cursor-pointer text-xs font-bold">Riwayat pilihan ({choice.data.history.length})</summary><ol className="mt-3 space-y-3">{choice.data.history.map((event) => <li key={event.id} className="border p-3 text-xs"><p>Revisi {event.revision} · {event.actor} · {new Date(event.created_at + "Z").toLocaleString("id-ID")}</p><p>{event.candidate_id ? `IDPEL ${displayValue(event.candidate.fields?.idpel)} · ${event.candidate.distance_meters?.toFixed(2)} m` : "Pilihan dibatalkan"} · Versi {event.generation}</p><p>{event.reason}</p></li>)}</ol></details>}
    </section>}
    {requested && requested.id === selected && <section className={panel} aria-label="Kandidat target peta"><h2 className="font-black">Kandidat dalam radius {requested.radius} m</h2>{candidateQuery.isFetching || blockedBySearch ? <p role="status" className="text-sm">Memuat kandidat…</p> : candidateQuery.isSuccess && !candidates.length ? <p className="text-sm">Tidak ada kandidat dalam radius ini.</p> : null}<p className="text-xs">{candidates.length} kandidat tersimpan. Jarak dihitung dari koordinat target sebelum koreksi.</p>
      <div className="grid gap-4 lg:grid-cols-2">{visibleCandidates.map((candidate) => <CandidateCard key={candidate.id} candidate={candidate} selected={choice.data?.current?.candidate_id === candidate.id} disabled={!canChoose || !candidates.some((item) => item.id === candidate.id)} choose={() => choose.mutate(candidate.id)} />)}</div>
      <div className="flex flex-wrap items-center justify-between gap-3 text-xs"><span>Halaman kandidat {candidatePage} dari {Math.max(1, Math.ceil(candidates.length / 10))}</span><div className="flex gap-3"><button className={button} disabled={candidatePage <= 1} onClick={() => setCandidatePage(candidatePage - 1)}>Kandidat sebelumnya</button><button className={button} disabled={candidatePage * 10 >= candidates.length} onClick={() => setCandidatePage(candidatePage + 1)}>Kandidat berikutnya</button></div></div>
    </section>}
  </div>;
}

function Fields({ fields }: { fields: CorrectionCandidate["fields"] }) {
  return <dl className="mt-3 grid gap-2 sm:grid-cols-2">{PDPJ_FIELDS.filter((field) => fields[field.key] !== undefined && fields[field.key] !== null && fields[field.key] !== "").map((field) => <div key={field.key} className="min-w-0 text-xs"><dt className="font-bold">{field.label}</dt><dd className="break-words">{displayValue(fields[field.key])}</dd></div>)}</dl>;
}

function CandidateCard({ candidate, selected, disabled, choose }: { candidate: CorrectionCandidate; selected: boolean; disabled: boolean; choose: () => void }) {
  return <article id={`candidate-${candidate.id}`} tabIndex={-1} className={`space-y-3 rounded-sm border-2 p-4 focus:ring-2 focus:ring-blue-500 ${selected ? "border-green-700 bg-green-50" : "border-neo-border"}`} aria-label={`Kandidat peta ${candidate.rank}`}><h3 className="text-sm font-black">Kandidat {candidate.rank} · {displayValue(candidate.fields.idpel)}</h3><p className="text-sm">{displayValue(candidate.fields.nama)} · <strong>{candidate.distance_meters.toFixed(2)} m</strong></p><Fields fields={candidate.fields} /><details><summary className="cursor-pointer text-xs font-bold">Sumber kandidat ({candidate.observations.length})</summary>{candidate.observations.map((source, index) => <div key={index} className="mt-3 border p-3 text-xs"><p className="font-bold">{source.dataset_type} · {source.filename} · Baris {source.row_number}</p><p>{source.source_sheet}</p><Fields fields={source.fields} /></div>)}</details><button type="button" disabled={disabled || selected} onClick={choose} className={selected ? buttonClass.success : buttonClass.primary}>{selected ? "Kandidat terpilih" : `Pilih kandidat ${candidate.rank}`}</button></article>;
}
