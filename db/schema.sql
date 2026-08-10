-- CaseMind schema — CockroachDB
-- NOTE: To be reviewed against the CockroachDB Agent Skills Repo's
-- schema-design guidance in Phase 1 before being finalized (see roadmap §4).
-- All data loaded against this schema is SYNTHETIC (see db/seed_synthetic_data.sql).

CREATE TABLE cases (
    case_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    entity_id UUID NOT NULL,
    narrative TEXT NOT NULL,
    narrative_embedding VECTOR(1536),
    status TEXT NOT NULL DEFAULT 'open',
    created_at TIMESTAMPTZ DEFAULT now(),
    updated_at TIMESTAMPTZ DEFAULT now()
);

CREATE TABLE entities (
    entity_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    entity_name TEXT NOT NULL,
    entity_type TEXT NOT NULL,
    risk_notes TEXT,
    created_at TIMESTAMPTZ DEFAULT now()
);

CREATE TABLE decisions (
    decision_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    case_id UUID REFERENCES cases(case_id),
    decision TEXT NOT NULL,       -- escalate / clear / monitor
    confidence FLOAT,
    reasoning TEXT,
    retrieved_case_ids UUID[],    -- audit trail: which memories informed this decision
    created_at TIMESTAMPTZ DEFAULT now()
);

CREATE VECTOR INDEX ON cases (narrative_embedding);
