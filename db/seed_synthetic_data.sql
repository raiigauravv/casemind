-- CaseMind synthetic seed data
-- ALL DATA IN THIS FILE IS SYNTHETIC. No real financial data, no real bank
-- names, no real individuals or organizations. Generated solely to
-- demonstrate CaseMind's retrieval + reasoning loop for the hackathon demo.
--
-- narrative_embedding values are NOT populated here — embeddings are
-- generated at load time by agent/vector_search.py (Phase 2) so they stay
-- consistent with whatever embedding model is configured. This file seeds
-- entities, cases (narrative text only), and a couple of historical
-- decisions so the agent has something to retrieve against on first run.

-- ============ SYNTHETIC ENTITIES ============
INSERT INTO entities (entity_id, entity_name, entity_type, risk_notes) VALUES
  ('11111111-1111-1111-1111-111111111111', 'Meridian Holdings LLC (synthetic)', 'business', 'Synthetic shell-company pattern for demo: layered ownership, no physical address on file.'),
  ('22222222-2222-2222-2222-222222222222', 'Priya Chandrasekaran (synthetic)', 'individual', 'Synthetic individual profile: high-frequency small transfers to synthetic entity below.'),
  ('33333333-3333-3333-3333-333333333333', 'Northgate Import-Export Co (synthetic)', 'business', 'Synthetic trade-based pattern: invoice amounts inconsistent with declared goods.'),
  ('44444444-4444-4444-4444-444444444444', 'Tomas Reyes (synthetic)', 'individual', 'Synthetic individual profile: no prior flags, first-time high-value transfer.'),
  ('55555555-5555-5555-5555-555555555555', 'Silverline Consulting FZE (synthetic)', 'business', 'Synthetic entity: registered in synthetic offshore jurisdiction, single-purpose account.');

-- ============ SYNTHETIC HISTORICAL CASES (narrative only; embeddings generated at load time) ============
INSERT INTO cases (case_id, entity_id, narrative, status) VALUES
  ('a1111111-0000-0000-0000-000000000001', '11111111-1111-1111-1111-111111111111',
   'SYNTHETIC CASE. Entity received seven incoming wires over 48 hours totaling $412,000 from unrelated synthetic shell companies, followed by a same-day outbound transfer of 96% of the balance to a synthetic offshore account. No business rationale on file.',
   'closed_escalated'),
  ('a1111111-0000-0000-0000-000000000002', '22222222-2222-2222-2222-222222222222',
   'SYNTHETIC CASE. Individual made 22 structured transfers of $9,200-$9,800 (just under the synthetic $10,000 reporting threshold) to the same synthetic recipient entity over three weeks.',
   'closed_escalated'),
  ('a1111111-0000-0000-0000-000000000003', '33333333-3333-3333-3333-333333333333',
   'SYNTHETIC CASE. Trade-finance invoice for synthetic goods valued at 4x the typical market rate for the stated commodity and quantity, payment routed through two intermediary synthetic jurisdictions.',
   'closed_escalated'),
  ('a1111111-0000-0000-0000-000000000004', '44444444-4444-4444-4444-444444444444',
   'SYNTHETIC CASE. First-time customer wired $85,000 inbound from a synthetic verified payroll source, consistent with a stated home-sale proceeds explanation on file; no other risk indicators.',
   'closed_cleared'),
  ('a1111111-0000-0000-0000-000000000005', '55555555-5555-5555-5555-555555555555',
   'SYNTHETIC CASE. Newly opened synthetic business account received a single large inbound wire from a synthetic entity with no prior relationship, then remained dormant for 60 days before a full-balance withdrawal.',
   'open');

-- ============ SYNTHETIC HISTORICAL DECISIONS ============
INSERT INTO decisions (case_id, decision, confidence, reasoning, retrieved_case_ids) VALUES
  ('a1111111-0000-0000-0000-000000000001', 'escalate', 0.91,
   'SYNTHETIC. Rapid pass-through of funds from multiple unrelated synthetic sources to a single offshore synthetic destination is a classic layering pattern; no counter-evidence of legitimate business purpose.',
   ARRAY[]::UUID[]),
  ('a1111111-0000-0000-0000-000000000002', 'escalate', 0.88,
   'SYNTHETIC. Transaction sizing clustered just under the synthetic reporting threshold across many repeated transfers to one recipient is a textbook structuring signature.',
   ARRAY[]::UUID[]),
  ('a1111111-0000-0000-0000-000000000003', 'escalate', 0.79,
   'SYNTHETIC. Invoice value materially exceeds market rate for stated goods, routed through intermediary jurisdictions commonly associated with trade-based laundering in this synthetic dataset.',
   ARRAY[]::UUID[]),
  ('a1111111-0000-0000-0000-000000000004', 'clear', 0.84,
   'SYNTHETIC. Source of funds verified against synthetic payroll record and matches stated rationale; no structuring, layering, or velocity anomalies present.',
   ARRAY[]::UUID[]);
