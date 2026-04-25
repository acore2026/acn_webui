import { ChangeEvent, useEffect, useRef, useState } from 'react';
import { createPortal } from 'react-dom';
import { LanguageMode, shellCopy } from '../i18n';
import { SettingsIcon } from './icons';

interface CertificateUploadModalProps {
  open: boolean;
  busy: boolean;
  language: LanguageMode;
  statusMessage?: string | null;
  statusTone?: 'success' | 'error' | null;
  onClose: () => void;
  onSubmit: (payload: { file: File | null; filePath: string }) => Promise<void>;
}

export const CertificateUploadModal = ({
  open,
  busy,
  language,
  statusMessage,
  statusTone,
  onClose,
  onSubmit
}: CertificateUploadModalProps) => {
  const copy = shellCopy[language].certificates;
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [filePath, setFilePath] = useState('');
  const [error, setError] = useState<string | null>(null);
  const fileInputRef = useRef<HTMLInputElement | null>(null);

  useEffect(() => {
    if (open) {
      return;
    }

    setSelectedFile(null);
    setFilePath('');
    setError(null);
    if (fileInputRef.current) {
      fileInputRef.current.value = '';
    }
  }, [open]);

  useEffect(() => {
    if (!open) {
      return;
    }

    const handleKeyDown = (event: KeyboardEvent) => {
      if (event.key === 'Escape' && !busy) {
        onClose();
      }
    };

    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [busy, onClose, open]);

  if (!open) {
    return null;
  }

  const handleFileChange = (event: ChangeEvent<HTMLInputElement>) => {
    const nextFile = event.target.files?.[0] ?? null;
    setSelectedFile(nextFile);
    setError(null);
  };

  const handleSubmit = async () => {
    const normalizedPath = filePath.trim();
    if (!selectedFile && !normalizedPath) {
      setError(copy.required);
      return;
    }

    await onSubmit({ file: selectedFile, filePath: normalizedPath });
  };

  return createPortal(
    <div
      className="fixed inset-0 z-[260] flex items-center justify-center bg-slate-950/68 p-4 backdrop-blur-sm"
      onClick={() => {
        if (!busy) {
          onClose();
        }
      }}
      role="presentation"
    >
      <div
        className="glass-panel w-full max-w-2xl p-6 md:p-7"
        onClick={(event) => event.stopPropagation()}
        role="dialog"
        aria-modal="true"
        aria-labelledby="certificate-upload-title"
      >
        <div className="flex items-start justify-between gap-4">
          <div>
            <p className="panel-eyebrow">{copy.uploadModalEyebrow}</p>
            <h3 id="certificate-upload-title" className="theme-title mt-2 text-2xl font-semibold">
              {copy.uploadModalTitle}
            </h3>
            <p className="theme-soft mt-2 text-sm leading-6">{copy.uploadModalDescription}</p>
          </div>
          <span className="theme-accent-icon flex h-12 w-12 items-center justify-center rounded-2xl">
            <SettingsIcon />
          </span>
        </div>

        <div className="mt-6 grid gap-5">
          <div className="theme-subtle-card px-4 py-4">
            <p className="theme-muted text-xs font-semibold uppercase tracking-[0.18em]">
              {copy.selectFile}
            </p>
            <input
              ref={fileInputRef}
              type="file"
              onChange={handleFileChange}
              disabled={busy}
              className="theme-copy mt-3 block w-full cursor-pointer text-sm file:mr-4 file:rounded-xl file:border-0 file:bg-[color:var(--surface-strong)] file:px-4 file:py-2 file:text-sm file:font-medium file:text-[color:var(--text-main)]"
            />
            <p className="theme-soft mt-3 text-sm">
              {copy.selectedFile}: {selectedFile?.name || '-'}
            </p>
          </div>

          <label className="theme-subtle-card block px-4 py-4">
            <span className="theme-muted text-xs font-semibold uppercase tracking-[0.18em]">
              {copy.filePathLabel}
            </span>
            <input
              value={filePath}
              onChange={(event) => {
                setFilePath(event.target.value);
                setError(null);
              }}
              disabled={busy}
              placeholder={copy.filePathPlaceholder}
              className="mt-3 w-full rounded-2xl border border-[color:var(--border-soft)] bg-[color:var(--surface-soft-solid)] px-4 py-3 text-sm text-[color:var(--text-main)] outline-none transition placeholder:text-[color:var(--text-muted)] focus:border-[color:var(--border-strong)]"
            />
            <p className="theme-soft mt-3 text-sm">{copy.fileHint}</p>
          </label>
        </div>

        <div className="mt-5 min-h-[1.5rem] text-sm text-[color:var(--accent-rose-text)]">
          {error ? (
            error
          ) : statusMessage ? (
            <span
              className={
                statusTone === 'success'
                  ? 'text-[color:var(--accent-cyan-text)]'
                  : 'text-[color:var(--accent-rose-text)]'
              }
            >
              {statusMessage}
            </span>
          ) : null}
        </div>

        <div className="mt-6 flex flex-wrap justify-end gap-3">
          <button
            type="button"
            className="theme-top-button px-5 py-3"
            onClick={onClose}
            disabled={busy}
          >
            {copy.close}
          </button>
          <button
            type="button"
            className={['theme-top-button px-5 py-3', busy ? 'cursor-wait opacity-70' : ''].join(' ')}
            onClick={() => {
              void handleSubmit();
            }}
            disabled={busy}
          >
            {busy ? copy.uploading : copy.submit}
          </button>
        </div>
      </div>
    </div>,
    document.body
  );
};
