-- =============================================
-- UniApply + JobApply - Supabase Schema
-- Run this in Supabase SQL Editor
-- supabase.com → SQL Editor → New Query
-- =============================================


-- ─── STUDENTS ───
-- Core student profile, shared across UniApply and JobApply
CREATE TABLE IF NOT EXISTS students (
    id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    phone_number TEXT UNIQUE NOT NULL,       -- WhatsApp number e.g. whatsapp:+27821234567
    name TEXT,
    id_number TEXT,                          -- SA ID (13 digits, encrypted ideally)
    home_address TEXT,
    city TEXT,
    province TEXT,

    -- Consent
    consent_given BOOLEAN DEFAULT FALSE,
    consent_at TIMESTAMPTZ,

    -- Conversation state
    -- States: greeting → consent → collecting_name → collecting_id →
    --         collecting_address → uploading_matric → confirming_results →
    --         uploading_id → collecting_preferences → searching → 
    --         confirming_applications → applying → completed
    conversation_state TEXT DEFAULT 'greeting',
    current_service TEXT DEFAULT 'uni',      -- 'uni' or 'jobs'

    -- Documents (Supabase Storage paths)
    matric_cert_path TEXT,                   -- storage path in 'documents' bucket
    id_doc_path TEXT,                        -- storage path in 'documents' bucket
    cv_path TEXT,                            -- storage path in 'documents' bucket

    -- Extracted data
    matric_results JSONB,                    -- extracted from certificate
    cv_data JSONB,                           -- extracted from CV
    profile JSONB,                           -- computed profile (APS, skills, etc.)

    -- Preferences
    study_field TEXT,                        -- for UniApply
    job_field TEXT,                          -- for JobApply
    job_location TEXT,
    salary_expectation TEXT,

    -- Temporary agent state (clears between sessions)
    agent_state JSONB DEFAULT '{}',

    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);


-- ─── UNIVERSITIES ───
CREATE TABLE IF NOT EXISTS universities (
    id TEXT PRIMARY KEY,                     -- e.g. 'uct', 'wits'
    name TEXT NOT NULL,
    short_name TEXT NOT NULL,
    location TEXT,
    province TEXT,
    application_url TEXT,
    application_email TEXT,
    closing_date TEXT,
    active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMPTZ DEFAULT NOW()
);


-- ─── UNIVERSITY PROGRAMS ───
CREATE TABLE IF NOT EXISTS university_programs (
    id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    university_id TEXT REFERENCES universities(id),
    name TEXT NOT NULL,
    faculty TEXT,
    duration TEXT,
    min_aps INTEGER,
    required_subjects JSONB DEFAULT '[]',   -- [{name, min_level, notes}]
    notes TEXT,
    active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMPTZ DEFAULT NOW()
);


-- ─── JOBS ───
CREATE TABLE IF NOT EXISTS jobs (
    id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    title TEXT NOT NULL,
    company TEXT NOT NULL,
    location TEXT,
    province TEXT,
    salary_min INTEGER,
    salary_max INTEGER,
    salary_text TEXT,                        -- raw salary string e.g. "R15,000 - R18,000"
    description TEXT,
    requirements TEXT,
    field TEXT,                              -- IT, Engineering, Finance, etc.
    experience_level TEXT,                   -- Entry, Mid, Senior
    source TEXT,                             -- pnet, careerjunction, indeed
    source_url TEXT,                         -- original job posting URL
    source_id TEXT,                          -- ID on source platform
    posted_at TIMESTAMPTZ,
    closes_at TIMESTAMPTZ,
    is_active BOOLEAN DEFAULT TRUE,
    scraped_at TIMESTAMPTZ DEFAULT NOW(),
    created_at TIMESTAMPTZ DEFAULT NOW()
);


-- ─── UNIVERSITY APPLICATIONS ───
CREATE TABLE IF NOT EXISTS university_applications (
    id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    student_id UUID REFERENCES students(id),
    university_id TEXT REFERENCES universities(id),
    program_id UUID REFERENCES university_programs(id),
    program_name TEXT,                       -- denormalized for easy access
    university_name TEXT,
    reference_number TEXT,
    status TEXT DEFAULT 'submitted',         -- submitted, received, accepted, rejected, waitlisted
    submitted_at TIMESTAMPTZ DEFAULT NOW(),
    response_at TIMESTAMPTZ,
    notes TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW()
);


-- ─── JOB APPLICATIONS ───
CREATE TABLE IF NOT EXISTS job_applications (
    id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    student_id UUID REFERENCES students(id),
    job_id UUID REFERENCES jobs(id),
    job_title TEXT,                          -- denormalized
    company TEXT,                            -- denormalized
    reference_number TEXT,
    cover_letter TEXT,                       -- generated cover letter
    status TEXT DEFAULT 'submitted',         -- submitted, viewed, interview, offered, rejected
    submitted_at TIMESTAMPTZ DEFAULT NOW(),
    response_at TIMESTAMPTZ,
    interview_at TIMESTAMPTZ,
    notes TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW()
);


-- ─── CONVERSATION HISTORY ───
CREATE TABLE IF NOT EXISTS conversations (
    id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    student_id UUID REFERENCES students(id),
    role TEXT NOT NULL,                      -- 'user' or 'assistant'
    message TEXT NOT NULL,
    media_url TEXT,                          -- if message had attachment
    created_at TIMESTAMPTZ DEFAULT NOW()
);


-- ─── INDEXES ───
CREATE INDEX IF NOT EXISTS idx_students_phone ON students(phone_number);
CREATE INDEX IF NOT EXISTS idx_jobs_field ON jobs(field);
CREATE INDEX IF NOT EXISTS idx_jobs_active ON jobs(is_active);
CREATE INDEX IF NOT EXISTS idx_jobs_location ON jobs(province);
CREATE INDEX IF NOT EXISTS idx_uni_apps_student ON university_applications(student_id);
CREATE INDEX IF NOT EXISTS idx_job_apps_student ON job_applications(student_id);
CREATE INDEX IF NOT EXISTS idx_conversations_student ON conversations(student_id);
CREATE INDEX IF NOT EXISTS idx_programs_university ON university_programs(university_id);


-- ─── AUTO UPDATE updated_at ───
CREATE OR REPLACE FUNCTION update_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER students_updated_at
    BEFORE UPDATE ON students
    FOR EACH ROW EXECUTE FUNCTION update_updated_at();


-- ─── ROW LEVEL SECURITY ───
-- Enable RLS on all tables
ALTER TABLE students ENABLE ROW LEVEL SECURITY;
ALTER TABLE university_applications ENABLE ROW LEVEL SECURITY;
ALTER TABLE job_applications ENABLE ROW LEVEL SECURITY;
ALTER TABLE conversations ENABLE ROW LEVEL SECURITY;
ALTER TABLE jobs ENABLE ROW LEVEL SECURITY;
ALTER TABLE universities ENABLE ROW LEVEL SECURITY;
ALTER TABLE university_programs ENABLE ROW LEVEL SECURITY;

-- Service role bypasses RLS (your backend uses service key)
-- This is safe because service key is only in your backend


-- ─── STORAGE BUCKETS ───
-- Run these separately in Supabase Storage settings
-- Or use the dashboard to create:
--   Bucket: 'documents'  (private, for CVs, matric certs, IDs)
--   Bucket: 'public'     (public, for any public assets)

-- =============================================
-- SEED DATA - Universities
-- =============================================

INSERT INTO universities (id, name, short_name, location, province, application_url, application_email, closing_date) VALUES
('uct',          'University of Cape Town',          'UCT',   'Cape Town',    'Western Cape', 'https://apply.uct.ac.za',          'admissions@uct.ac.za',       '31 July'),
('wits',         'University of the Witwatersrand',  'Wits',  'Johannesburg', 'Gauteng',      'https://www.wits.ac.za/apply',     'applications@wits.ac.za',    '30 September'),
('stellenbosch', 'Stellenbosch University',          'SU',    'Stellenbosch', 'Western Cape', 'https://www.sun.ac.za/apply',      'info@sun.ac.za',             '31 July'),
('up',           'University of Pretoria',           'UP',    'Pretoria',     'Gauteng',      'https://www.up.ac.za/apply',       'ssc@up.ac.za',               '31 August'),
('unisa',        'University of South Africa',       'UNISA', 'Pretoria',     'National',     'https://www.unisa.ac.za/apply',    'study-info@unisa.ac.za',     'October'),
('uj',           'University of Johannesburg',       'UJ',    'Johannesburg', 'Gauteng',      'https://www.uj.ac.za/apply',       'admission@uj.ac.za',         '30 September'),
('ukzn',         'University of KwaZulu-Natal',      'UKZN',  'Durban',       'KwaZulu-Natal','https://www.ukzn.ac.za/apply',     'cao@ukzn.ac.za',             '30 September'),
('nwu',          'North-West University',            'NWU',   'Potchefstroom','North West',   'https://www.nwu.ac.za/apply',      'admissions@nwu.ac.za',       '30 September')
ON CONFLICT (id) DO NOTHING;


-- UCT Programs
INSERT INTO university_programs (university_id, name, faculty, duration, min_aps, required_subjects, notes) VALUES
('uct', 'Bachelor of Science in Computer Science',  'Science',                        '3 years', 36, '[{"name":"Mathematics","min_level":"B"},{"name":"English","min_level":"C"}]', 'Mathematics B minimum'),
('uct', 'Bachelor of Commerce',                     'Commerce',                       '3 years', 34, '[{"name":"Mathematics","min_level":"C"},{"name":"English","min_level":"C"}]', ''),
('uct', 'Bachelor of Science in Engineering',       'Engineering & Built Environment', '4 years', 40, '[{"name":"Mathematics","min_level":"A"},{"name":"Physical Sciences","min_level":"B"},{"name":"English","min_level":"C"}]', 'Very competitive'),
('uct', 'Bachelor of Laws (LLB)',                   'Law',                            '4 years', 38, '[{"name":"English","min_level":"B"}]', ''),
('uct', 'Bachelor of Medicine and Surgery (MBChB)', 'Health Sciences',                '6 years', 42, '[{"name":"Mathematics","min_level":"A"},{"name":"Physical Sciences","min_level":"A"},{"name":"Life Sciences","min_level":"A"},{"name":"English","min_level":"B"}]', 'Extremely competitive'),
('uct', 'Bachelor of Arts',                        'Humanities',                     '3 years', 30, '[{"name":"English","min_level":"C"}]', '');

-- Wits Programs  
INSERT INTO university_programs (university_id, name, faculty, duration, min_aps, required_subjects, notes) VALUES
('wits', 'Bachelor of Science in Computer Science',   'Science',                    '3 years', 35, '[{"name":"Mathematics","min_level":"C"},{"name":"English","min_level":"C"}]', ''),
('wits', 'Bachelor of Engineering (Civil)',           'Engineering & Built Environment','4 years',38,'[{"name":"Mathematics","min_level":"B"},{"name":"Physical Sciences","min_level":"B"},{"name":"English","min_level":"C"}]',''),
('wits', 'Bachelor of Commerce',                     'Commerce, Law & Management',  '3 years', 34, '[{"name":"Mathematics","min_level":"C"},{"name":"English","min_level":"C"}]', ''),
('wits', 'Bachelor of Laws (LLB)',                   'Commerce, Law & Management',  '4 years', 36, '[{"name":"English","min_level":"B"}]', ''),
('wits', 'Bachelor of Arts',                         'Humanities',                  '3 years', 28, '[{"name":"English","min_level":"C"}]', '');

-- UP Programs
INSERT INTO university_programs (university_id, name, faculty, duration, min_aps, required_subjects, notes) VALUES
('up', 'Bachelor of Science in Computer Science',    'Engineering, Built Environment & IT', '3 years', 32, '[{"name":"Mathematics","min_level":"C"},{"name":"English","min_level":"C"}]', ''),
('up', 'Bachelor of Engineering (Computer)',         'Engineering, Built Environment & IT', '4 years', 35, '[{"name":"Mathematics","min_level":"B"},{"name":"Physical Sciences","min_level":"C"},{"name":"English","min_level":"C"}]', ''),
('up', 'Bachelor of Commerce',                      'Economic & Management Sciences',      '3 years', 30, '[{"name":"Mathematics","min_level":"C"},{"name":"English","min_level":"C"}]', ''),
('up', 'Bachelor of Laws (LLB)',                    'Law',                                 '4 years', 30, '[{"name":"English","min_level":"C"}]', ''),
('up', 'Bachelor of Arts',                          'Humanities',                          '3 years', 26, '[{"name":"English","min_level":"D"}]', '');

-- UNISA Programs
INSERT INTO university_programs (university_id, name, faculty, duration, min_aps, required_subjects, notes) VALUES
('unisa', 'Bachelor of Science in Computing',  'Science, Engineering & Technology',  '3 years (distance)', 20, '[{"name":"Mathematics","min_level":"D"},{"name":"English","min_level":"D"}]', 'Distance learning'),
('unisa', 'Bachelor of Commerce',              'Economic & Management Sciences',     '3 years (distance)', 20, '[{"name":"Mathematics","min_level":"D"},{"name":"English","min_level":"D"}]', 'Distance learning'),
('unisa', 'Bachelor of Arts',                 'Humanities',                         '3 years (distance)', 18, '[{"name":"English","min_level":"D"}]', 'Distance learning'),
('unisa', 'Bachelor of Laws (LLB)',            'Law',                                '4 years (distance)', 22, '[{"name":"English","min_level":"C"}]', 'Distance learning'),
('unisa', 'Bachelor of Education',             'Education',                          '4 years (distance)', 20, '[{"name":"English","min_level":"D"}]', 'Distance learning');
