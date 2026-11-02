-- PROPOSAL ONLY. Not executed against the source database.
-- Check the full workload, disk headroom, replication/load and maintenance window first.
-- First candidate: cover the industry-first lookup, including its deleted predicate.
-- Existing chain_id(industry_chain_id) and idx_chain_pos(industry_chain_id,position_id)
-- do not include deleted. DISTINCT across multiple industry IDs is still required.
ALTER TABLE c_position_chain
  ADD INDEX idx_chain_deleted_position (industry_chain_id, deleted, position_id);

-- Separate, conditional candidate for geography-first queries, especially without an industry filter.
-- The current industry-first benchmark does not establish its benefit; verify that workload first.
ALTER TABLE c_company_position
  ADD INDEX idx_address_state_deleted (company_address_id, publish_state, deleted);

-- Do not drop existing indexes automatically. Benchmark and assess other consumers first.
