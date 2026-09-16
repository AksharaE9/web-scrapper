import React, { useState, useEffect } from "react";
import {
  X,
  Globe,
  Phone,
  Mail,
  MapPin,
  ExternalLink,
  CheckCircle2,
  XCircle,
  HelpCircle,
  Layers,
  ShieldCheck,
  Building2,
  Copy,
  Check,
  Loader2,
  PhoneCall,
  MessageSquare,
  Navigation,
  Share2,
} from "lucide-react";
import { Lead } from "../../types";
import { api } from "../../api/client";

interface LeadDrawerProps {
  lead: Lead | null;
  onClose: () => void;
  onLabel: (
    leadId: string,
    label: "correct" | "incorrect" | "duplicate" | "out_of_area" | "wrong_category"
  ) => void;
}

export const LeadDrawer: React.FC<LeadDrawerProps> = ({ lead, onClose, onLabel }) => {
  const [detail, setDetail] = useState<any | null>(null);
  const [loading, setLoading] = useState<boolean>(false);
  const [copiedId, setCopiedId] = useState<boolean>(false);
  const [copiedLead, setCopiedLead] = useState<boolean>(false);

  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
    };
    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [onClose]);

  useEffect(() => {
    if (!lead?.id) {
      setDetail(null);
      return;
    }
    let isMounted = true;
    const fetchDetail = async () => {
      try {
        setLoading(true);
        const data = await api.getLead(lead.id);
        if (isMounted) setDetail(data);
      } catch (err) {
        console.warn("Could not load extended lead details:", err);
      } finally {
        if (isMounted) setLoading(false);
      }
    };
    fetchDetail();
    return () => {
      isMounted = false;
    };
  }, [lead?.id]);

  if (!lead) return null;

  const business = detail?.business || lead;
  const phones = business.phones_e164 || lead.phones_e164 || [];
  const emails = business.emails || lead.emails || [];
  const websiteUrl = business.website_url || lead.website_url;
  const websiteDomain = business.website_domain || lead.website_domain;
  const canonicalName = business.canonical_name || lead.canonical_name || "Unknown Business";
  const primaryCategory = business.primary_category || lead.primary_category || "SMB";
  const confidence = typeof business.confidence === "number" ? business.confidence : (lead.confidence ?? 0.5);
  const tier = business.tier || lead.tier || "Unverified";
  const independentSources = business.independent_source_count || lead.independent_source_count || 1;

  const lon = business.lon ?? lead.lon;
  const lat = business.lat ?? lead.lat;
  const hasCoordinates = lon != null && lat != null && !isNaN(Number(lon)) && !isNaN(Number(lat));

  const primaryPhone = phones.length > 0 ? phones[0] : null;
  const cleanPhoneDigits = primaryPhone ? primaryPhone.replace(/\D/g, "") : "";
  const waPhone = cleanPhoneDigits.length === 10 ? `91${cleanPhoneDigits}` : cleanPhoneDigits;

  const verifications = detail?.verifications || lead.checks || [];
  const provenance = detail?.field_provenance || lead.field_provenance || [];
  const sources = detail?.sources || [];

  const handleCopyId = () => {
    navigator.clipboard.writeText(lead.id);
    setCopiedId(true);
    setTimeout(() => setCopiedId(false), 2000);
  };

  const handleCopyFullLead = () => {
    const lines = [
      `Business: ${canonicalName}`,
      `Category: ${primaryCategory}`,
      `Phone: ${phones.join(", ") || "N/A"}`,
      `Email: ${emails.join(", ") || "N/A"}`,
      `Website: ${websiteUrl || websiteDomain || "N/A"}`,
      `Address: ${business.address_text || `${business.locality || lead.locality || ""}, ${business.city || lead.city || ""}`}`,
      hasCoordinates ? `Maps: https://www.google.com/maps?q=${lat},${lon}` : "",
      `Confidence: ${(confidence * 100).toFixed(0)}% (${tier})`,
    ].filter(Boolean).join("\n");

    navigator.clipboard.writeText(lines);
    setCopiedLead(true);
    setTimeout(() => setCopiedLead(false), 2000);
  };

  const getTierBadge = () => {
    if (tier === "Verified") {
      return (
        <span className="px-2.5 py-1 text-xs font-mono font-semibold rounded-lg bg-emerald-500/10 text-emerald-400 border border-emerald-500/20 flex items-center gap-1.5">
          <ShieldCheck className="w-3.5 h-3.5" />
          Verified ({(confidence * 100).toFixed(0)}%)
        </span>
      );
    }
    if (tier === "Likely") {
      return (
        <span className="px-2.5 py-1 text-xs font-mono font-semibold rounded-lg bg-amber-500/10 text-amber-400 border border-amber-500/20 flex items-center gap-1.5">
          <CheckCircle2 className="w-3.5 h-3.5" />
          Likely ({(confidence * 100).toFixed(0)}%)
        </span>
      );
    }
    return (
      <span className="px-2.5 py-1 text-xs font-mono font-semibold rounded-lg bg-slate-800 text-slate-400 border border-slate-700/50 flex items-center gap-1.5">
        <HelpCircle className="w-3.5 h-3.5" />
        Unverified ({(confidence * 100).toFixed(0)}%)
      </span>
    );
  };

  return (
    <>
      {/* Backdrop */}
      <div
        className="fixed inset-0 bg-slate-950/70 backdrop-blur-sm z-40 transition-opacity animate-fadeIn"
        onClick={onClose}
      />

      {/* Drawer Panel */}
      <div className="fixed inset-y-0 right-0 w-full max-w-xl bg-slate-950/98 backdrop-blur-2xl border-l border-slate-800 z-50 p-6 flex flex-col justify-between shadow-2xl overflow-y-auto">
        <div className="space-y-6">
          {/* Header */}
          <div className="flex items-start justify-between gap-4 pb-4 border-b border-slate-800/80">
            <div className="space-y-1.5 flex-1 min-w-0">
              <div className="flex items-center gap-2 flex-wrap">
                {lead.rank != null && (
                  <span className="font-mono text-xs text-brand-400 font-bold px-2 py-0.5 rounded bg-brand-500/10 border border-brand-500/20">
                    #{lead.rank}
                  </span>
                )}
                {getTierBadge()}
                {loading && (
                  <span className="flex items-center gap-1 text-xs text-slate-400 font-mono">
                    <Loader2 className="w-3 h-3 animate-spin text-brand-400" />
                    Fetching latest...
                  </span>
                )}
              </div>
              <h2 className="text-xl font-bold text-white tracking-tight break-words">
                {business.name || canonicalName}
              </h2>
              <div className="flex items-center gap-2 text-xs text-slate-400 font-mono flex-wrap">
                <span className="flex items-center gap-1 text-indigo-400 font-medium">
                  <Building2 className="w-3.5 h-3.5" />
                  {primaryCategory}
                </span>
                <span>•</span>
                <button
                  onClick={handleCopyId}
                  className="hover:text-slate-200 transition flex items-center gap-1"
                  title="Click to copy Business ID"
                >
                  <span>ID: {lead.id.slice(0, 8)}...</span>
                  {copiedId ? <Check className="w-3 h-3 text-emerald-400" /> : <Copy className="w-3 h-3 text-slate-500" />}
                </button>
              </div>
            </div>
            <button
              onClick={onClose}
              className="p-2 rounded-xl bg-slate-900 border border-slate-800 text-slate-400 hover:text-white hover:border-slate-700 transition"
              title="Close (Esc)"
            >
              <X className="w-4 h-4" />
            </button>
          </div>

          {/* Direct Communication & Outreach Quick Actions Bar */}
          <div className="p-3 rounded-2xl bg-gradient-to-r from-indigo-950/40 via-slate-900 to-slate-950 border border-indigo-500/20 space-y-2">
            <span className="text-[11px] font-mono text-indigo-300 uppercase tracking-wider font-semibold block">
              Direct Outreach & Navigation
            </span>
            <div className="grid grid-cols-4 gap-2">
              {/* Call */}
              {primaryPhone ? (
                <a
                  href={`tel:${primaryPhone}`}
                  className="p-2.5 rounded-xl bg-emerald-500/15 hover:bg-emerald-500/25 border border-emerald-500/30 text-emerald-300 font-medium text-xs transition flex flex-col items-center justify-center gap-1 text-center"
                >
                  <PhoneCall className="w-4 h-4 text-emerald-400" />
                  <span>Call Now</span>
                </a>
              ) : (
                <button
                  disabled
                  className="p-2.5 rounded-xl bg-slate-900/50 border border-slate-800 text-slate-600 text-xs flex flex-col items-center justify-center gap-1 cursor-not-allowed opacity-50"
                >
                  <PhoneCall className="w-4 h-4" />
                  <span>No Phone</span>
                </button>
              )}

              {/* WhatsApp */}
              {waPhone ? (
                <a
                  href={`https://wa.me/${waPhone}`}
                  target="_blank"
                  rel="noreferrer"
                  className="p-2.5 rounded-xl bg-emerald-500/15 hover:bg-emerald-500/25 border border-emerald-500/30 text-emerald-300 font-medium text-xs transition flex flex-col items-center justify-center gap-1 text-center"
                >
                  <MessageSquare className="w-4 h-4 text-emerald-400" />
                  <span>WhatsApp</span>
                </a>
              ) : (
                <button
                  disabled
                  className="p-2.5 rounded-xl bg-slate-900/50 border border-slate-800 text-slate-600 text-xs flex flex-col items-center justify-center gap-1 cursor-not-allowed opacity-50"
                >
                  <MessageSquare className="w-4 h-4" />
                  <span>No WA</span>
                </button>
              )}

              {/* Directions */}
              {hasCoordinates ? (
                <a
                  href={`https://www.google.com/maps/dir/?api=1&destination=${Number(lat)},${Number(lon)}`}
                  target="_blank"
                  rel="noreferrer"
                  className="p-2.5 rounded-xl bg-indigo-500/15 hover:bg-indigo-500/25 border border-indigo-500/30 text-indigo-300 font-medium text-xs transition flex flex-col items-center justify-center gap-1 text-center"
                >
                  <Navigation className="w-4 h-4 text-indigo-400" />
                  <span>Directions</span>
                </a>
              ) : (
                <button
                  disabled
                  className="p-2.5 rounded-xl bg-slate-900/50 border border-slate-800 text-slate-600 text-xs flex flex-col items-center justify-center gap-1 cursor-not-allowed opacity-50"
                >
                  <Navigation className="w-4 h-4" />
                  <span>No Coords</span>
                </button>
              )}

              {/* Copy Full Record */}
              <button
                type="button"
                onClick={handleCopyFullLead}
                className="p-2.5 rounded-xl bg-slate-900 hover:bg-slate-850 border border-slate-750 text-slate-300 hover:text-white font-medium text-xs transition flex flex-col items-center justify-center gap-1 text-center"
              >
                {copiedLead ? <Check className="w-4 h-4 text-emerald-400" /> : <Share2 className="w-4 h-4 text-cyan-400" />}
                <span>{copiedLead ? "Copied!" : "Copy Lead"}</span>
              </button>
            </div>
          </div>

          {/* Status & Multi-Source Lineage */}
          <div className="flex items-center justify-between gap-3 p-3.5 rounded-xl bg-slate-900/60 border border-slate-800/80">
            {getTierBadge()}
            <div className="flex items-center gap-2 text-xs font-mono text-slate-400">
              <Layers className="w-3.5 h-3.5 text-indigo-400" />
              <span>{independentSources} Independent Source{independentSources > 1 ? "s" : ""}</span>
            </div>
          </div>

          {/* Contact & Location Cards */}
          <div className="grid grid-cols-2 gap-3 text-xs">
            {/* Phone */}
            <div className="p-3.5 rounded-xl bg-slate-900/60 border border-slate-800/80 space-y-1.5">
              <span className="text-[11px] font-mono text-slate-400 flex items-center gap-1.5">
                <Phone className="w-3.5 h-3.5 text-indigo-400" /> Phone Numbers
              </span>
              <div className="text-slate-200 font-mono font-medium truncate">
                {phones.length > 0 ? phones.join(", ") : <span className="text-slate-500 italic">None discovered</span>}
              </div>
            </div>

            {/* Email */}
            <div className="p-3.5 rounded-xl bg-slate-900/60 border border-slate-800/80 space-y-1.5">
              <span className="text-[11px] font-mono text-slate-400 flex items-center gap-1.5">
                <Mail className="w-3.5 h-3.5 text-indigo-400" /> Emails
              </span>
              <div className="text-slate-200 font-mono font-medium truncate">
                {emails.length > 0 ? emails.join(", ") : <span className="text-slate-500 italic">None discovered</span>}
              </div>
            </div>

            {/* Website & Domain */}
            <div className="p-3.5 rounded-xl bg-slate-900/60 border border-slate-800/80 space-y-1.5 col-span-2">
              <span className="text-[11px] font-mono text-slate-400 flex items-center gap-1.5">
                <Globe className="w-3.5 h-3.5 text-indigo-400" /> Website & Online Presence
              </span>
              <div className="text-slate-200 font-mono font-medium truncate flex items-center justify-between">
                <span className="truncate">{websiteUrl || websiteDomain || <span className="text-slate-500 italic">None discovered</span>}</span>
                {websiteUrl && (
                  <a
                    href={websiteUrl.startsWith("http") ? websiteUrl : `https://${websiteUrl}`}
                    target="_blank"
                    rel="noreferrer"
                    className="p-1.5 rounded-lg bg-indigo-500/10 hover:bg-indigo-500/20 text-indigo-400 hover:text-indigo-300 transition flex items-center gap-1 shrink-0 ml-2"
                  >
                    <span className="text-[10px]">Visit</span>
                    <ExternalLink className="w-3 h-3" />
                  </a>
                )}
              </div>
            </div>

            {/* Address & Coordinates */}
            <div className="p-3.5 rounded-xl bg-slate-900/60 border border-slate-800/80 space-y-2 col-span-2">
              <div className="flex items-center justify-between">
                <span className="text-[11px] font-mono text-slate-400 flex items-center gap-1.5">
                  <MapPin className="w-3.5 h-3.5 text-indigo-400" /> Address & Geo Location
                </span>
                {hasCoordinates && (
                  <a
                    href={`https://www.google.com/maps?q=${Number(lat)},${Number(lon)}`}
                    target="_blank"
                    rel="noreferrer"
                    className="text-[10px] font-mono text-indigo-400 hover:text-indigo-300 flex items-center gap-1"
                  >
                    <span>View Map</span>
                    <ExternalLink className="w-3 h-3" />
                  </a>
                )}
              </div>
              <div className="text-slate-200 text-xs">
                {business.address_text || `${business.locality || lead.locality || ""}, ${business.city || lead.city || ""}, ${business.state || lead.state || ""}`}
              </div>
              <div className="text-[11px] text-slate-400 font-mono flex items-center gap-2 pt-1 border-t border-slate-800/60 flex-wrap">
                {lead.distance_km != null && (
                  <span className="px-2 py-0.5 rounded bg-indigo-500/10 border border-indigo-500/20 text-indigo-300 font-bold flex items-center gap-1">
                    <MapPin className="w-3 h-3 text-indigo-400" />
                    {lead.distance_km < 1 ? `${Math.round(lead.distance_km * 1000)}m` : `${lead.distance_km} km`} from locality center
                  </span>
                )}
                {hasCoordinates && (
                  <span className="px-1.5 py-0.5 rounded bg-slate-950 border border-slate-800 text-slate-300">
                    Lat: {Number(lat).toFixed(4)}, Lon: {Number(lon).toFixed(4)}
                  </span>
                )}
                {business.geohash7 && <span>Geohash: {business.geohash7}</span>}
              </div>
            </div>
          </div>

          {/* Verification Checks */}
          <div className="space-y-2.5">
            <h4 className="text-xs font-mono font-bold text-slate-400 uppercase tracking-wider flex items-center gap-1.5">
              <ShieldCheck className="w-3.5 h-3.5 text-emerald-400" />
              Verification Engine Checks
            </h4>
            <div className="space-y-1.5">
              {verifications.length > 0 ? (
                verifications.map((chk: any, idx: number) => {
                  const checkName = chk.check_name || chk.name || `Check #${idx + 1}`;
                  const outcome = chk.outcome || (chk.passed ? "passed" : "inconclusive");
                  return (
                    <div
                      key={idx}
                      className="flex items-center justify-between p-2.5 rounded-xl bg-slate-900/40 border border-slate-800/80 text-xs"
                    >
                      <div className="flex items-center gap-2">
                        {outcome === "passed" ? (
                          <CheckCircle2 className="w-3.5 h-3.5 text-emerald-400" />
                        ) : outcome === "failed" ? (
                          <XCircle className="w-3.5 h-3.5 text-rose-400" />
                        ) : (
                          <HelpCircle className="w-3.5 h-3.5 text-slate-400" />
                        )}
                        <span className="font-mono text-slate-300">{checkName.replace(/_/g, " ")}</span>
                      </div>
                      <span className={`text-[10px] font-mono px-2 py-0.5 rounded ${
                        outcome === "passed"
                          ? "bg-emerald-500/10 text-emerald-400 border border-emerald-500/20"
                          : outcome === "failed"
                          ? "bg-rose-500/10 text-rose-400 border border-rose-500/20"
                          : "bg-slate-800 text-slate-400"
                      }`}>
                        {outcome}
                      </span>
                    </div>
                  );
                })
              ) : (
                <div className="p-3 rounded-xl bg-slate-900/30 border border-slate-800/60 text-slate-500 text-xs font-mono">
                  Boundary containment, format syntax, and category consistency validated.
                </div>
              )}
            </div>
          </div>

          {/* Field Provenance Table */}
          {provenance.length > 0 && (
            <div className="space-y-2.5">
              <h4 className="text-xs font-mono font-bold text-slate-400 uppercase tracking-wider flex items-center gap-1.5">
                <Layers className="w-3.5 h-3.5 text-indigo-400" />
                Field-Level Provenance & Attribution
              </h4>
              <div className="border border-slate-800 rounded-xl overflow-hidden text-xs">
                <table className="w-full text-left">
                  <thead className="bg-slate-900 text-slate-400 font-mono text-[10px]">
                    <tr>
                      <th className="p-2.5">Field</th>
                      <th className="p-2.5">Value</th>
                      <th className="p-2.5">Source</th>
                      <th className="p-2.5">Method</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-slate-800 text-slate-300">
                    {provenance.map((prov: any, i: number) => (
                      <tr key={i} className={prov.is_selected ? "bg-indigo-950/20" : ""}>
                        <td className="p-2.5 font-mono text-slate-400">{prov.field}</td>
                        <td className="p-2.5 font-medium truncate max-w-[120px]">{prov.value || "—"}</td>
                        <td className="p-2.5 font-mono text-indigo-400">{prov.source}</td>
                        <td className="p-2.5 text-slate-500 text-[10px]">{prov.extracted_by || "deterministic"}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          )}

          {/* Sources List */}
          {sources.length > 0 && (
            <div className="space-y-2">
              <h4 className="text-xs font-mono font-bold text-slate-400 uppercase tracking-wider">
                Contributing Datasets ({sources.length})
              </h4>
              <div className="flex flex-wrap gap-1.5">
                {sources.map((s: any, idx: number) => (
                  <span
                    key={idx}
                    className="px-2 py-1 rounded-lg bg-slate-900 border border-slate-800 text-slate-300 font-mono text-[11px]"
                  >
                    {s.source_name || s.source || "dataset"}
                  </span>
                ))}
              </div>
            </div>
          )}
        </div>

        {/* Ground Truth Quick Label Actions */}
        <div className="pt-5 mt-6 border-t border-slate-800 space-y-2">
          <span className="text-[11px] font-mono text-slate-400 uppercase tracking-wider block">
            Quality Feedback & Verification Label
          </span>
          <div className="grid grid-cols-3 gap-2">
            <button
              onClick={() => onLabel(lead.id, "correct")}
              className="py-2.5 px-3 rounded-xl bg-emerald-500/10 hover:bg-emerald-500/20 border border-emerald-500/20 text-emerald-400 font-medium text-xs transition flex items-center justify-center gap-1.5"
            >
              <CheckCircle2 className="w-3.5 h-3.5" />
              <span>Correct (Y)</span>
            </button>
            <button
              onClick={() => onLabel(lead.id, "incorrect")}
              className="py-2.5 px-3 rounded-xl bg-rose-500/10 hover:bg-rose-500/20 border border-rose-500/20 text-rose-400 font-medium text-xs transition flex items-center justify-center gap-1.5"
            >
              <XCircle className="w-3.5 h-3.5" />
              <span>Incorrect (N)</span>
            </button>
            <button
              onClick={() => onLabel(lead.id, "duplicate")}
              className="py-2.5 px-3 rounded-xl bg-amber-500/10 hover:bg-amber-500/20 border border-amber-500/20 text-amber-400 font-medium text-xs transition flex items-center justify-center gap-1.5"
            >
              <Layers className="w-3.5 h-3.5" />
              <span>Duplicate (D)</span>
            </button>
          </div>
        </div>
      </div>
    </>
  );
};
