"use client";

import { useState, useCallback, useRef } from "react";
import { Upload, FileText, AlertCircle } from "lucide-react";

interface CsvUploaderProps {
  onFileLoaded: (text: string, fileName: string) => void;
}

export default function CsvUploader({ onFileLoaded }: CsvUploaderProps) {
  const [isDragging, setIsDragging] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [fileName, setFileName] = useState<string | null>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  const handleFile = useCallback(
    (file: File) => {
      setError(null);

      if (!file.name.toLowerCase().endsWith(".csv")) {
        setError("Please upload a CSV file.");
        return;
      }

      if (file.size > 10 * 1024 * 1024) {
        setError("File too large. Maximum size is 10MB.");
        return;
      }

      setFileName(file.name);

      const reader = new FileReader();
      reader.onload = (e) => {
        const text = e.target?.result as string;
        if (!text || text.trim().length === 0) {
          setError("File appears to be empty.");
          return;
        }
        onFileLoaded(text, file.name);
      };
      reader.onerror = () => {
        setError("Failed to read file. Please try again.");
      };
      reader.readAsText(file);
    },
    [onFileLoaded],
  );

  const handleDrop = useCallback(
    (e: React.DragEvent) => {
      e.preventDefault();
      setIsDragging(false);
      const file = e.dataTransfer.files[0];
      if (file) handleFile(file);
    },
    [handleFile],
  );

  const handleDragOver = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    setIsDragging(true);
  }, []);

  const handleDragLeave = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    setIsDragging(false);
  }, []);

  return (
    <div className="space-y-4">
      <div
        onDrop={handleDrop}
        onDragOver={handleDragOver}
        onDragLeave={handleDragLeave}
        onClick={() => inputRef.current?.click()}
        className={`
          relative border-2 border-dashed rounded-xl p-12
          flex flex-col items-center justify-center gap-4 cursor-pointer
          transition-all duration-200
          ${
            isDragging
              ? "border-teal bg-teal-light scale-[1.01]"
              : "border-border hover:border-text-ter hover:bg-surface-hover"
          }
        `}
      >
        <input
          ref={inputRef}
          type="file"
          accept=".csv"
          className="hidden"
          onChange={(e) => {
            const file = e.target.files?.[0];
            if (file) handleFile(file);
          }}
        />

        <div
          className={`w-14 h-14 rounded-full flex items-center justify-center transition-colors ${
            isDragging ? "bg-teal/20" : "bg-surface-hover"
          }`}
        >
          <Upload
            className={`w-6 h-6 ${isDragging ? "text-teal" : "text-text-ter"}`}
          />
        </div>

        <div className="text-center">
          <p className="text-sm font-semibold text-text font-body">
            {fileName ? fileName : "Drop your CSV file here"}
          </p>
          <p className="text-xs text-text-ter mt-1 font-body">
            or click to browse. Supports Wells Fargo, TD Ameritrade, Schwab exports.
          </p>
        </div>
      </div>

      {error && (
        <div className="flex items-center gap-2 px-4 py-3 rounded-lg bg-red-light text-red text-sm font-body">
          <AlertCircle className="w-4 h-4 shrink-0" />
          {error}
        </div>
      )}

      <div className="flex items-start gap-3 px-4 py-3 rounded-lg bg-surface-hover">
        <FileText className="w-4 h-4 text-text-ter mt-0.5 shrink-0" />
        <div className="text-xs text-text-ter leading-relaxed font-body">
          <p className="font-medium text-text-sec mb-1">Expected CSV format</p>
          <p>
            Your file should include columns for Date, Ticker/Symbol, Buy/Sell action,
            Quantity, Price, and optionally Total amount. Headers are auto-detected.
          </p>
        </div>
      </div>
    </div>
  );
}
