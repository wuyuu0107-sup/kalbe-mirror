from notification.sse import sse_send

def notify(session_id, type_, *, data=None, job_id=None):
    sse_send(session_id, type_, data=data or {}, job_id=job_id)

def notify_ocr_completed(session_id, *, path, size=None, job_id=None):
    message = f"File {path} berhasil diproses." if path else "OCR selesai."
    data = {"path": path, "size": size, "message": message}
    notify(session_id, "ocr.completed", data=data, job_id=job_id)

def notify_ocr_failed(session_id, *, path, reason, job_id=None):
    message = f"Gagal memproses {path}: {reason}" if path else f"OCR gagal: {reason}"
    data = {"path": path, "reason": reason, "message": message}
    notify(session_id, "ocr.failed", data=data, job_id=job_id)

def notify_chat_reply(session_id, *, job_id=None):
    message = "Chatbot telah mengirim respons baru."
    data = {"message": message}
    notify(session_id, "chat.reply", data=data, job_id=job_id)