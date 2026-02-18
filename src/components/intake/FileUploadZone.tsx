'use client'

import { useCallback, useRef, useState } from 'react'

interface FileUploadZoneProps {
  accept: string
  multiple?: boolean
  label: string
  hint: string
  files: File[]
  onFilesChange: (files: File[]) => void
  showThumbnails?: boolean
}

export default function FileUploadZone({
  accept,
  multiple = false,
  label,
  hint,
  files,
  onFilesChange,
  showThumbnails = false,
}: FileUploadZoneProps) {
  const [isDragOver, setIsDragOver] = useState(false)
  const inputRef = useRef<HTMLInputElement>(null)

  const handleFiles = useCallback(
    (incoming: FileList | null) => {
      if (!incoming) return
      const arr = Array.from(incoming)
      if (multiple) {
        onFilesChange([...files, ...arr])
      } else {
        onFilesChange(arr.slice(0, 1))
      }
    },
    [files, multiple, onFilesChange]
  )

  const handleDrop = useCallback(
    (e: React.DragEvent) => {
      e.preventDefault()
      setIsDragOver(false)
      handleFiles(e.dataTransfer.files)
    },
    [handleFiles]
  )

  const handleDragOver = useCallback((e: React.DragEvent) => {
    e.preventDefault()
    setIsDragOver(true)
  }, [])

  const handleDragLeave = useCallback(() => {
    setIsDragOver(false)
  }, [])

  const removeFile = useCallback(
    (index: number) => {
      onFilesChange(files.filter((_, i) => i !== index))
    },
    [files, onFilesChange]
  )

  const hasFiles = files.length > 0

  return (
    <div>
      <label
        style={{
          display: 'block',
          fontFamily: "'Inter', system-ui, sans-serif",
          fontSize: '13px',
          color: '#6B6560',
          textTransform: 'uppercase' as const,
          letterSpacing: '0.05em',
          marginBottom: '8px',
        }}
      >
        {label}
      </label>

      {/* Drop zone */}
      <div
        onClick={() => inputRef.current?.click()}
        onDrop={handleDrop}
        onDragOver={handleDragOver}
        onDragLeave={handleDragLeave}
        style={{
          border: hasFiles
            ? '2px solid #B8860B'
            : isDragOver
            ? '2px dashed #D4A843'
            : '2px dashed #E8E0D4',
          borderRadius: '12px',
          padding: hasFiles ? '1rem' : '2rem',
          textAlign: 'center',
          cursor: 'pointer',
          backgroundColor: isDragOver ? 'rgba(184, 134, 11, 0.1)' : 'transparent',
          transition: 'border-color 0.2s, background-color 0.2s',
        }}
      >
        <input
          ref={inputRef}
          type="file"
          accept={accept}
          multiple={multiple}
          onChange={(e) => handleFiles(e.target.files)}
          style={{ display: 'none' }}
        />

        {!hasFiles ? (
          <>
            <div
              style={{
                fontFamily: "'Inter', system-ui, sans-serif",
                fontSize: '15px',
                color: '#2C2C2C',
                marginBottom: '4px',
              }}
            >
              Drop {multiple ? 'files' : 'file'} here or click to browse
            </div>
            <div
              style={{
                fontFamily: "'Inter', system-ui, sans-serif",
                fontSize: '13px',
                color: '#6B6560',
              }}
            >
              {hint}
            </div>
          </>
        ) : (
          <div style={{ textAlign: 'left' }}>
            {files.map((file, i) => (
              <div
                key={`${file.name}-${i}`}
                style={{
                  display: 'flex',
                  alignItems: 'center',
                  gap: '12px',
                  padding: '8px 0',
                  borderBottom:
                    i < files.length - 1 ? '1px solid #E8E0D4' : 'none',
                }}
              >
                {showThumbnails && file.type.startsWith('image/') ? (
                  <img
                    src={URL.createObjectURL(file)}
                    alt={file.name}
                    style={{
                      width: '48px',
                      height: '48px',
                      objectFit: 'cover',
                      borderRadius: '6px',
                      flexShrink: 0,
                    }}
                  />
                ) : (
                  <div
                    style={{
                      width: '36px',
                      height: '36px',
                      borderRadius: '6px',
                      backgroundColor: 'rgba(184, 134, 11, 0.1)',
                      display: 'flex',
                      alignItems: 'center',
                      justifyContent: 'center',
                      flexShrink: 0,
                    }}
                  >
                    <svg
                      width="16"
                      height="16"
                      viewBox="0 0 24 24"
                      fill="none"
                      stroke="#B8860B"
                      strokeWidth="2"
                      strokeLinecap="round"
                      strokeLinejoin="round"
                    >
                      <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" />
                      <polyline points="14 2 14 8 20 8" />
                    </svg>
                  </div>
                )}
                <div style={{ flex: 1, minWidth: 0 }}>
                  <div
                    style={{
                      fontFamily: "'Inter', system-ui, sans-serif",
                      fontSize: '14px',
                      color: '#2C2C2C',
                      overflow: 'hidden',
                      textOverflow: 'ellipsis',
                      whiteSpace: 'nowrap',
                    }}
                  >
                    {file.name}
                  </div>
                  <div
                    style={{
                      fontFamily: "'Inter', system-ui, sans-serif",
                      fontSize: '12px',
                      color: '#6B6560',
                    }}
                  >
                    {(file.size / 1024).toFixed(0)} KB
                  </div>
                </div>
                <button
                  type="button"
                  onClick={(e) => {
                    e.stopPropagation()
                    removeFile(i)
                  }}
                  style={{
                    background: 'none',
                    border: 'none',
                    cursor: 'pointer',
                    padding: '4px',
                    color: '#6B6560',
                    fontSize: '18px',
                    lineHeight: 1,
                    flexShrink: 0,
                  }}
                  aria-label={`Remove ${file.name}`}
                >
                  &times;
                </button>
              </div>
            ))}
            {multiple && (
              <div
                style={{
                  fontFamily: "'Inter', system-ui, sans-serif",
                  fontSize: '13px',
                  color: '#B8860B',
                  marginTop: '8px',
                  textAlign: 'center',
                }}
              >
                + Add more files
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  )
}
