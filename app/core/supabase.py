"""
Supabase client - used for all database and storage operations
"""
from supabase import create_client, Client
from app.core.config import settings
from functools import lru_cache


@lru_cache
def get_supabase() -> Client:
    """Get Supabase client (service role - bypasses RLS for backend use)"""
    return create_client(
        supabase_url=settings.SUPABASE_URL,
        supabase_key=settings.SUPABASE_SERVICE_KEY
    )


# ─────────────────────────────────────────────
# STUDENT OPERATIONS
# ─────────────────────────────────────────────

async def get_student(phone: str) -> dict | None:
    """Get student by phone number"""
    sb = get_supabase()
    result = sb.table("students")\
        .select("*")\
        .eq("phone_number", phone)\
        .execute()
    return result.data[0] if result.data else None


async def create_student(phone: str) -> dict:
    """Create new student record"""
    sb = get_supabase()
    result = sb.table("students").insert({
        "phone_number": phone,
        "conversation_state": "greeting",
        "agent_state": {},
        "consent_given": False
    }).execute()
    return result.data[0]


async def get_or_create_student(phone: str) -> dict:
    """Get existing student or create new one"""
    student = await get_student(phone)
    if not student:
        student = await create_student(phone)
    return student


async def update_student(phone: str, updates: dict) -> dict:
    """Update student record"""
    sb = get_supabase()
    result = sb.table("students")\
        .update(updates)\
        .eq("phone_number", phone)\
        .execute()
    return result.data[0] if result.data else {}


# ─────────────────────────────────────────────
# CONVERSATION HISTORY
# ─────────────────────────────────────────────

async def save_message(student_id: str, role: str, message: str, media_url: str = None):
    """Save a message to conversation history"""
    sb = get_supabase()
    sb.table("conversations").insert({
        "student_id": student_id,
        "role": role,
        "message": message,
        "media_url": media_url
    }).execute()


async def get_recent_messages(student_id: str, limit: int = 20) -> list:
    """Get recent conversation history for context"""
    sb = get_supabase()
    result = sb.table("conversations")\
        .select("role, message")\
        .eq("student_id", student_id)\
        .order("created_at", desc=True)\
        .limit(limit)\
        .execute()
    # Return in chronological order
    return list(reversed(result.data))


# ─────────────────────────────────────────────
# DOCUMENT STORAGE
# ─────────────────────────────────────────────

async def upload_document(file_bytes: bytes, path: str, content_type: str = "image/jpeg") -> str:
    """
    Upload document to Supabase Storage.
    Returns the storage path.
    """
    sb = get_supabase()
    sb.storage.from_("documents").upload(
        path=path,
        file=file_bytes,
        file_options={"content-type": content_type, "upsert": "true"}
    )
    return path


async def get_document_url(path: str, expires_in: int = 3600) -> str:
    """Get a signed URL for a private document"""
    sb = get_supabase()
    result = sb.storage.from_("documents").create_signed_url(
        path=path,
        expires_in=expires_in
    )
    return result.get("signedURL", "")


# ─────────────────────────────────────────────
# UNIVERSITY APPLICATIONS
# ─────────────────────────────────────────────

async def save_university_application(student_id: str, program: dict, reference: str) -> dict:
    """Save a university application record"""
    sb = get_supabase()
    result = sb.table("university_applications").insert({
        "student_id": student_id,
        "university_id": program.get("university_id"),
        "program_name": program.get("program_name"),
        "university_name": program.get("university_name"),
        "reference_number": reference,
        "status": "submitted"
    }).execute()
    return result.data[0] if result.data else {}


async def get_student_university_applications(student_id: str) -> list:
    """Get all university applications for a student"""
    sb = get_supabase()
    result = sb.table("university_applications")\
        .select("*")\
        .eq("student_id", student_id)\
        .order("submitted_at", desc=True)\
        .execute()
    return result.data


# ─────────────────────────────────────────────
# JOB APPLICATIONS
# ─────────────────────────────────────────────

async def save_job_application(student_id: str, job: dict, reference: str, cover_letter: str = None) -> dict:
    """Save a job application record"""
    sb = get_supabase()
    result = sb.table("job_applications").insert({
        "student_id": student_id,
        "job_id": job.get("id"),
        "job_title": job.get("title"),
        "company": job.get("company"),
        "reference_number": reference,
        "cover_letter": cover_letter,
        "status": "submitted"
    }).execute()
    return result.data[0] if result.data else {}


async def get_student_job_applications(student_id: str) -> list:
    """Get all job applications for a student"""
    sb = get_supabase()
    result = sb.table("job_applications")\
        .select("*")\
        .eq("student_id", student_id)\
        .order("submitted_at", desc=True)\
        .execute()
    return result.data


# ─────────────────────────────────────────────
# JOBS
# ─────────────────────────────────────────────

async def save_jobs(jobs: list) -> int:
    """Bulk save scraped jobs, skip duplicates"""
    sb = get_supabase()
    if not jobs:
        return 0
    result = sb.table("jobs")\
        .upsert(jobs, on_conflict="source_id,source")\
        .execute()
    return len(result.data)


async def search_jobs_db(field: str = None, province: str = None, limit: int = 20) -> list:
    """Search active jobs from database"""
    sb = get_supabase()
    query = sb.table("jobs").select("*").eq("is_active", True)
    
    if field:
        query = query.ilike("field", f"%{field}%")
    if province:
        query = query.ilike("province", f"%{province}%")
    
    result = query.order("posted_at", desc=True).limit(limit).execute()
    return result.data


# ─────────────────────────────────────────────
# UNIVERSITY PROGRAMS
# ─────────────────────────────────────────────

async def get_all_programs() -> list:
    """Get all active university programs with university info"""
    sb = get_supabase()
    result = sb.table("university_programs")\
        .select("*, universities(name, short_name, location, province, application_url, application_email, closing_date)")\
        .eq("active", True)\
        .execute()
    return result.data
