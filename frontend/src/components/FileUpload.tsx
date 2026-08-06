import React, { useState, useCallback } from 'react';
import { Upload, FileText, X, CheckCircle, Loader2, Sparkles } from 'lucide-react';
import { api } from '../api/backend';
import { useAgentStore } from '../store/agentStore';
import { useAgentStream } from '../hooks/useAgentStream';

interface UploadResult {
    filename: string;
    document_id: string;
    text_length: number;
    text_preview: string;
    full_text: string;
    chunks_indexed: number;
    rag_enabled: boolean;
}

export const FileUpload: React.FC = () => {
    const [isDragging, setIsDragging] = useState(false);
    const [uploading, setUploading] = useState(false);
    const [result, setResult] = useState<UploadResult | null>(null);
    const [error, setError] = useState<string | null>(null);
    const { addMessage, setSrsText, activeSessionId } = useAgentStore();
    const { send } = useAgentStream();

    const ALLOWED_EXTENSIONS = ['.pdf', '.docx', '.doc', '.md', '.txt'];

    const handleFile = useCallback(async (file: File) => {
        const ext = '.' + file.name.split('.').pop()?.toLowerCase();
        if (!ALLOWED_EXTENSIONS.includes(ext)) {
            setError(`Unsupported file type: ${ext}. Allowed: ${ALLOWED_EXTENSIONS.join(', ')}`);
            return;
        }

        setUploading(true);
        setError(null);
        setResult(null);

        try {
            const uploadResult = await api.documents.upload(file);
            setResult(uploadResult);

            // Store the full extracted text so the agent can use it
            setSrsText(uploadResult.full_text, activeSessionId);

            // Inject the document text as a system preview message
            addMessage({
                role: 'system',
                content: `📄 Document uploaded: **${uploadResult.filename}**\n` +
                    `• ${uploadResult.text_length.toLocaleString()} characters extracted\n` +
                    (uploadResult.rag_enabled
                        ? `• ${uploadResult.chunks_indexed} chunks indexed for semantic search\n`
                        : '• RAG indexing not available\n') +
                    `\nPreview:\n${uploadResult.text_preview}`,
            }, activeSessionId);

            // Automatically trigger the AI Agent to build the app from the uploaded SRS!
            const prompt = `Build the complete application specified in the uploaded SRS document (${uploadResult.filename}). Implement all required features with clean code and modern styling.`;
            const srsContext = useAgentStore.getState().consumeSrsText(activeSessionId);
            const fullMessage = srsContext
                ? `[SRS DOCUMENT]\n${srsContext}\n\n[USER INSTRUCTION]\n${prompt}`
                : prompt;
            send(fullMessage);

        } catch (e) {
            const msg = e instanceof Error ? e.message : String(e);
            setError(msg);
        } finally {
            setUploading(false);
        }
    }, [addMessage, setSrsText, activeSessionId, send]);

    const onDrop = useCallback((e: React.DragEvent) => {
        e.preventDefault();
        setIsDragging(false);
        const file = e.dataTransfer.files[0];
        if (file) handleFile(file);
    }, [handleFile]);

    const onDragOver = useCallback((e: React.DragEvent) => {
        e.preventDefault();
        setIsDragging(true);
    }, []);

    const onDragLeave = useCallback(() => setIsDragging(false), []);

    const onFileSelect = useCallback((e: React.ChangeEvent<HTMLInputElement>) => {
        const file = e.target.files?.[0];
        if (file) handleFile(file);
        e.target.value = '';
    }, [handleFile]);

    const handleBuildFromSrs = (e: React.MouseEvent) => {
        e.preventDefault();
        if (!result) return;
        send(`Build the complete application specified in the uploaded SRS document (${result.filename}). Implement all required features, clean UI, and complete application logic.`);
    };

    return (
        <div className="relative">
            {/* Drag overlay */}
            {isDragging && (
                <div
                    className="absolute inset-0 z-50 bg-brand/10 border-2 border-dashed border-brand rounded-lg flex items-center justify-center backdrop-blur-sm"
                    onDrop={onDrop}
                    onDragOver={onDragOver}
                    onDragLeave={onDragLeave}
                >
                    <div className="text-center">
                        <Upload size={32} className="mx-auto text-brand mb-2" />
                        <p className="text-sm text-brand font-medium">Drop SRS document here</p>
                        <p className="text-xs text-text-muted mt-1">PDF, DOCX, MD, TXT</p>
                    </div>
                </div>
            )}

            {/* Upload area */}
            <div
                className={`border border-dashed rounded-lg p-3 transition-all cursor-pointer ${
                    isDragging
                        ? 'border-brand bg-brand/5'
                        : 'border-border hover:border-brand/50 bg-surface-hover/50'
                }`}
                onDrop={onDrop}
                onDragOver={onDragOver}
                onDragLeave={onDragLeave}
            >
                <label className="flex items-center gap-3 cursor-pointer">
                    <div className="w-8 h-8 rounded-md bg-brand/10 flex items-center justify-center flex-shrink-0">
                        {uploading ? (
                            <Loader2 size={16} className="text-brand animate-spin" />
                        ) : result ? (
                            <CheckCircle size={16} className="text-emerald-500" />
                        ) : (
                            <Upload size={16} className="text-brand" />
                        )}
                    </div>
                    <div className="flex-1 min-w-0">
                        {uploading ? (
                            <p className="text-xs text-text-muted">Processing document & starting AI agent...</p>
                        ) : result ? (
                            <div className="flex items-center justify-between gap-2">
                                <div className="flex items-center gap-2 min-w-0">
                                    <FileText size={12} className="text-emerald-500 flex-shrink-0" />
                                    <span className="text-xs text-emerald-600 font-medium truncate">{result.filename}</span>
                                </div>
                                <div className="flex items-center gap-2 shrink-0">
                                    <button
                                        type="button"
                                        onClick={handleBuildFromSrs}
                                        className="btn-primary h-6 text-[10px] px-2 flex items-center gap-1 shadow-xs"
                                        title="Generate Application"
                                    >
                                        <Sparkles size={11} />
                                        <span>Build App</span>
                                    </button>
                                    <button
                                        type="button"
                                        onClick={(e) => {
                                            e.preventDefault();
                                            setResult(null);
                                        }}
                                        className="p-1 rounded hover:bg-surface-hover"
                                    >
                                        <X size={12} className="text-text-muted hover:text-text" />
                                    </button>
                                </div>
                            </div>
                        ) : (
                            <>
                                <p className="text-xs text-text">Upload SRS document</p>
                                <p className="text-[10px] text-text-muted">PDF, DOCX, MD, TXT — drag & drop or click</p>
                            </>
                        )}
                    </div>
                    <input
                        type="file"
                        className="hidden"
                        accept={ALLOWED_EXTENSIONS.join(',')}
                        onChange={onFileSelect}
                        disabled={uploading}
                    />
                </label>
            </div>

            {/* Error */}
            {error && (
                <div className="mt-2 text-xs text-red-400 bg-red-950/40 border border-red-800 rounded p-2 flex items-start gap-2">
                    <X size={12} className="flex-shrink-0 mt-0.5" />
                    <span>{error}</span>
                </div>
            )}
        </div>
    );
};
