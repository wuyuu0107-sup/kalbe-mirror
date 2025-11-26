from notification.sse import sse_send
from .models import Notification
from authentication.models import User

def notify(session_id, type_, *, data=None, job_id=None, user_id=None):
    sse_send(session_id, type_, data=data or {}, job_id=job_id, user_id=user_id)

    # Also create persistent notification if user_id is provided
    if user_id:
        try:
            user = User.objects.get(user_id=user_id)
            create_persistent_notification(user, type_, data or {}, job_id)
        except User.DoesNotExist:
            pass  # Skip if user not found

def create_persistent_notification(user, type_, data, job_id=None):
    """Create a persistent notification in the database."""
    title = get_notification_title(type_, data)
    message = get_notification_message(type_, data)

    Notification.objects.create(
        user=user,
        title=title,
        message=message,
        type=type_,
        job_id=job_id,
        data=data
    )

def get_notification_title(type_: str, _data: dict | None = None):
    """Generate notification title based on type."""
    titles = {
        'ocr.completed': 'Pemrosesan OCR Selesai',
        'ocr.failed': 'Pemrosesan OCR Gagal',
        'chat.reply': 'Respons Chat Baru',
        'system': 'Notifikasi Sistem',
    }
    return titles.get(type_, 'Notifikasi')



def get_notification_message(type_, data):
    """Generate notification message based on type and data."""
    if type_ == 'ocr.completed':
        path = data.get('path', '')
        return f"Berkas {path} telah berhasil diproses." if path else "Pemrosesan OCR selesai."
    elif type_ == 'ocr.failed':
        path = data.get('path', '')
        reason = data.get('reason', 'Kesalahan tidak diketahui')
        return f"Gagal memproses {path}: {reason}" if path else f"Pemrosesan OCR gagal: {reason}"
    elif type_ == 'chat.reply':
        return "Chatbot telah mengirim respons baru."
    elif type_ == 'system':
        return data.get('message', 'Notifikasi sistem')
    else:
        return data.get('message', 'Notifikasi baru')

def notify_ocr_completed(session_id, *, path, size=None, job_id=None, user_id=None):
    message = f"File {path} berhasil diproses." if path else "OCR selesai."
    data = {"path": path, "size": size, "message": message}
    notify(session_id, "ocr.completed", data=data, job_id=job_id, user_id=user_id)

def notify_ocr_failed(session_id, *, path, reason, job_id=None, user_id=None):
    message = f"Gagal memproses {path}: {reason}" if path else f"OCR gagal: {reason}"
    data = {"path": path, "reason": reason, "message": message}
    notify(session_id, "ocr.failed", data=data, job_id=job_id, user_id=user_id)

def notify_chat_reply(session_id, *, job_id=None, user_id=None):
    message = "Chatbot telah mengirim respons baru."
    data = {"message": message}
    notify(session_id, "chat.reply", data=data, job_id=job_id, user_id=user_id)
