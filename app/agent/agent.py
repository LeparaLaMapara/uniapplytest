"""
UniApply + JobApply AI Agent
Uses Claude's tool use to reason and act autonomously.
This is a TRUE AGENT - Claude decides what to do, not a scripted bot.
"""
import anthropic
import json
import logging
import hashlib
from datetime import datetime
from app.core.config import settings
from app.core.supabase import (
    get_or_create_student, update_student, save_message, get_recent_messages,
    upload_document, get_all_programs, save_university_application,
    save_job_application, get_student_university_applications,
    get_student_job_applications, search_jobs_db
)
from app.services.whatsapp import send_message
from app.services.documents import extract_matric_results, extract_id_document, extract_cv, calculate_aps
from app.services.scraper import search_and_store_jobs

logger = logging.getLogger(__name__)
claude = anthropic.Anthropic(api_key=settings.ANTHROPIC_API_KEY)


# ─────────────────────────────────────────────
# AGENT TOOLS
# These are the actions Claude can take
# ─────────────────────────────────────────────

TOOLS = [
    {
        "name": "send_whatsapp",
        "description": "Send a WhatsApp message to the student. Use this to communicate, ask questions, share results, or provide updates.",
        "input_schema": {
            "type": "object",
            "properties": {
                "message": {
                    "type": "string",
                    "description": "The message to send. Supports WhatsApp markdown: *bold*, _italic_"
                }
            },
            "required": ["message"]
        }
    },
    {
        "name": "update_student_profile",
        "description": "Save or update student information in the database. Use after collecting any student data.",
        "input_schema": {
            "type": "object",
            "properties": {
                "field": {
                    "type": "string",
                    "description": "Field to update",
                    "enum": ["name", "id_number", "home_address", "city", "province",
                             "conversation_state", "study_field", "job_field",
                             "job_location", "salary_expectation", "agent_state",
                             "current_service", "consent_given", "matric_results",
                             "cv_data", "profile"]
                },
                "value": {
                    "description": "Value to set (string, number, boolean, or object)"
                }
            },
            "required": ["field", "value"]
        }
    },
    {
        "name": "process_matric_certificate",
        "description": "Read and extract matric results from the photo/PDF the student sent. Call this when student sends their matric certificate.",
        "input_schema": {
            "type": "object",
            "properties": {
                "media_url": {
                    "type": "string",
                    "description": "URL of the matric certificate image/PDF"
                }
            },
            "required": ["media_url"]
        }
    },
    {
        "name": "process_id_document",
        "description": "Read and extract information from student's SA ID document.",
        "input_schema": {
            "type": "object",
            "properties": {
                "media_url": {
                    "type": "string",
                    "description": "URL of the ID document image"
                }
            },
            "required": ["media_url"]
        }
    },
    {
        "name": "process_cv",
        "description": "Read and extract information from student's CV. Use when student sends their CV for job applications.",
        "input_schema": {
            "type": "object",
            "properties": {
                "media_url": {
                    "type": "string",
                    "description": "URL of the CV image or PDF"
                },
                "media_type": {
                    "type": "string",
                    "description": "Media type e.g. image/jpeg or application/pdf"
                }
            },
            "required": ["media_url"]
        }
    },
    {
        "name": "find_university_programs",
        "description": "Find university programs the student qualifies for based on their matric results and APS score.",
        "input_schema": {
            "type": "object",
            "properties": {
                "field_preference": {
                    "type": "string",
                    "description": "Field of study preference e.g. Engineering, Medicine, Commerce, Law, IT, Arts. Use 'any' for all fields."
                }
            },
            "required": ["field_preference"]
        }
    },
    {
        "name": "search_jobs",
        "description": "Search for job listings online matching the student's profile, field, and location.",
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "Job search query e.g. 'IT Support Technician', 'Software Developer'"
                },
                "location": {
                    "type": "string",
                    "description": "Location to search in e.g. 'Johannesburg', 'Cape Town', 'South Africa'"
                }
            },
            "required": ["query", "location"]
        }
    },
    {
        "name": "submit_university_applications",
        "description": "Submit university applications for the student. Only call after student has confirmed which programs they want to apply to.",
        "input_schema": {
            "type": "object",
            "properties": {
                "programs": {
                    "type": "array",
                    "description": "List of programs to apply to",
                    "items": {
                        "type": "object",
                        "properties": {
                            "university_id": {"type": "string"},
                            "university_name": {"type": "string"},
                            "program_name": {"type": "string"},
                            "application_url": {"type": "string"},
                            "application_email": {"type": "string"}
                        }
                    }
                }
            },
            "required": ["programs"]
        }
    },
    {
        "name": "submit_job_applications",
        "description": "Submit job applications for the student. Only call after student confirms which jobs they want to apply to.",
        "input_schema": {
            "type": "object",
            "properties": {
                "jobs": {
                    "type": "array",
                    "description": "List of jobs to apply to",
                    "items": {
                        "type": "object",
                        "properties": {
                            "id": {"type": "string"},
                            "title": {"type": "string"},
                            "company": {"type": "string"},
                            "source_url": {"type": "string"}
                        }
                    }
                }
            },
            "required": ["jobs"]
        }
    },
    {
        "name": "get_application_status",
        "description": "Get current application status for the student (both university and job applications).",
        "input_schema": {
            "type": "object",
            "properties": {},
            "required": []
        }
    }
]


# ─────────────────────────────────────────────
# TOOL EXECUTION
# ─────────────────────────────────────────────

async def execute_tool(tool_name: str, tool_input: dict, student: dict, media_urls: list, media_types: list) -> str:
    """Execute a tool call from Claude and return the result"""
    phone = student["phone_number"]

    try:
        if tool_name == "send_whatsapp":
            await send_message(phone, tool_input["message"])
            return "Message sent successfully"

        elif tool_name == "update_student_profile":
            field = tool_input["field"]
            value = tool_input["value"]
            await update_student(phone, {field: value})
            student[field] = value  # Update local copy too
            return f"Updated {field} successfully"

        elif tool_name == "process_matric_certificate":
            url = tool_input.get("media_url") or (media_urls[0] if media_urls else None)
            if not url:
                return "Error: No document URL provided"

            results = await extract_matric_results(url)

            if "error" in results:
                return f"Error: {results['error']}"

            # Calculate APS if needed
            if not results.get("aps_score") and results.get("subjects"):
                results["aps_score"] = calculate_aps(results["subjects"])

            # Save to Supabase
            profile = {
                "aps_score": results.get("aps_score", 0),
                "endorsement": results.get("endorsement", ""),
                "subjects": results.get("subjects", [])
            }
            await update_student(phone, {
                "matric_results": results,
                "profile": profile,
                "matric_cert_path": url
            })
            student["matric_results"] = results
            student["profile"] = profile

            return json.dumps(results)

        elif tool_name == "process_id_document":
            url = tool_input.get("media_url") or (media_urls[0] if media_urls else None)
            if not url:
                return "Error: No document URL provided"

            result = await extract_id_document(url)
            if "error" not in result:
                updates = {"id_doc_path": url}
                if result.get("full_name") and not student.get("name"):
                    updates["name"] = result["full_name"]
                if result.get("id_number") and not student.get("id_number"):
                    updates["id_number"] = result["id_number"]
                await update_student(phone, updates)

            return json.dumps(result)

        elif tool_name == "process_cv":
            url = tool_input.get("media_url") or (media_urls[0] if media_urls else None)
            media_type = tool_input.get("media_type", media_types[0] if media_types else "image/jpeg")

            if not url:
                return "Error: No CV URL provided"

            cv_data = await extract_cv(url, media_type)
            if "error" not in cv_data:
                await update_student(phone, {
                    "cv_data": cv_data,
                    "cv_path": url
                })
                student["cv_data"] = cv_data

            return json.dumps(cv_data)

        elif tool_name == "find_university_programs":
            profile = student.get("profile", {})
            aps_score = profile.get("aps_score", 0)
            subjects = profile.get("subjects", [])
            endorsement = profile.get("endorsement", "")
            field_preference = tool_input.get("field_preference", "any")

            if not aps_score:
                return "Error: No matric results found. Student needs to upload matric certificate first."

            # Get programs from Supabase
            all_programs = await get_all_programs()
            matches = match_programs(all_programs, aps_score, subjects, endorsement, field_preference)

            # Store in agent state
            agent_state = student.get("agent_state", {}) or {}
            agent_state["matching_programs"] = matches[:10]
            await update_student(phone, {"agent_state": agent_state})
            student["agent_state"] = agent_state

            return json.dumps({"total_matches": len(matches), "programs": matches[:10]})

        elif tool_name == "search_jobs":
            query = tool_input["query"]
            location = tool_input.get("location", "South Africa")

            # Search online and store in Supabase
            jobs = await search_and_store_jobs(query, location)

            # Also check database for recent matches
            if not jobs:
                cv_data = student.get("cv_data", {})
                field = cv_data.get("fields", [query])[0] if cv_data else query
                jobs = await search_jobs_db(field=field, limit=15)

            # Store in agent state
            agent_state = student.get("agent_state", {}) or {}
            agent_state["available_jobs"] = jobs[:10]
            await update_student(phone, {"agent_state": agent_state})
            student["agent_state"] = agent_state

            return json.dumps({"total_found": len(jobs), "jobs": jobs[:10]})

        elif tool_name == "submit_university_applications":
            programs = tool_input["programs"]
            results = []

            for program in programs:
                ref = generate_reference("uni", program.get("university_id", ""), phone)
                await save_university_application(student["id"], program, ref)
                results.append({
                    "university": program.get("university_name"),
                    "program": program.get("program_name"),
                    "reference": ref,
                    "status": "submitted"
                })

            return json.dumps({"applications_submitted": len(results), "results": results})

        elif tool_name == "submit_job_applications":
            jobs = tool_input["jobs"]
            results = []

            for job in jobs:
                ref = generate_reference("job", job.get("company", ""), phone)
                cover_letter = generate_cover_letter(student, job)
                await save_job_application(student["id"], job, ref, cover_letter)
                results.append({
                    "company": job.get("company"),
                    "title": job.get("title"),
                    "reference": ref,
                    "status": "submitted"
                })

            return json.dumps({"applications_submitted": len(results), "results": results})

        elif tool_name == "get_application_status":
            uni_apps = await get_student_university_applications(student["id"])
            job_apps = await get_student_job_applications(student["id"])

            return json.dumps({
                "university_applications": uni_apps,
                "job_applications": job_apps,
                "total": len(uni_apps) + len(job_apps)
            })

        else:
            return f"Unknown tool: {tool_name}"

    except Exception as e:
        logger.error(f"Tool execution error ({tool_name}): {e}", exc_info=True)
        return f"Error executing {tool_name}: {str(e)}"


# ─────────────────────────────────────────────
# MAIN AGENT LOOP
# ─────────────────────────────────────────────

async def run_agent(phone: str, user_message: str, media_urls: list, media_types: list):
    """
    Main agent entry point.
    Claude receives the message, reasons about it, and calls tools autonomously.
    """
    # Get or create student
    student = await get_or_create_student(phone)

    # Save incoming message to history
    await save_message(
        student["id"],
        "user",
        user_message,
        media_urls[0] if media_urls else None
    )

    # Get recent conversation for context
    history = await get_recent_messages(student["id"], limit=15)

    # Build system prompt
    system_prompt = build_system_prompt(student, media_urls)

   # Build messages for Claude
    messages = []

    # Add conversation history - skip empty and fix alternating roles
    prev_role = None
    for msg in history[:-1]:
        content = msg["message"].strip() if msg["message"] else ""
        if not content:
            continue  # Skip empty messages
        role = msg["role"]
        if role == prev_role:
            continue  # Skip consecutive same-role messages
        messages.append({"role": role, "content": content})
        prev_role = role

    # Add current message with media context
    current_content = user_message.strip() if user_message else ""
    if media_urls:
        types_str = ', '.join(media_types) if media_types else "file"
        current_content += f"\n[Student sent {len(media_urls)} file(s): {types_str}]"
    if not current_content.strip():
        current_content = "[Student sent a file or media attachment]"

    # Ensure no consecutive user messages
    if messages and messages[-1]["role"] == "user":
        messages[-1]["content"] += f"\n{current_content}"
    else:
        messages.append({"role": "user", "content": current_content})

    # ─── AGENTIC LOOP ───
    # Claude thinks, calls tools, gets results, thinks again, calls more tools...
    # Until it decides to stop
    max_iterations = 10  # Safety limit

    for iteration in range(max_iterations):
        logger.info(f"Agent iteration {iteration + 1} for {phone}")

        response = claude.messages.create(
            model="claude-opus-4-6",
            max_tokens=4096,
            system=system_prompt,
            tools=TOOLS,
            messages=messages
        )

        # Add assistant response to message history
        messages.append({"role": "assistant", "content": response.content})

        # Check if done
        if response.stop_reason == "end_turn":
            # Extract any final text response
            for block in response.content:
                if hasattr(block, "text") and block.text:
                    await save_message(student["id"], "assistant", block.text)
            break

        # Process tool calls
        if response.stop_reason == "tool_use":
            tool_results = []

            for block in response.content:
                if block.type == "tool_use":
                    logger.info(f"Claude calling tool: {block.name} with {json.dumps(block.input)[:200]}")

                    # Execute the tool
                    result = await execute_tool(
                        block.name,
                        block.input,
                        student,
                        media_urls,
                        media_types
                    )

                    logger.info(f"Tool {block.name} result: {str(result)[:200]}")

                    tool_results.append({
                        "type": "tool_result",
                        "tool_use_id": block.id,
                        "content": result
                    })

            # Add tool results back to conversation
            messages.append({"role": "user", "content": tool_results})

        else:
            # Unexpected stop reason
            break

    logger.info(f"Agent completed for {phone} after {iteration + 1} iterations")


# ─────────────────────────────────────────────
# HELPER FUNCTIONS
# ─────────────────────────────────────────────

def build_system_prompt(student: dict, media_urls: list) -> str:
    """Build the system prompt with full student context"""
    name = student.get("name", "the student")
    state = student.get("conversation_state", "greeting")
    service = student.get("current_service", "uni")
    profile = student.get("profile") or {}
    matric = student.get("matric_results") or {}
    cv_data = student.get("cv_data") or {}
    agent_state = student.get("agent_state") or {}
    has_media = len(media_urls) > 0

    return f"""You are UniApply, an AI agent that helps South African students apply to universities and find jobs via WhatsApp.

You are a TRUE AGENT - you reason about what to do and call tools autonomously. You are NOT a scripted bot.

═══ STUDENT CONTEXT ═══
Name: {name or 'Unknown'}
Phone: {student['phone_number']}
Current State: {state}
Service: {"University Applications" if service == "uni" else "Job Applications"}
Has Files: {has_media}
Consent Given: {student.get('consent_given', False)}

Matric Results: {json.dumps(matric, indent=2) if matric else 'Not yet uploaded'}
APS Score: {profile.get('aps_score', 'Unknown')}
Endorsement: {profile.get('endorsement', 'Unknown')}

CV Data: {json.dumps(cv_data, indent=2) if cv_data else 'Not yet uploaded'}

Agent State (temporary memory): {json.dumps(agent_state, indent=2) if agent_state else 'Empty'}

═══ YOUR MISSION ═══
Help this student:
1. Apply to universities (UniApply) - collect info, read matric cert, find matching programs, apply
2. Find and apply for jobs (JobApply) - collect CV, search jobs online, match to profile, apply

═══ HOW TO BEHAVE ═══
- Be warm, encouraging and supportive - many students are nervous about this process
- Communicate in simple, clear English (not academic language)
- Use WhatsApp formatting: *bold* for important info, numbered lists for options
- Always get consent before collecting personal data (first interaction)
- Verify extracted data with the student before applying
- Be proactive - if you see an opportunity to help, do it
- Handle errors gracefully - if something fails, tell the student simply and try again

═══ CONVERSATION FLOW FOR UNIVERSITY APPLICATIONS ═══
1. Greet and get consent → 2. Collect name, ID, address → 
3. Request matric cert → 4. Extract and confirm results →
5. Request ID document → 6. Ask study field preference →
7. Find matching programs → 8. Student selects programs →
9. Submit applications → 10. Confirm with references

═══ CONVERSATION FLOW FOR JOB APPLICATIONS ═══
1. Greet and get consent → 2. Collect name, contact details →
3. Request CV → 4. Extract and confirm CV data →
5. Ask job field and location → 6. Search jobs online →
7. Present matches → 8. Student selects jobs →
9. Submit applications → 10. Confirm with references

═══ IMPORTANT RULES ═══
- NEVER apply anywhere without explicit student confirmation
- Always show what you found and ask before submitting
- Save EVERYTHING to the database as you collect it
- If student sends a file/image, process it immediately
- Keep track of what's been completed in agent_state
- If student says "jobs" or "find work", switch to job service
- If student says "university" or "apply to uni", switch to university service
- Students can type RESTART to start over, STATUS for application status

═══ SOUTH AFRICAN CONTEXT ═══
- APS score uses best 6 subjects (Life Orientation excluded)
- Bachelor's Pass (APS 23+) needed for university
- Major SA universities: UCT, Wits, Stellenbosch, UP, UNISA, UJ, UKZN
- NSFAS funding available for qualifying students - mention it
- Many students are first-generation university applicants - be extra supportive

Now respond to the student's latest message. Use tools as needed."""


def match_programs(all_programs: list, aps_score: int, subjects: list, endorsement: str, field_preference: str) -> list:
    """Match student to qualifying university programs"""
    if "failed" in endorsement.lower() or "higher certificate" in endorsement.lower():
        return []

    symbol_order = {"A": 8, "B": 7, "C": 6, "D": 5, "E": 4, "F": 3, "G": 2, "H": 1}

    def pct_to_symbol(pct):
        if pct >= 80: return "A"
        elif pct >= 70: return "B"
        elif pct >= 60: return "C"
        elif pct >= 50: return "D"
        elif pct >= 40: return "E"
        elif pct >= 30: return "F"
        return "G"

    def meets_subject_req(required_subjects):
        for req in required_subjects:
            req_name = req.get("name", "").lower()
            min_level = req.get("min_level", "D")

            found = None
            for subj in subjects:
                sname = subj.get("name", "").lower()
                if req_name in sname or sname in req_name:
                    if req_name == "mathematics" and "literacy" in sname:
                        continue
                    found = subj
                    break

            if not found:
                return False

            pct = found.get("percentage", 0)
            sym = found.get("symbol") or pct_to_symbol(pct)
            if symbol_order.get(sym.upper(), 0) < symbol_order.get(min_level.upper(), 0):
                return False
        return True

    matches = []
    for prog in all_programs:
        uni = prog.get("universities", {})
        min_aps = prog.get("min_aps", 0)

        if aps_score < min_aps:
            continue

        required = prog.get("required_subjects", [])
        if not meets_subject_req(required):
            continue

        # Filter by field
        if field_preference and field_preference.lower() not in ["any", "all"]:
            pref = field_preference.lower()
            prog_name = prog.get("name", "").lower()
            faculty = prog.get("faculty", "").lower()

            field_map = {
                "engineering": ["engineer", "built environment"],
                "medicine": ["medicine", "medical", "health", "mbchb"],
                "commerce": ["commerce", "business", "economics", "management"],
                "law": ["law", "llb"],
                "it": ["computer", "computing", "informatics", "it"],
                "science": ["science"],
                "arts": ["arts", "humanities", "social"],
                "education": ["education"],
            }

            keywords = field_map.get(pref, [pref])
            if not any(kw in prog_name or kw in faculty for kw in keywords):
                continue

        matches.append({
            "university_id": prog.get("university_id"),
            "university_name": uni.get("name"),
            "university_short": uni.get("short_name"),
            "location": uni.get("location"),
            "province": uni.get("province"),
            "program_name": prog.get("name"),
            "faculty": prog.get("faculty"),
            "duration": prog.get("duration"),
            "min_aps": min_aps,
            "student_aps": aps_score,
            "margin": aps_score - min_aps,
            "application_url": uni.get("application_url"),
            "application_email": uni.get("application_email"),
            "closing_date": uni.get("closing_date"),
            "notes": prog.get("notes", ""),
        })

    matches.sort(key=lambda x: -x["margin"])
    return matches


def generate_reference(service: str, entity: str, phone: str) -> str:
    """Generate application reference number"""
    data = f"{service}{entity}{phone}{datetime.utcnow().date()}"
    h = hashlib.md5(data.encode()).hexdigest()[:8].upper()
    prefix = "UA" if service == "uni" else "JA"
    entity_code = entity[:3].upper() if entity else "GEN"
    return f"{prefix}-{entity_code}-{h}"


def generate_cover_letter(student: dict, job: dict) -> str:
    """Generate a basic cover letter for a job application"""
    name = student.get("name", "Applicant")
    cv = student.get("cv_data") or {}
    skills = ", ".join(cv.get("skills", [])[:5]) or "relevant skills"
    exp_years = cv.get("experience_years", 0)
    qualification = cv.get("highest_qualification", "qualification")

    return f"""Dear Hiring Manager,

I am writing to apply for the position of {job.get('title')} at {job.get('company')}.

I hold a {qualification} and have {exp_years} year(s) of experience. My key skills include {skills}.

I am confident that my background makes me a strong candidate for this role. I am eager to contribute to your team and would welcome the opportunity to discuss my application further.

Thank you for considering my application.

Yours sincerely,
{name}

Submitted via UniApply Career Assistant"""
