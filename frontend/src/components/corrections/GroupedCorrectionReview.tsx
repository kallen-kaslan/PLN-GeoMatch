import { useEffect, useRef, useState } from "react";
import { Link } from "react-router-dom";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { LoaderCircle } from "lucide-react";
import { correctionApi, type AutomaticPreview, type AutomaticReviewGroup, type CorrectionCandidate, type CorrectionChoice } from "@/lib/corrections";
import type { ApiError } from "@/lib/api";
import { buttonClass } from "@/lib/button";
import { displayValue, type CorrectionKind } from "@/lib/master";
import { useAppStore } from "@/store/app";
import { CandidateCoordinateSource } from "./CandidateCoordinateSource";
import { AdvancedCandidateSearch } from "./AdvancedCandidateSearch";

const control = "min-w-0 rounded-lg border border-ui-border bg-white px-3 py-2 text-sm disabled:opacity-50";
const count = (value: number) => value.toLocaleString("id-ID");
const reasonLabel = (reason: string) => ({ equal_distance: "Jarak sama", candidates_used: "Kandidat sudah digunakan / dicadangkan", outside_radius: "Di luar radius", no_candidates: "Tanpa kandidat", pdpj_conflict: "Benturan PDPJ", invalid_data: "Data perlu diperbaiki", incomplete_coordinates: "Koordinat belum lengkap" })[reason] ?? reason;

export function GroupedCorrectionReview({ kind, processId, preview, mapUrl, onResolved, onBusyChange, disabled }: {
  kind: CorrectionKind; processId: number; preview: AutomaticPreview; mapUrl: string; disabled: boolean;
  onResolved: (notice: string) => void; onBusyChange: (value: boolean) => void;
}) {
  const [open, setOpen] = useState(false);
  const [search, setSearch] = useState("");
  const [reason, setReason] = useState("all");
  const [page, setPage] = useState(1);
  const [selected, setSelected] = useState<string | null>(null);
  const groups = useQuery<Awaited<ReturnType<typeof correctionApi.reviewGroups>>, ApiError>({
    queryKey: ["automatic-review-groups", kind, processId, preview.fingerprint],
    queryFn: ({ signal }) => correctionApi.reviewGroups(kind, processId, { generation: preview.generation, radius_meters: preview.radius_meters, fingerprint: preview.fingerprint, tie_strategy: preview.tie_strategy }, signal),
    enabled: open, retry: false, gcTime: 0, refetchOnWindowFocus: false,
  });
  const filtered = (groups.data?.groups ?? []).filter((group) => (reason === "all" || !!group.reason_counts[reason]) && (!search.trim() || group.candidates.some((candidate) => candidate.idpel.includes(search.trim())) || group.targets.some((target) => String(target.row_number).includes(search.trim()))));
  const pages = Math.max(1, Math.ceil(filtered.length / 10));
  const items = filtered.slice((Math.min(page, pages) - 1) * 10, Math.min(page, pages) * 10);
  const active = filtered.find((group) => group.id === selected) ?? items[0];
  return <section aria-label="Tinjauan kelompok koordinat dan IDPEL" className="space-y-4 rounded-lg border border-ui-border p-3 sm:p-4">
    <div className="flex flex-wrap items-center justify-between gap-3"><div><h3 className="text-sm font-semibold">Tinjauan per kelompok</h3><p className="mt-1 text-xs text-ui-muted">Target yang berbagi IDPEL atau koordinat kandidat terdekat ditampilkan bersama. Koordinat dikelompokkan dengan presisi asli.</p></div><button type="button" disabled={disabled} className={buttonClass.secondary} onClick={() => setOpen(!open)}>{open ? "Tutup tinjauan kelompok" : "Tinjau per kelompok koordinat / IDPEL"}</button></div>
    {open && <>
      {groups.isPending && <p role="status" className="flex items-center gap-2 text-sm"><LoaderCircle size={16} className="animate-spin" />Mengelompokkan target dan memeriksa pemakaian IDPEL...</p>}
      {groups.error && <p role="alert" className="text-sm text-red-700">{groups.error.message} <button type="button" className="font-semibold underline" onClick={() => onResolved("Memuat ulang pratinjau untuk menyesuaikan tinjauan kelompok.")}>Muat ulang pratinjau</button></p>}
      {groups.data && <>
        <p className="text-sm font-semibold">{count(groups.data.target_count)} target dalam {count(groups.data.group_count)} kelompok. Satu target dihitung satu kali.</p>
        <div className="flex flex-col gap-3 sm:flex-row"><input type="search" aria-label="Cari kelompok IDPEL atau baris" value={search} onChange={(event) => { setSearch(event.target.value); setPage(1); setSelected(null); }} placeholder="Cari IDPEL atau nomor baris..." className={`${control} flex-1`} /><select aria-label="Filter alasan kelompok" value={reason} onChange={(event) => { setReason(event.target.value); setPage(1); setSelected(null); }} className={control}><option value="all">Semua alasan</option>{Object.keys(preview.review_reasons).map((item) => <option key={item} value={item}>{reasonLabel(item)}</option>)}</select></div>
        <div className="grid gap-3 lg:grid-cols-2">{items.map((group, index) => <button type="button" key={group.id} aria-label={`Tinjau kelompok mulai baris ${group.targets[0].row_number}`} aria-pressed={active?.id === group.id} disabled={disabled} onClick={() => setSelected(group.id)} className={`space-y-2 rounded-lg border p-3 text-left text-xs ${active?.id === group.id ? "border-blue-700 bg-blue-50" : "border-ui-border bg-white"}`}><p className="font-semibold">Kelompok {(Math.min(page, pages) - 1) * 10 + index + 1} · {count(group.target_count)} target · {count(group.candidate_count)} IDPEL</p><p>Baris: {group.targets.slice(0, 8).map((target) => target.row_number).join(", ")}{group.target_count > 8 && "..."}</p><p>IDPEL: {group.candidates.slice(0, 4).map((candidate) => candidate.idpel).join(", ") || "Belum ada kandidat dalam radius"}{group.candidates.length > 4 && "..."}</p><p>{Object.entries(group.reason_counts).map(([key, total]) => `${reasonLabel(key)}: ${count(total)}`).join(" · ")}</p></button>)}</div>
        {!items.length && <p className="text-xs">Tidak ada kelompok sesuai pencarian.</p>}
        <div className="flex flex-wrap items-center justify-between gap-3 text-xs"><p>{count(filtered.length)} kelompok sesuai filter · Halaman {Math.min(page, pages)} dari {pages}</p><div className="flex gap-2"><button type="button" disabled={disabled || page <= 1} onClick={() => { setPage(page - 1); setSelected(null); }} className={buttonClass.secondary}>Kelompok sebelumnya</button><button type="button" disabled={disabled || page >= pages} onClick={() => { setPage(page + 1); setSelected(null); }} className={buttonClass.secondary}>Kelompok berikutnya</button></div></div>
        {active && <ReviewGroup key={active.id} group={active} kind={kind} processId={processId} preview={preview} mapUrl={mapUrl} onResolved={onResolved} onBusyChange={onBusyChange} disabled={disabled} />}
      </>}
    </>}
  </section>;
}

function ReviewGroup({ group, kind, processId, preview, mapUrl, onResolved, onBusyChange, disabled }: {
  group: AutomaticReviewGroup; kind: CorrectionKind; processId: number; preview: AutomaticPreview; mapUrl: string;
  onResolved: (notice: string) => void; onBusyChange: (value: boolean) => void; disabled: boolean;
}) {
  const [recordId, setRecordId] = useState(group.targets[0].record_id);
  const [visible, setVisible] = useState(10);
  const target = group.targets.find((item) => item.record_id === recordId)!;
  return <section aria-label="Perbandingan kelompok terpilih" className="space-y-4 rounded-lg border border-blue-200 bg-slate-50 p-3 sm:p-4">
    <h4 className="text-sm font-semibold">Bandingkan {count(group.target_count)} target dan {count(group.candidate_count)} IDPEL</h4>
    {group.coordinates.length > 0 && <p className="break-words font-mono text-xs">Koordinat kandidat: {group.coordinates.slice(0, 4).map((coordinate) => `${coordinate.lat}, ${coordinate.lon}`).join(" · ")}{group.coordinates.length > 4 && ` · ${count(group.coordinates.length)} koordinat dalam kelompok ini`}</p>}
    <div className="flex flex-wrap gap-2">{group.targets.slice(0, visible).map((item) => <button type="button" key={item.record_id} aria-pressed={recordId === item.record_id} disabled={disabled} onClick={() => setRecordId(item.record_id)} className={recordId === item.record_id ? buttonClass.primary : buttonClass.secondary}>Baris {item.row_number}</button>)}{visible < group.target_count && <button type="button" className={buttonClass.secondary} disabled={disabled} onClick={() => setVisible(visible + 20)}>Tampilkan target berikutnya</button>}</div>
    {group.candidates.some((candidate) => candidate.used_by.length) && <ul className="space-y-1 text-xs text-amber-900">{group.candidates.filter((candidate) => candidate.used_by.length).map((candidate) => <li key={`${candidate.idpel}-${candidate.lat}-${candidate.lon}`}>IDPEL {candidate.idpel} sudah dipilih untuk baris {candidate.used_by.map((owner) => owner.row_number).join(", ")}. {candidate.used_by.map((owner) => <Link key={owner.record_id} to={`${mapUrl}&record_id=${owner.record_id}&map_view=map`} className="ml-2 font-semibold underline">Tinjau pilihan baris {owner.row_number}</Link>)}</li>)}</ul>}
    <ReviewTarget key={recordId} kind={kind} processId={processId} preview={preview} target={target} groupCandidates={group.candidates} mapUrl={mapUrl} onResolved={onResolved} onBusyChange={onBusyChange} disabled={disabled} />
  </section>;
}

export function ReviewTarget({ kind, processId, preview, target, groupCandidates, mapUrl, onResolved, onBusyChange, disabled }: {
  kind: CorrectionKind; processId: number; preview: AutomaticPreview; target: AutomaticPreview["review"][number]; mapUrl: string;
  onResolved: (notice: string) => void; onBusyChange: (value: boolean) => void; disabled: boolean;
  groupCandidates: AutomaticReviewGroup["candidates"];
}) {
  const client = useQueryClient();
  const actor = useAppStore((state) => state.user?.username ?? "");
  const [offset, setOffset] = useState(0);
  const [reason, setReason] = useState("");
  const operation = useRef<{ intent: string; key: string } | null>(null);
  const detail = useQuery({ queryKey: ["corrections", kind, "review-detail", processId, preview.generation, preview.radius_meters, target.record_id, offset, preview.fingerprint],
    queryFn: ({ signal }) => correctionApi.reviewDetail(kind, processId, target.record_id, preview.generation, preview.radius_meters, offset, signal), retry: false });
  const choiceKey = ["correction-choice", kind, processId, target.record_id, preview.generation];
  const choice = useQuery({ queryKey: choiceKey, queryFn: () => correctionApi.choice(kind, processId, target.record_id, preview.generation), staleTime: 0 });
  const save = useMutation<CorrectionChoice, ApiError, CorrectionCandidate>({
    mutationFn: (candidate) => {
      const intent = JSON.stringify([candidate.id, reason.trim(), choice.data!.revision]);
      if (operation.current?.intent !== intent) operation.current = { intent, key: crypto.randomUUID() };
      return correctionApi.choose(kind, processId, target.record_id, { generation: preview.generation, expected_revision: choice.data!.revision, candidate_id: candidate.id, actor, reason: reason.trim(), request_key: operation.current.key });
    },
    onSuccess: (data) => {
      client.setQueryData(choiceKey, data);
      for (const key of ["corrections", "correction-choice", "correction-results", "correction-decisions", "process-history", "correction-map-candidates"]) void client.invalidateQueries({ queryKey: [key] });
      onResolved(`Pilihan IDPEL ${data.current?.candidate.fields?.idpel ?? ""} untuk baris ${target.row_number} tersimpan. Pratinjau dihitung ulang; target lain tetap dipertahankan.`);
    },
    onError: () => { void client.invalidateQueries({ queryKey: choiceKey }); void client.invalidateQueries({ queryKey: ["corrections", kind, "advanced-candidates"] }); void detail.refetch(); },
  });
  useEffect(() => { onBusyChange(save.isPending); return () => onBusyChange(false); }, [save.isPending, onBusyChange]);
  const fields = detail.data?.fields;
  const hasChoice = !!choice.data?.current;
  const suggestion = preview.suggestions?.find((item) => item.record_id === target.record_id);
  return <div className="space-y-3">
    <div className="flex flex-wrap items-center justify-between gap-2"><h5 className="text-sm font-semibold">Target baris {target.row_number} · {reasonLabel(target.reason)}</h5><Link to={`${mapUrl}&record_id=${target.record_id}&map_view=map`} className="text-xs font-semibold underline">Buka target ini di Peta Koreksi</Link></div>
    {suggestion && <p className="rounded-lg bg-amber-50 p-3 text-sm font-semibold text-amber-950">Usulan sistem: IDPEL {suggestion.idpel} · {suggestion.distance_meters.toLocaleString("id-ID", { minimumFractionDigits: 2, maximumFractionDigits: 2 })} m. Verifikasi identitas sebelum menyimpan.</p>}
    {fields && <dl className="grid gap-3 text-xs sm:grid-cols-2 lg:grid-cols-4">{[
      ["Nama target", fields.nama], ["Meter / referensi target", fields.meter_ref || fields.survey_ref || fields.target_ref],
      ["Alamat target", fields.alamat], ["Gardu target", fields.kode_gardu],
      ["IDPEL awal", fields.idpel], ["Koordinat target", `${displayValue(fields.lat)}, ${displayValue(fields.lon)}`],
    ].map(([label, value]) => <div key={String(label)}><dt className="font-semibold text-ui-muted">{label}</dt><dd className="mt-1 break-words">{displayValue(value)}</dd></div>)}</dl>}
    {(detail.isPending || choice.isPending) && <p role="status" className="text-sm">Memuat bukti kandidat dan pilihan terbaru...</p>}
    {(detail.isError || choice.isError) && <p role="alert" className="text-sm text-red-700">Bukti belum dapat dimuat. <button type="button" className="underline" onClick={() => { void detail.refetch(); void choice.refetch(); }}>Coba lagi</button></p>}
    {hasChoice && <p role="alert" className="text-sm text-amber-900">Target ini sudah memiliki keputusan tersimpan. <button type="button" onClick={() => onResolved("Memperbarui pratinjau sesuai keputusan terbaru.")} className="font-semibold underline">Perbarui pratinjau</button></p>}
    <label className="flex flex-col gap-1.5 text-xs font-semibold">Dasar verifikasi pilihan<input aria-label="Dasar verifikasi pilihan" value={reason} maxLength={1000} onChange={(event) => setReason(event.target.value)} disabled={disabled || hasChoice} placeholder="Contoh: nomor meter cocok dengan bukti lapangan" className={control} /></label>
    <p className="text-xs text-ui-muted">Pilih setelah identitas terverifikasi. IDPEL yang sudah digunakan target lain tetap terkunci. Jarak memakai nilai asli; tampilan dua desimal hanya untuk keterbacaan.</p>
    {fields && <AdvancedCandidateSearch kind={kind} processId={processId} recordId={target.record_id} rowNumber={target.row_number} generation={preview.generation} radius={preview.radius_meters} fingerprint={preview.fingerprint} fields={fields} mapUrl={mapUrl} disabled={disabled || save.isPending || hasChoice} canChoose={!!reason.trim() && !!choice.data && !choice.isFetching && !choice.isError && !hasChoice} onChoose={(candidate) => save.mutate(candidate)} />}
    <div className="overflow-x-auto rounded-lg border border-ui-border"><table className="w-full min-w-[900px] text-left text-xs"><thead className="bg-ui-table-head"><tr>{["IDPEL / Nama", "Meter", "Alamat / Gardu", "Jarak", "Sumber koordinat", "Status / Pilihan"].map((label) => <th key={label} className="p-3">{label}</th>)}</tr></thead><tbody>{detail.data?.candidates.map((candidate) => {
      const owners = (candidate.used_by ?? []).filter((owner) => owner.record_id !== target.record_id);
      const proposed = groupCandidates.find((item) => item.idpel === String(candidate.fields.idpel))?.proposed_for;
      return <tr key={candidate.id} className="border-t border-ui-border bg-white"><td className="p-3"><p className="font-mono font-semibold">{displayValue(candidate.fields.idpel)}</p><p className="mt-1">{displayValue(candidate.fields.nama)}</p></td><td className="p-3">{displayValue(candidate.fields.nomor_meter_kwh || candidate.fields.nomor_meter_prepaid || candidate.fields.meter_ref || candidate.fields.target_ref)}</td><td className="p-3"><p>{displayValue(candidate.fields.alamat)}</p><p className="mt-1">Gardu: {displayValue(candidate.fields.kode_gardu)}</p></td><td className="p-3 whitespace-nowrap">{candidate.distance_meters.toLocaleString("id-ID", { minimumFractionDigits: 2, maximumFractionDigits: 2 })} m</td><td className="p-3"><CandidateCoordinateSource fields={candidate.fields} /></td><td className="space-y-2 p-3">{proposed && proposed.record_id !== target.record_id && <p className="text-blue-900">Diusulkan otomatis untuk baris {proposed.row_number}. Usulan diperbarui setelah tinjauan.</p>}{owners.length > 0 && <p className="text-amber-900">Dipakai baris {owners.map((owner) => owner.row_number).join(", ")}</p>}<button type="button" aria-label={`Pilih IDPEL ${candidate.fields.idpel} untuk baris ${target.row_number}`} disabled={disabled || save.isPending || choice.isFetching || !choice.data || hasChoice || owners.length > 0 || !reason.trim()} onClick={() => save.mutate(candidate)} className={buttonClass.primary}>Pilih untuk target ini</button></td></tr>;
    })}</tbody></table></div>
    {detail.data?.candidates_total === 0 && <p className="text-xs">Tidak ada kandidat dalam radius ini. Tinjau data sumber atau perluas pemeriksaan melalui Data Koreksi jika sesuai kondisi lapangan.</p>}
    {detail.data && detail.data.candidates_total > 10 && <div className="flex flex-wrap items-center justify-between gap-3 text-xs"><p>Kandidat {offset + 1}–{Math.min(offset + 10, detail.data.candidates_total)} dari {count(detail.data.candidates_total)}</p><div className="flex gap-2"><button type="button" disabled={disabled || offset === 0} onClick={() => setOffset(offset - 10)} className={buttonClass.secondary}>Kandidat sebelumnya</button><button type="button" disabled={disabled || offset + 10 >= detail.data.candidates_total} onClick={() => setOffset(offset + 10)} className={buttonClass.secondary}>Kandidat berikutnya</button></div></div>}
    {save.isPending && <p role="status" className="flex items-center gap-2 text-sm"><LoaderCircle size={16} className="animate-spin" />Menyimpan pilihan hasil verifikasi...</p>}
    {save.error && <p role="alert" className="text-sm text-red-700">{save.error.message}</p>}
  </div>;
}
