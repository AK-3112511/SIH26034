"use client";
/**
 * §3 Screen 5 — E-Commerce Ingestion Screen
 * Companion: MetrologyAI Elevated Blueprint §3.2 & UX Blueprint §3 screen 5
 * 
 * Invariants:
 * 1. Drag-and-drop screenshot upload zone (§5.7 / .dropzone) with file preview.
 * 2. Manual dimension input form: package height (mm), package width (mm), optional depth (mm).
 * 3. Declared net quantity and product platform tag (Blinkit, Amazon, Flipkart, Zepto, Instamart, BigBasket, Other).
 * 4. Submits into /api/v1/scans/ingest-derived via multipart/form-data.
 * 5. Demonstrates the manual-dimension calibration path: mm/px calibration ratio computed
 *    from physical dimensions mapped to screenshot pixels rather than a reference card.
 */
import { useState, useRef, useCallback, DragEvent, ChangeEvent, FormEvent } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import {
  UploadCloud,
  FileImage,
  Ruler,
  ShoppingBag,
  ExternalLink,
  CheckCircle2,
  AlertTriangle,
  ArrowRight,
  Info,
  Layers,
  Sparkles,
  X,
} from "lucide-react";
import { AppShell } from "@/app/components/AppShell";
import { CalibrationRuler } from "@/app/components/CalibrationRuler";
import { scansApi } from "@/lib/api";
import { apiErrorMessage } from "@/lib/errors";

const PLATFORM_OPTIONS = [
  { value: "Blinkit", label: "Blinkit" },
  { value: "Amazon", label: "Amazon India" },
  { value: "Flipkart", label: "Flipkart" },
  { value: "Zepto", label: "Zepto" },
  { value: "Instamart", label: "Swiggy Instamart" },
  { value: "BigBasket", label: "BigBasket / BB Now" },
  { value: "Other", label: "Other E-Commerce Platform" },
];

export default function EcommerceIngestionPage() {
  const router = useRouter();
  const fileInputRef = useRef<HTMLInputElement>(null);

  // Form State
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [previewUrl, setPreviewUrl] = useState<string | null>(null);
  const [isDragOver, setIsDragOver] = useState(false);

  const [platform, setPlatform] = useState<string>("Blinkit");
  const [customPlatform, setCustomPlatform] = useState<string>("");
  const [platformUrl, setPlatformUrl] = useState<string>("");
  const [packageHeightMm, setPackageHeightMm] = useState<string>("");
  const [packageWidthMm, setPackageWidthMm] = useState<string>("");
  const [packageDepthMm, setPackageDepthMm] = useState<string>("");
  const [declaredNetQty, setDeclaredNetQty] = useState<string>("");

  // Submission State
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [successData, setSuccessData] = useState<{
    scanId: string;
    message: string;
    ratioEstimate?: number;
    pdpArea?: number;
  } | null>(null);

  // File Handlers
  const handleFile = (file: File) => {
    if (!file.type.startsWith("image/")) {
      setError("Only screenshot image files (PNG, JPEG, WebP) are allowed.");
      return;
    }
    setError(null);
    setSelectedFile(file);
    const url = URL.createObjectURL(file);
    setPreviewUrl(url);
  };

  const onDragOver = (e: DragEvent<HTMLDivElement>) => {
    e.preventDefault();
    setIsDragOver(true);
  };

  const onDragLeave = (e: DragEvent<HTMLDivElement>) => {
    e.preventDefault();
    setIsDragOver(false);
  };

  const onDrop = (e: DragEvent<HTMLDivElement>) => {
    e.preventDefault();
    setIsDragOver(false);
    if (e.dataTransfer.files && e.dataTransfer.files.length > 0) {
      handleFile(e.dataTransfer.files[0]);
    }
  };

  const onFileInputChange = (e: ChangeEvent<HTMLInputElement>) => {
    if (e.target.files && e.target.files.length > 0) {
      handleFile(e.target.files[0]);
    }
  };

  const clearFile = () => {
    setSelectedFile(null);
    if (previewUrl) URL.revokeObjectURL(previewUrl);
    setPreviewUrl(null);
    if (fileInputRef.current) fileInputRef.current.value = "";
  };

  // Live PDP Area & Ratio calculation preview
  const heightVal = parseFloat(packageHeightMm);
  const widthVal = parseFloat(packageWidthMm);
  const pdpAreaPreview =
    !isNaN(heightVal) && !isNaN(widthVal) && heightVal > 0 && widthVal > 0
      ? ((heightVal * widthVal) / 100).toFixed(1)
      : null;

  // Submit Handler
  const handleSubmit = async (e: FormEvent) => {
    e.preventDefault();
    setError(null);

    if (!selectedFile) {
      setError("Please select or drop an e-commerce product screenshot.");
      return;
    }

    if (!heightVal || heightVal <= 0 || !widthVal || widthVal <= 0) {
      setError("Valid package face height and width in millimeters are required for calibration.");
      return;
    }

    const effectivePlatform = platform === "Other" ? (customPlatform || "Other") : platform;

    setSubmitting(true);
    try {
      const formData = new FormData();
      formData.append("image", selectedFile);
      formData.append("platform", effectivePlatform);
      formData.append("package_height_mm", heightVal.toString());
      formData.append("package_width_mm", widthVal.toString());
      if (packageDepthMm && parseFloat(packageDepthMm) > 0) {
        formData.append("package_depth_mm", packageDepthMm);
      }
      if (declaredNetQty.trim()) {
        formData.append("declared_net_quantity", declaredNetQty.trim());
      }
      if (platformUrl.trim()) {
        formData.append("platform_url", platformUrl.trim());
      }

      const res = await scansApi.ingestDerived(formData);
      setSuccessData({
        scanId: res.data.scan_id,
        message: res.data.message,
        pdpArea: pdpAreaPreview ? parseFloat(pdpAreaPreview) : undefined,
      });
    } catch (err) {
      setError(apiErrorMessage(err, "The listing could not be submitted for checking."));
    } finally {
      setSubmitting(false);
    }
  };

  const handleReset = () => {
    clearFile();
    setPlatform("Blinkit");
    setCustomPlatform("");
    setPlatformUrl("");
    setPackageHeightMm("");
    setPackageWidthMm("");
    setPackageDepthMm("");
    setDeclaredNetQty("");
    setSuccessData(null);
    setError(null);
  };

  return (
    <AppShell>
      {/* ── Screen Header ──────────────────────────────────────────────── */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 mb-4">
        <div>
          <h1 className="font-display font-semibold text-2xl text-ink-900 leading-tight">
            E-Commerce Screenshot Ingestion
          </h1>
          <p className="font-body text-xs text-ink-600 mt-1">
            Check an online product listing against the same rules as a field capture. Because
            there is no reference card in a listing photograph, the package dimensions are
            entered by hand instead.
          </p>
        </div>
        <span className="font-mono text-xs text-ink-600 bg-ink-900/5 px-2.5 py-1 rounded border border-ink-900/10 self-start sm:self-auto">
          Source: E-Commerce Web Portal
        </span>
      </div>

      <CalibrationRuler />

      {/* ── Success Banner ──────────────────────────────────────────────── */}
      {successData && (
        <div className="card-surface mt-6 border-verdict-pass/40 bg-verdict-pass/5 p-6 space-y-4">
          <div className="flex items-start gap-3">
            <CheckCircle2 size={24} className="text-verdict-pass shrink-0 mt-0.5" />
            <div className="space-y-1">
              <h2 className="font-display font-semibold text-base text-ink-900">
                E-Commerce Screenshot Successfully Queued
              </h2>
              <p className="font-body text-xs text-ink-600">
                {successData.message}
              </p>
              <div className="flex flex-wrap items-center gap-4 mt-2 font-mono text-xs text-ink-900">
                <span className="bg-white px-2 py-1 rounded border border-ink-900/10">
                  Scan ID: <strong>{successData.scanId}</strong>
                </span>
                {successData.pdpArea && (
                  <span className="bg-white px-2 py-1 rounded border border-ink-900/10">
                    Calculated PDP: <strong>{successData.pdpArea} cm²</strong>
                  </span>
                )}
              </div>
            </div>
          </div>

          <div className="flex items-center gap-3 pt-2">
            <Link
              href={`/queue/${successData.scanId}`}
              className="btn-primary text-xs"
            >
              <span>Inspect in Scan Detail</span>
              <ArrowRight size={14} />
            </Link>
            <button
              type="button"
              onClick={handleReset}
              className="btn-secondary text-xs"
            >
              Upload Another Screenshot
            </button>
          </div>
        </div>
      )}

      {/* ── Main Form ─────────────────────────────────────────────────── */}
      {!successData && (
        <form onSubmit={handleSubmit} className="mt-6 space-y-6">
          <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
            {/* Left Column: Drag and Drop Zone */}
            <div className="lg:col-span-6 space-y-4">
              <div className="flex items-center justify-between">
                <label className="form-label mb-0">
                  Product Screenshot *
                </label>
                <span className="font-mono text-[11px] text-ink-600">
                  PNG / JPEG / WebP up to 15MB
                </span>
              </div>

              {!previewUrl ? (
                <div
                  onDragOver={onDragOver}
                  onDragLeave={onDragLeave}
                  onDrop={onDrop}
                  onClick={() => fileInputRef.current?.click()}
                  className={`
                    dropzone min-h-[300px] flex flex-col items-center justify-center
                    ${isDragOver ? "dragover" : ""}
                  `}
                >
                  <input
                    ref={fileInputRef}
                    type="file"
                    accept="image/png, image/jpeg, image/webp"
                    className="hidden"
                    onChange={onFileInputChange}
                  />
                  <div className="w-12 h-12 rounded-full bg-ink-900/5 flex items-center justify-center text-ink-600 mb-2">
                    <UploadCloud size={24} />
                  </div>
                  <p className="font-display font-semibold text-sm text-ink-900">
                    Drag and drop screenshot here, or <span className="text-brass-500 underline">browse</span>
                  </p>
                  <p className="font-body text-xs text-ink-600 max-w-xs">
                    Upload clear product front face from Blinkit, Amazon, Flipkart, etc.
                  </p>
                </div>
              ) : (
                <div className="card-surface p-3 space-y-3">
                  <div className="relative rounded overflow-hidden bg-black/5 flex items-center justify-center min-h-[260px] max-h-[360px]">
                    <img
                      src={previewUrl}
                      alt="Screenshot preview"
                      className="w-full h-full object-contain max-h-[360px]"
                    />
                    <button
                      type="button"
                      onClick={clearFile}
                      aria-label="Remove image"
                      className="
                        absolute top-2 right-2 p-1.5 rounded-full bg-ink-900/80 text-white
                        hover:bg-verdict-fail transition-colors
                      "
                    >
                      <X size={14} />
                    </button>
                  </div>
                  <div className="flex items-center justify-between font-mono text-xs text-ink-600 px-1">
                    <span>{selectedFile?.name}</span>
                    <span>{selectedFile ? `${(selectedFile.size / 1024).toFixed(0)} KB` : ""}</span>
                  </div>
                </div>
              )}

              {/* Section 3.2 Calibration Info Card */}
              <div className="card-surface p-4 bg-paper-100/60 border border-ink-900/10 space-y-2">
                <div className="flex items-center gap-2 text-ink-900 font-semibold text-xs uppercase tracking-wider">
                  <Info size={14} className="text-brass-500" />
                  <span>Manual calibration</span>
                </div>
                <p className="font-body text-xs text-ink-600 leading-relaxed">
                  Because digital screenshots contain no physical reference card, manual physical dimensions
                  substitute directly for the card-to-pixel ratio. The system maps the face height to image pixels
                  to determine legal numeral compliance under Schedule II.
                </p>
              </div>
            </div>

            {/* Right Column: Manual Dimensions & Platform Form */}
            <div className="lg:col-span-6 space-y-5">
              {/* Platform Selector */}
              <div className="card-surface space-y-4">
                <div className="flex items-center gap-2 border-b border-ink-900/10 pb-2">
                  <ShoppingBag size={16} className="text-brass-500" />
                  <h2 className="font-display font-semibold text-sm text-ink-900 uppercase tracking-wider">
                    Listing & Platform Metadata
                  </h2>
                </div>

                <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                  <div>
                    <label htmlFor="platform-select" className="form-label">
                      E-Commerce Platform *
                    </label>
                    <select
                      id="platform-select"
                      value={platform}
                      onChange={(e) => setPlatform(e.target.value)}
                      className="form-input text-xs"
                    >
                      {PLATFORM_OPTIONS.map((opt) => (
                        <option key={opt.value} value={opt.value}>
                          {opt.label}
                        </option>
                      ))}
                    </select>
                  </div>

                  {platform === "Other" && (
                    <div>
                      <label htmlFor="custom-platform" className="form-label">
                        Platform Name *
                      </label>
                      <input
                        id="custom-platform"
                        type="text"
                        placeholder="e.g. Meesho, JioMart"
                        value={customPlatform}
                        onChange={(e) => setCustomPlatform(e.target.value)}
                        className="form-input text-xs"
                        required
                      />
                    </div>
                  )}

                  <div className={platform === "Other" ? "sm:col-span-2" : "sm:col-span-1"}>
                    <label htmlFor="declared-qty" className="form-label">
                      Declared Net Quantity (on listing)
                    </label>
                    <input
                      id="declared-qty"
                      type="text"
                      placeholder="e.g. 500g, 1L, 200 ml"
                      value={declaredNetQty}
                      onChange={(e) => setDeclaredNetQty(e.target.value)}
                      className="form-input text-xs"
                    />
                  </div>
                </div>

                <div>
                  <label htmlFor="platform-url" className="form-label">
                    Product Listing URL (Optional)
                  </label>
                  <input
                    id="platform-url"
                    type="url"
                    placeholder="https://blinkit.com/prn/..."
                    value={platformUrl}
                    onChange={(e) => setPlatformUrl(e.target.value)}
                    className="form-input text-xs"
                  />
                </div>
              </div>

              {/* Dimensions are typed in, since no reference card is present. */}
              <div className="card-surface space-y-4">
                <div className="flex items-center justify-between border-b border-ink-900/10 pb-2">
                  <div className="flex items-center gap-2">
                    <Ruler size={16} className="text-brass-500" />
                    <h2 className="font-display font-semibold text-sm text-ink-900 uppercase tracking-wider">
                      Physical package dimensions
                    </h2>
                  </div>
                  <span className="font-mono text-[11px] text-ink-600 bg-ink-900/5 px-2 py-0.5 rounded">
                    Millimeters (mm)
                  </span>
                </div>

                <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
                  <div>
                    <label htmlFor="pkg-height" className="form-label">
                      Face Height (mm) *
                    </label>
                    <input
                      id="pkg-height"
                      type="number"
                      step="0.1"
                      min="1"
                      placeholder="e.g. 180"
                      value={packageHeightMm}
                      onChange={(e) => setPackageHeightMm(e.target.value)}
                      className="form-input font-mono text-xs"
                      required
                    />
                  </div>

                  <div>
                    <label htmlFor="pkg-width" className="form-label">
                      Face Width (mm) *
                    </label>
                    <input
                      id="pkg-width"
                      type="number"
                      step="0.1"
                      min="1"
                      placeholder="e.g. 90"
                      value={packageWidthMm}
                      onChange={(e) => setPackageWidthMm(e.target.value)}
                      className="form-input font-mono text-xs"
                      required
                    />
                  </div>

                  <div>
                    <label htmlFor="pkg-depth" className="form-label">
                      Depth (mm, optional)
                    </label>
                    <input
                      id="pkg-depth"
                      type="number"
                      step="0.1"
                      min="0"
                      placeholder="e.g. 45"
                      value={packageDepthMm}
                      onChange={(e) => setPackageDepthMm(e.target.value)}
                      className="form-input font-mono text-xs"
                    />
                  </div>
                </div>

                {/* Live Calibration Calculation Preview */}
                <div className="rounded-[4px] p-3 bg-ink-900/[0.03] border border-ink-900/10 flex items-center justify-between">
                  <div className="space-y-0.5">
                    <span className="block font-body text-xs font-semibold text-ink-900">
                      Calculated Principal Display Panel (PDP)
                    </span>
                    <span className="block font-body text-[11px] text-ink-600">
                      Height × Width / 100 per Legal Metrology PCR Schedule II
                    </span>
                  </div>
                  <span className="font-mono text-sm font-semibold text-brass-500 bg-white px-2.5 py-1 rounded border border-ink-900/10">
                    {pdpAreaPreview ? `${pdpAreaPreview} cm²` : "— cm²"}
                  </span>
                </div>
              </div>

              {/* Error Display */}
              {error && (
                <div className="card-surface p-3 border-verdict-fail/30 bg-verdict-fail/5 text-verdict-fail flex items-center gap-3 text-xs">
                  <AlertTriangle size={18} className="shrink-0" />
                  <span>{error}</span>
                </div>
              )}

              {/* Action Buttons */}
              <div className="flex items-center justify-end gap-3 pt-2">
                <button
                  type="button"
                  onClick={handleReset}
                  disabled={submitting}
                  className="btn-secondary text-xs px-4"
                >
                  Clear Form
                </button>
                <button
                  type="submit"
                  disabled={submitting || !selectedFile}
                  className="btn-primary text-xs px-6"
                >
                  {submitting ? "Submitting Screenshot..." : "Ingest & Queue for Analysis"}
                </button>
              </div>
            </div>
          </div>
        </form>
      )}
    </AppShell>
  );
}
